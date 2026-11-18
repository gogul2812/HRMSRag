"""Chat session / message use-cases."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.models import ChatMessageDB, ChatSessionDB, FeedbackDB
from app.infrastructure import orchestrator_client as orch
from rag_platform_observability import get_logger
from rag_platform_schemas.chat import (
    ChatMessage,
    ChatMessageCreate,
    ChatMessageResponse,
    ChatSession,
    ChatSessionCreate,
    ChatSessionDetail,
    Feedback,
    FeedbackCreate,
)

logger = get_logger(__name__)


def _msg_to_schema(row: ChatMessageDB) -> ChatMessage:
    return ChatMessage(
        id=row.id,
        session_id=row.session_id,
        tenant_id=row.tenant_id,
        role=row.role,  # type: ignore[arg-type]
        content=row.content,
        citations=list(row.citations_json or []),
        created_at=row.created_at,
    )


def _session_to_schema(row: ChatSessionDB) -> ChatSession:
    return ChatSession(
        id=row.id,
        tenant_id=row.tenant_id,
        user_id=row.user_id,
        title=row.title,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def create_session(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    body: ChatSessionCreate,
) -> ChatSession:
    row = ChatSessionDB(
        tenant_id=tenant_id,
        user_id=user_id,
        title=body.title,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _session_to_schema(row)


async def list_sessions(
    db: AsyncSession, *, tenant_id: uuid.UUID, user_id: uuid.UUID
) -> list[ChatSession]:
    q = (
        select(ChatSessionDB)
        .where(
            ChatSessionDB.tenant_id == tenant_id,
            ChatSessionDB.user_id == user_id,
            ChatSessionDB.deleted_at.is_(None),
        )
        .order_by(ChatSessionDB.updated_at.desc())
    )
    rows = (await db.execute(q)).scalars().all()
    return [_session_to_schema(r) for r in rows]


async def get_session_detail(
    db: AsyncSession,
    *,
    session_id: uuid.UUID,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> ChatSessionDetail:
    row = await _get_owned_session(db, session_id=session_id, tenant_id=tenant_id, user_id=user_id)
    messages = [
        _msg_to_schema(m)
        for m in sorted(row.messages, key=lambda m: m.created_at)
    ]
    base = _session_to_schema(row)
    return ChatSessionDetail(**base.model_dump(), messages=messages)


async def soft_delete_session(
    db: AsyncSession,
    *,
    session_id: uuid.UUID,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    row = await _get_owned_session(db, session_id=session_id, tenant_id=tenant_id, user_id=user_id)
    row.deleted_at = datetime.now(timezone.utc)
    await db.commit()


async def _get_owned_session(
    db: AsyncSession,
    *,
    session_id: uuid.UUID,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> ChatSessionDB:
    q = (
        select(ChatSessionDB)
        .options(selectinload(ChatSessionDB.messages))
        .where(
            ChatSessionDB.id == session_id,
            ChatSessionDB.tenant_id == tenant_id,
            ChatSessionDB.user_id == user_id,
            ChatSessionDB.deleted_at.is_(None),
        )
    )
    row = (await db.execute(q)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return row


async def _history_for_orchestrator(db: AsyncSession, session_id: uuid.UUID) -> list[dict[str, str]]:
    q = (
        select(ChatMessageDB)
        .where(ChatMessageDB.session_id == session_id)
        .order_by(ChatMessageDB.created_at.asc())
    )
    rows = (await db.execute(q)).scalars().all()
    return [{"role": r.role, "content": r.content} for r in rows if r.role in {"user", "assistant"}]


async def send_message(
    db: AsyncSession,
    *,
    session_id: uuid.UUID,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    body: ChatMessageCreate,
    token: str,
) -> ChatMessageResponse:
    session = await _get_owned_session(
        db, session_id=session_id, tenant_id=tenant_id, user_id=user_id
    )
    history = await _history_for_orchestrator(db, session_id)

    user_msg = ChatMessageDB(
        session_id=session.id,
        tenant_id=tenant_id,
        role="user",
        content=body.content,
        citations_json=None,
    )
    db.add(user_msg)
    await db.flush()

    result = await orch.orchestrate_generate(
        query=body.content,
        token=token,
        chat_history=history,
        doc_type=body.doc_type,
    )

    citations = result.get("citations") or []
    assistant_msg = ChatMessageDB(
        session_id=session.id,
        tenant_id=tenant_id,
        role="assistant",
        content=result.get("answer") or "",
        citations_json=citations,
    )
    db.add(assistant_msg)
    session.updated_at = datetime.now(timezone.utc)
    if not session.title:
        session.title = body.content[:80]
    await db.commit()
    await db.refresh(user_msg)
    await db.refresh(assistant_msg)

    logger.info(
        "chat_message_sent",
        tenant_id=str(tenant_id),
        session_id=str(session_id),
        provider=result.get("provider"),
    )

    return ChatMessageResponse(
        user_message=_msg_to_schema(user_msg),
        assistant_message=_msg_to_schema(assistant_msg),
        provider=result.get("provider"),
        model=result.get("model"),
        forced_local=bool(result.get("forced_local")),
        insufficient_information=bool(result.get("insufficient_information")),
    )


async def persist_streamed_turn(
    db: AsyncSession,
    *,
    session_id: uuid.UUID,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    user_content: str,
    assistant_content: str,
    citations: list[dict],
) -> tuple[ChatMessage, ChatMessage]:
    session = await _get_owned_session(
        db, session_id=session_id, tenant_id=tenant_id, user_id=user_id
    )
    user_msg = ChatMessageDB(
        session_id=session.id,
        tenant_id=tenant_id,
        role="user",
        content=user_content,
    )
    assistant_msg = ChatMessageDB(
        session_id=session.id,
        tenant_id=tenant_id,
        role="assistant",
        content=assistant_content,
        citations_json=citations,
    )
    db.add(user_msg)
    db.add(assistant_msg)
    session.updated_at = datetime.now(timezone.utc)
    if not session.title:
        session.title = user_content[:80]
    await db.commit()
    await db.refresh(user_msg)
    await db.refresh(assistant_msg)
    return _msg_to_schema(user_msg), _msg_to_schema(assistant_msg)


async def submit_feedback(
    db: AsyncSession,
    *,
    message_id: uuid.UUID,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    body: FeedbackCreate,
) -> Feedback:
    msg_q = select(ChatMessageDB).where(
        ChatMessageDB.id == message_id,
        ChatMessageDB.tenant_id == tenant_id,
    )
    msg = (await db.execute(msg_q)).scalar_one_or_none()
    if msg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    # Ensure the message belongs to a session owned by this user
    await _get_owned_session(
        db, session_id=msg.session_id, tenant_id=tenant_id, user_id=user_id
    )

    existing_q = select(FeedbackDB).where(
        FeedbackDB.message_id == message_id,
        FeedbackDB.user_id == user_id,
    )
    existing = (await db.execute(existing_q)).scalar_one_or_none()
    if existing:
        existing.rating = body.rating
        await db.commit()
        await db.refresh(existing)
        row = existing
    else:
        row = FeedbackDB(
            message_id=message_id,
            tenant_id=tenant_id,
            user_id=user_id,
            rating=body.rating,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)

    return Feedback(
        id=row.id,
        message_id=row.message_id,
        tenant_id=row.tenant_id,
        user_id=row.user_id,
        rating=row.rating,  # type: ignore[arg-type]
        created_at=row.created_at,
    )
