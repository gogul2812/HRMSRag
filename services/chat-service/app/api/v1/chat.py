"""Chat HTTP endpoints — sessions, message, SSE stream, feedback."""

from __future__ import annotations

import json
import uuid
from typing import Annotated, AsyncIterator

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.application import chat_service as svc
from app.infrastructure import database as db_mod
from app.infrastructure import orchestrator_client as orch
from app.infrastructure.database import get_db_session
from rag_platform_auth_middleware import require_role
from rag_platform_observability import get_logger
from rag_platform_schemas.auth import JWTClaims, UserRole
from rag_platform_schemas.chat import (
    ChatMessageCreate,
    ChatMessageResponse,
    ChatSession,
    ChatSessionCreate,
    ChatSessionDetail,
    Feedback,
    FeedbackCreate,
)

router = APIRouter()
logger = get_logger(__name__)

CallerClaims = Annotated[JWTClaims, Depends(require_role(UserRole.END_USER))]
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


def _bearer_token(request: Request) -> str:
    auth = request.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return ""


def _ids(claims: JWTClaims) -> tuple[uuid.UUID, uuid.UUID]:
    return uuid.UUID(claims.tenant_id), uuid.UUID(claims.sub)


@router.post("/sessions", response_model=ChatSession, status_code=201)
async def create_session(
    body: ChatSessionCreate, claims: CallerClaims, db: DbSession
) -> ChatSession:
    tenant_id, user_id = _ids(claims)
    return await svc.create_session(db, tenant_id=tenant_id, user_id=user_id, body=body)


@router.get("/sessions", response_model=list[ChatSession])
async def list_sessions(claims: CallerClaims, db: DbSession) -> list[ChatSession]:
    tenant_id, user_id = _ids(claims)
    return await svc.list_sessions(db, tenant_id=tenant_id, user_id=user_id)


@router.get("/sessions/{session_id}", response_model=ChatSessionDetail)
async def get_session(
    session_id: uuid.UUID, claims: CallerClaims, db: DbSession
) -> ChatSessionDetail:
    tenant_id, user_id = _ids(claims)
    return await svc.get_session_detail(
        db, session_id=session_id, tenant_id=tenant_id, user_id=user_id
    )


@router.delete("/sessions/{session_id}", status_code=204, response_class=Response)
async def delete_session(
    session_id: uuid.UUID, claims: CallerClaims, db: DbSession
) -> Response:
    tenant_id, user_id = _ids(claims)
    await svc.soft_delete_session(
        db, session_id=session_id, tenant_id=tenant_id, user_id=user_id
    )
    return Response(status_code=204)


@router.post(
    "/sessions/{session_id}/message",
    response_model=ChatMessageResponse,
    summary="Send a message (non-streaming)",
)
async def send_message(
    session_id: uuid.UUID,
    body: ChatMessageCreate,
    claims: CallerClaims,
    db: DbSession,
    request: Request,
) -> ChatMessageResponse:
    tenant_id, user_id = _ids(claims)
    return await svc.send_message(
        db,
        session_id=session_id,
        tenant_id=tenant_id,
        user_id=user_id,
        body=body,
        token=_bearer_token(request),
    )


@router.post(
    "/sessions/{session_id}/stream",
    summary="Send a message and stream the answer via SSE",
)
async def stream_message(
    session_id: uuid.UUID,
    body: ChatMessageCreate,
    claims: CallerClaims,
    db: DbSession,
    request: Request,
) -> EventSourceResponse:
    tenant_id, user_id = _ids(claims)
    token = _bearer_token(request)

    # Validate ownership before opening the stream
    await svc.get_session_detail(
        db, session_id=session_id, tenant_id=tenant_id, user_id=user_id
    )
    history = await svc._history_for_orchestrator(db, session_id)

    async def event_gen() -> AsyncIterator[dict]:
        final_payload: dict | None = None
        token_count = 0
        async for evt in orch.orchestrate_stream(
            query=body.content,
            token=token,
            chat_history=history,
            doc_type=body.doc_type,
        ):
            event_name = evt.get("event") or "message"
            data = evt.get("data")
            if event_name == "token":
                token_count += 1
                # data may be {"token": "..."} or already a string
                if isinstance(data, dict):
                    yield {"event": "token", "data": json.dumps(data)}
                else:
                    yield {"event": "token", "data": json.dumps({"token": data})}
            elif event_name == "final":
                final_payload = data if isinstance(data, dict) else {"answer": str(data)}
            else:
                yield {
                    "event": event_name,
                    "data": json.dumps(data) if not isinstance(data, str) else data,
                }

        answer = (final_payload or {}).get("answer") or ""
        citations = (final_payload or {}).get("citations") or []
        # Fresh session — request-scoped db may already be closed when SSE finishes
        async with db_mod.async_session_maker() as stream_db:
            from rag_platform_auth_middleware import set_tenant_guc

            await set_tenant_guc(stream_db, tenant_id)
            user_msg, assistant_msg = await svc.persist_streamed_turn(
                stream_db,
                session_id=session_id,
                tenant_id=tenant_id,
                user_id=user_id,
                user_content=body.content,
                assistant_content=answer,
                citations=citations,
            )
        logger.info(
            "chat_stream_done",
            tenant_id=str(tenant_id),
            session_id=str(session_id),
            tokens=token_count,
        )
        yield {
            "event": "final",
            "data": json.dumps(
                {
                    "answer": answer,
                    "citations": citations,
                    "user_message_id": str(user_msg.id),
                    "assistant_message_id": str(assistant_msg.id),
                    "token_count": token_count,
                    "provider": (final_payload or {}).get("provider"),
                    "model": (final_payload or {}).get("model"),
                }
            ),
        }

    return EventSourceResponse(event_gen())


@router.post(
    "/messages/{message_id}/feedback",
    response_model=Feedback,
    status_code=201,
)
async def post_feedback(
    message_id: uuid.UUID,
    body: FeedbackCreate,
    claims: CallerClaims,
    db: DbSession,
) -> Feedback:
    tenant_id, user_id = _ids(claims)
    return await svc.submit_feedback(
        db,
        message_id=message_id,
        tenant_id=tenant_id,
        user_id=user_id,
        body=body,
    )
