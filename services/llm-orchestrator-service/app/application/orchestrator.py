"""Orchestration use-cases."""

from __future__ import annotations

import asyncio
import os
from typing import Any

# Faithfulness check is a *second* full LLM call after the main answer — cap
# how long we'll wait for it so a slow/free-tier provider never doubles the
# user-visible latency of an otherwise-fast answer.
FAITHFULNESS_CHECK_TIMEOUT_S = 6.0

from app.application.prompting import (
    apply_guardrails,
    assemble_messages,
    build_citations,
    build_faithfulness_check_messages,
    is_meta_or_greeting,
    parse_faithfulness_verdict,
    parse_requirements_json,
    requires_local_only,
)
from app.infrastructure import clients
from rag_platform_llm_router import generate
from rag_platform_llm_router.router import GenerateResult
from rag_platform_observability import LLM_PROVIDER_COUNT, get_logger, get_tracer
from rag_platform_pii import scrub, scrub_messages
from rag_platform_schemas.orchestration import (
    ContextChunk,
    ExtractRequirementsResponse,
    OrchestrateRequest,
    OrchestrateResponse,
)

logger = get_logger(__name__)
tracer = get_tracer("llm-orchestrator-service")


async def run_faithfulness_check(
    *,
    answer: str,
    chunks: list[ContextChunk],
    tenant_id: str,
    force_local: bool,
    policy: dict[str, Any] | None = None,
) -> tuple[bool, str | None]:
    """
    Bounded-time groundedness check — a SECOND full LLM call, so it doubles
    the cost and latency of every answer it runs on. Off by default; a tenant
    opts in via Guardrails ("enable_faithfulness_check": true in policy_json)
    if they want that safety net badly enough to pay for it twice.
    """
    if not chunks or not (policy or {}).get("enable_faithfulness_check"):
        return True, None
    try:
        check_messages = build_faithfulness_check_messages(answer=answer, chunks=chunks)

        async def _check() -> GenerateResult:
            result = await generate(
                check_messages, tenant_id=tenant_id, force_local=force_local, stream=False
            )
            assert isinstance(result, GenerateResult)
            return result

        check_result = await asyncio.wait_for(_check(), timeout=FAITHFULNESS_CHECK_TIMEOUT_S)
        return parse_faithfulness_verdict(check_result.content)
    except Exception as exc:
        logger.warning("faithfulness_check_failed", tenant_id=tenant_id, error=str(exc))
        return True, None


def _as_chunks(raw: list[Any]) -> list[ContextChunk]:
    out: list[ContextChunk] = []
    for item in raw:
        if isinstance(item, ContextChunk):
            out.append(item)
        elif isinstance(item, dict):
            out.append(
                ContextChunk(
                    text=item.get("text") or "",
                    doc_id=str(item.get("doc_id")),
                    doc_type=item.get("doc_type"),
                    chunk_index=item.get("chunk_index"),
                    section=item.get("section"),
                    page=item.get("page"),
                    score=item.get("score"),
                )
            )
    return out


async def orchestrate(
    req: OrchestrateRequest, *, tenant_id: str, token: str
) -> OrchestrateResponse:
    # Ensure router mode/env visible to ai-core package
    os.environ.setdefault("LLM_ROUTER_MODE", os.environ.get("LLM_ROUTER_MODE", "fake"))

    with tracer.start_as_current_span("orchestrate") as span:
        span.set_attribute("tenant_id", tenant_id)
        span.set_attribute("query.length", len(req.query))

        if req.chunks is not None:
            chunks = list(req.chunks)
            insufficient = len(chunks) == 0
        elif is_meta_or_greeting(req.query):
            # Greeting/capability question — skip the retrieval round-trip
            # entirely rather than running it and discarding the result.
            chunks, insufficient = [], False
        else:
            with tracer.start_as_current_span("retrieval"):
                raw_chunks, insufficient = await clients.fetch_retrieved_chunks(
                    query=req.query, token=token, doc_type=req.doc_type
                )
            chunks = _as_chunks(raw_chunks)

        if (insufficient or not chunks) and not is_meta_or_greeting(req.query):
            return OrchestrateResponse(
                answer="I don't have enough relevant information in the knowledge base to answer that.",
                citations=[],
                provider="none",
                model="none",
                forced_local=False,
                attempts=[],
                guardrails_applied=[],
                insufficient_information=True,
                metadata={"reason": "retrieval_insufficient"},
            )
        if insufficient or not chunks:
            # Greeting/capability question with no matching context — let the
            # LLM respond conversationally instead of forcing a refusal.
            chunks = []

        system_prompt = req.system_prompt_override
        if system_prompt is None:
            system_prompt = await clients.fetch_active_prompt(tenant_id, token)
        policy = await clients.fetch_active_guardrails(tenant_id, token)

        force_local = requires_local_only(chunks)
        span.set_attribute("force_local", force_local)
        messages = assemble_messages(
            query=req.query,
            chunks=chunks,
            system_prompt=system_prompt,
            chat_history=req.chat_history,
        )
        # Presidio / regex scrub before any cloud LLM tier (not for local employee path)
        messages = scrub_messages(messages, force_local=force_local)

        with tracer.start_as_current_span("llm_router") as llm_span:
            result = await generate(
                messages,
                tenant_id=tenant_id,
                force_local=force_local,
                stream=False,
            )
            assert isinstance(result, GenerateResult)
            llm_span.set_attribute("provider", result.provider)
            LLM_PROVIDER_COUNT.labels(
                "llm-orchestrator-service", result.provider, "ok"
            ).inc()

        answer, applied = apply_guardrails(result.content, policy, query=req.query)
        citations = build_citations(chunks)

        with tracer.start_as_current_span("faithfulness_check"):
            grounded, ungrounded_reason = await run_faithfulness_check(
                answer=result.content,
                chunks=chunks,
                tenant_id=tenant_id,
                force_local=force_local,
                policy=policy,
            )
        if not grounded:
            applied = [*applied, "faithfulness_flagged"]
            answer = (
                f"{answer.rstrip()}\n\n"
                f"_Note: parts of this answer may not be fully supported by the "
                f"source documents ({ungrounded_reason})._"
            )
            logger.warning(
                "answer_not_grounded",
                tenant_id=tenant_id,
                reason=ungrounded_reason,
            )

        logger.info(
            "orchestrate_done",
            tenant_id=tenant_id,
            provider=result.provider,
            forced_local=force_local,
            citations=len(citations),
            grounded=grounded,
            query_scrubbed=scrub(req.query)[:120],
        )

        return OrchestrateResponse(
            answer=answer,
            citations=citations,
            provider=result.provider,
            model=result.model,
            forced_local=force_local,
            attempts=result.attempts,
            guardrails_applied=applied,
            insufficient_information=False,
            metadata={"chunk_count": len(chunks), "grounded": grounded},
        )


async def extract_requirements(
    text: str, *, tenant_id: str, filename: str | None = None
) -> ExtractRequirementsResponse:
    os.environ.setdefault("LLM_ROUTER_MODE", os.environ.get("LLM_ROUTER_MODE", "fake"))
    messages = [
        {
            "role": "system",
            "content": (
                "Extract structured requirements as JSON with keys: "
                "skills (list), tech_stack (list), domain (string|null), "
                "timeline (string|null). Return JSON only."
            ),
        },
        {
            "role": "user",
            "content": f"Filename: {filename or 'unknown'}\n\nDocument:\n{text[:20000]}",
        },
    ]
    result = await generate(messages, tenant_id=tenant_id, force_local=False, stream=False)
    assert isinstance(result, GenerateResult)
    # Fake mode: synthesize structured JSON
    if result.provider.startswith("fake") or result.model == "fake-model":
        reqs = {
            "skills": ["python", "fastapi"] if "python" in text.lower() else [],
            "tech_stack": ["postgres", "qdrant"] if "qdrant" in text.lower() else [],
            "domain": "healthcare" if "health" in text.lower() else None,
            "timeline": "Q4" if "q4" in text.lower() else None,
        }
    else:
        reqs = parse_requirements_json(result.content)
    return ExtractRequirementsResponse(
        requirements=reqs, provider=result.provider, model=result.model
    )
