"""Orchestration HTTP endpoints."""

from __future__ import annotations

import json
import os
from typing import Annotated, AsyncIterator

from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from app.application import orchestrator as orch
from app.application.prompting import (
    apply_guardrails,
    assemble_messages,
    build_citations,
    is_meta_or_greeting,
    requires_local_only,
)
from app.infrastructure import clients
from rag_platform_auth_middleware import require_role
from rag_platform_llm_router import generate
from rag_platform_observability import get_logger
from rag_platform_schemas.auth import JWTClaims, UserRole
from rag_platform_schemas.orchestration import (
    ExtractRequirementsRequest,
    ExtractRequirementsResponse,
    OrchestrateRequest,
    OrchestrateResponse,
)

router = APIRouter()
logger = get_logger(__name__)

CallerClaims = Annotated[JWTClaims, Depends(require_role(UserRole.END_USER))]


def _bearer_token(request: Request) -> str:
    auth = request.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return ""


@router.post(
    "/generate",
    response_model=OrchestrateResponse,
    summary="Assemble prompt, call LLM router, apply guardrails",
)
async def generate_answer(
    req: OrchestrateRequest,
    claims: CallerClaims,
    request: Request,
) -> OrchestrateResponse:
    return await orch.orchestrate(
        req, tenant_id=str(claims.tenant_id), token=_bearer_token(request)
    )


@router.post(
    "/stream",
    summary="Same as /generate but streamed via SSE",
)
async def stream_answer(
    req: OrchestrateRequest,
    claims: CallerClaims,
    request: Request,
) -> EventSourceResponse:
    tenant_id = str(claims.tenant_id)
    token = _bearer_token(request)

    async def event_gen() -> AsyncIterator[dict]:
        os.environ.setdefault(
            "LLM_ROUTER_MODE", os.environ.get("LLM_ROUTER_MODE", "fake")
        )

        if req.chunks is not None:
            chunks = list(req.chunks)
            insufficient = len(chunks) == 0
        elif is_meta_or_greeting(req.query):
            # Greeting/capability question — skip the retrieval round-trip
            # entirely rather than running it and discarding the result.
            chunks, insufficient = [], False
        else:
            yield {"event": "status", "data": json.dumps({"status": "searching your documents"})}
            raw_chunks, insufficient = await clients.fetch_retrieved_chunks(
                query=req.query, token=token, doc_type=req.doc_type
            )
            chunks = orch._as_chunks(raw_chunks)

        if (insufficient or not chunks) and not is_meta_or_greeting(req.query):
            payload = OrchestrateResponse(
                answer=(
                    "I don't have enough relevant information in the knowledge "
                    "base to answer that."
                ),
                citations=[],
                provider="none",
                model="none",
                forced_local=False,
                attempts=[],
                guardrails_applied=[],
                insufficient_information=True,
                metadata={"reason": "retrieval_insufficient"},
            )
            yield {"event": "final", "data": payload.model_dump_json()}
            return
        if insufficient or not chunks:
            # Greeting/capability question with no matching context — let the
            # LLM respond conversationally instead of forcing a refusal.
            chunks = []

        system_prompt = (
            req.system_prompt_override
            if req.system_prompt_override is not None
            else await clients.fetch_active_prompt(tenant_id, token)
        )
        policy = await clients.fetch_active_guardrails(tenant_id, token)
        force_local = requires_local_only(chunks)
        messages = assemble_messages(
            query=req.query,
            chunks=chunks,
            system_prompt=system_prompt,
            chat_history=req.chat_history,
        )

        yield {"event": "status", "data": json.dumps({"status": "thinking"})}
        stream = await generate(
            messages, tenant_id=tenant_id, force_local=force_local, stream=True
        )
        parts: list[str] = []
        async for token_text in stream:  # type: ignore[union-attr]
            parts.append(token_text)
            yield {"event": "token", "data": json.dumps({"token": token_text})}

        raw_answer = "".join(parts)
        answer, applied = apply_guardrails(raw_answer, policy, query=req.query)
        citations = build_citations(chunks)

        grounded, ungrounded_reason = await orch.run_faithfulness_check(
            answer=raw_answer,
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
            logger.warning("answer_not_grounded", tenant_id=tenant_id, reason=ungrounded_reason)

        final = OrchestrateResponse(
            answer=answer,
            citations=citations,
            provider="ollama" if force_local else "stream",
            model="stream",
            forced_local=force_local,
            attempts=[],
            guardrails_applied=applied,
            insufficient_information=False,
            metadata={"chunk_count": len(chunks), "grounded": grounded},
        )
        yield {"event": "final", "data": final.model_dump_json()}

    return EventSourceResponse(event_gen())


@router.post(
    "/extract-requirements",
    response_model=ExtractRequirementsResponse,
    summary="Layer 6 — extract structured requirements from tender/spec text",
)
async def extract_requirements(
    req: ExtractRequirementsRequest, claims: CallerClaims
) -> ExtractRequirementsResponse:
    return await orch.extract_requirements(
        req.text, tenant_id=str(claims.tenant_id), filename=req.filename
    )
