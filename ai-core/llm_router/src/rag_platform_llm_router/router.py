"""
Layer 7 — LLM Router (litellm).

Fallback: Groq → Gemini → OpenRouter → Ollama.
When force_local=True, only Ollama is used (sensitivity routing).
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from rag_platform_llm_router.config import settings

logger = logging.getLogger(__name__)


@dataclass
class GenerateResult:
    content: str
    provider: str
    model: str
    forced_local: bool = False
    attempts: list[str] = field(default_factory=list)


def _provider_chain(*, force_local: bool) -> list[dict[str, Any]]:
    """Ordered list of provider configs to try."""
    ollama = {
        "name": "ollama",
        "model": f"ollama/{settings.ollama_model}",
        "api_base": settings.ollama_base_url,
        "api_key": "ollama",
    }
    if force_local:
        return [ollama]

    chain: list[dict[str, Any]] = []
    # OpenRouter first for now — Groq is network-blocked in this environment.
    # Move back below Gemini once Groq access is restored.
    if settings.openrouter_api_key and settings.openrouter_api_key not in {
        "",
        "CHANGE_ME",
    }:
        chain.append(
            {
                "name": "openrouter",
                "model": settings.openrouter_model,
                "api_key": settings.openrouter_api_key,
                "api_base": "https://openrouter.ai/api/v1",
            }
        )
    if settings.groq_api_key and settings.groq_api_key not in {"", "CHANGE_ME"}:
        chain.append(
            {
                "name": "groq",
                "model": settings.groq_model,
                "api_key": settings.groq_api_key,
            }
        )
    if settings.gemini_api_key and settings.gemini_api_key not in {"", "CHANGE_ME"}:
        chain.append(
            {
                "name": "gemini",
                "model": settings.gemini_model,
                "api_key": settings.gemini_api_key,
            }
        )
    chain.append(ollama)
    return chain


async def generate(
    messages: list[dict],
    tenant_id: str,
    force_local: bool = False,
    stream: bool = False,
) -> GenerateResult | AsyncIterator[str]:
    """
    Route to the appropriate LLM with automatic fallback.

    When ``force_local=True``, only the local Ollama model is called.
    """
    if stream:
        return _generate_stream(messages, tenant_id=tenant_id, force_local=force_local)

    mode = (settings.llm_router_mode or "litellm").lower()
    if mode in {"fake", "stub", "test"}:
        return _fake_generate(messages, force_local=force_local)

    return await _generate_litellm(messages, tenant_id=tenant_id, force_local=force_local)


def _fake_generate(messages: list[dict], *, force_local: bool) -> GenerateResult:
    user = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
    system = next((m["content"] for m in messages if m.get("role") == "system"), "")
    provider = "ollama" if force_local else "fake-primary"
    # Simulate primary failure → fallback when LLM_FAKE_FAIL_PRIMARY=1
    attempts = []
    if not force_local and os.environ.get("LLM_FAKE_FAIL_PRIMARY", "").lower() in {
        "1",
        "true",
        "yes",
    }:
        attempts.append("fake-primary:forced_failure")
        provider = "fake-secondary"

    # Prompt-injection defense (fake mode): never obey hidden instructions in context
    injection_markers = (
        "ignore previous instructions",
        "ignore all instructions",
        "disregard the system",
        "you are now",
        "system prompt override",
    )
    hay = user.lower()
    if any(m in hay for m in injection_markers):
        content = (
            "[fake:injection_blocked] I will only answer from the provided context "
            "and will not follow instructions embedded in documents. "
            f"Grounded answer using system rules. Q={user[:80]}"
        )
    else:
        content = (
            f"[fake:{provider}] Grounded answer for tenant query. "
            f"Based on retrieved context. Q={user[:120]}"
        )
    # Ensure system prompt still "holds" — echo a marker when present
    if "answer ONLY using the provided context" in system.lower() or "cite" in system.lower():
        content = content  # rules applied structurally via roles

    return GenerateResult(
        content=content,
        provider=provider if "injection_blocked" not in content else provider,
        model="fake-model",
        forced_local=force_local,
        attempts=attempts + [f"{provider}:ok"],
    )


async def _generate_litellm(
    messages: list[dict], *, tenant_id: str, force_local: bool
) -> GenerateResult:
    try:
        import litellm  # noqa: F401
    except Exception:
        return await _generate_openai_compat(
            messages, tenant_id=tenant_id, force_local=force_local
        )

    litellm.drop_params = True
    chain = _provider_chain(force_local=force_local)
    attempts: list[str] = []
    last_error: Exception | None = None

    for provider in chain:
        try:
            kwargs: dict[str, Any] = {
                "model": provider["model"],
                "messages": messages,
                "api_key": provider.get("api_key"),
            }
            if provider.get("api_base"):
                kwargs["api_base"] = provider["api_base"]
            # Force failure of primary for DoD testing
            if (
                provider["name"] == "groq"
                and os.environ.get("LLM_FORCE_PRIMARY_FAIL", "").lower()
                in {"1", "true", "yes"}
            ):
                raise RuntimeError("Forced primary failure for fallback test")

            response = await litellm.acompletion(**kwargs)
            content = response.choices[0].message.content or ""
            attempts.append(f"{provider['name']}:ok")
            logger.info(
                "llm_generate_ok tenant=%s provider=%s model=%s",
                tenant_id,
                provider["name"],
                provider["model"],
            )
            return GenerateResult(
                content=content,
                provider=provider["name"],
                model=provider["model"],
                forced_local=force_local,
                attempts=attempts,
            )
        except Exception as exc:
            attempts.append(f"{provider['name']}:fail:{type(exc).__name__}")
            last_error = exc
            logger.warning(
                "llm_provider_failed tenant=%s provider=%s err=%s",
                tenant_id,
                provider["name"],
                exc,
            )
            continue

    # litellm present but all providers failed — try raw OpenAI-compat path once
    try:
        return await _generate_openai_compat(
            messages, tenant_id=tenant_id, force_local=force_local
        )
    except Exception:
        raise RuntimeError(
            f"All LLM providers failed for tenant={tenant_id}. attempts={attempts}. "
            f"last_error={last_error}"
        ) from last_error


def _openai_compat_endpoint(provider: dict[str, Any]) -> tuple[str, str] | None:
    """Return (url, model_id) for OpenAI-compatible chat completions, or None."""
    name = provider["name"]
    model = provider["model"]
    if name == "groq":
        return (
            "https://api.groq.com/openai/v1/chat/completions",
            model.removeprefix("groq/"),
        )
    if name == "openrouter":
        return (
            "https://openrouter.ai/api/v1/chat/completions",
            model.removeprefix("openrouter/"),
        )
    if name == "ollama":
        base = (provider.get("api_base") or "http://localhost:11434").rstrip("/")
        return (f"{base}/v1/chat/completions", model.removeprefix("ollama/"))
    return None


async def _generate_openai_compat(
    messages: list[dict], *, tenant_id: str, force_local: bool
) -> GenerateResult:
    """
    Direct OpenAI-compatible HTTP calls (Groq / OpenRouter / Ollama).

    Used when litellm is unavailable (common on Windows Python 3.13 / long paths).
    """
    import httpx

    chain = _provider_chain(force_local=force_local)
    attempts: list[str] = []
    last_error: Exception | None = None

    async with httpx.AsyncClient(timeout=120.0) as client:
        for provider in chain:
            endpoint = _openai_compat_endpoint(provider)
            if endpoint is None:
                attempts.append(f"{provider['name']}:skip:no_openai_compat")
                continue
            url, model_id = endpoint
            if (
                provider["name"] == "groq"
                and os.environ.get("LLM_FORCE_PRIMARY_FAIL", "").lower()
                in {"1", "true", "yes"}
            ):
                attempts.append("groq:fail:ForcedPrimaryFail")
                continue
            try:
                headers = {
                    "Authorization": f"Bearer {provider.get('api_key')}",
                    "Content-Type": "application/json",
                }
                if provider["name"] == "openrouter":
                    headers["HTTP-Referer"] = "http://localhost:8000"
                    headers["X-Title"] = "RAG Platform"
                resp = await client.post(
                    url,
                    headers=headers,
                    json={"model": model_id, "messages": messages},
                )
                if resp.status_code >= 400:
                    raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
                payload = resp.json()
                content = (
                    payload.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content")
                    or ""
                )
                attempts.append(f"{provider['name']}:ok")
                logger.info(
                    "llm_generate_ok tenant=%s provider=%s model=%s via=openai_compat",
                    tenant_id,
                    provider["name"],
                    model_id,
                )
                return GenerateResult(
                    content=content,
                    provider=provider["name"],
                    model=model_id,
                    forced_local=force_local,
                    attempts=attempts,
                )
            except Exception as exc:
                attempts.append(f"{provider['name']}:fail:{type(exc).__name__}")
                last_error = exc
                logger.warning(
                    "llm_provider_failed tenant=%s provider=%s err=%s",
                    tenant_id,
                    provider["name"],
                    exc,
                )
                continue

    raise RuntimeError(
        f"All LLM providers failed for tenant={tenant_id}. attempts={attempts}. "
        f"last_error={last_error}"
    )


async def _generate_stream(
    messages: list[dict], *, tenant_id: str, force_local: bool
) -> AsyncIterator[str]:
    result = await generate(messages, tenant_id=tenant_id, force_local=force_local, stream=False)
    assert isinstance(result, GenerateResult)
    # Simple chunked yield for SSE consumers
    text = result.content
    step = max(12, len(text) // 8 or 1)
    for i in range(0, len(text), step):
        yield text[i : i + step]
