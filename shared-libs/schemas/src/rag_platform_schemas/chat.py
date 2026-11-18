"""Chat session / message / feedback schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChatSessionCreate(BaseModel):
    title: Annotated[str | None, Field(default=None, max_length=255)] = None


class ChatSession(BaseModel):
    id: UUID
    tenant_id: UUID
    user_id: UUID
    title: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatMessageCreate(BaseModel):
    content: Annotated[str, Field(min_length=1, max_length=8000)]
    doc_type: str | None = None

    model_config = ConfigDict(str_strip_whitespace=True)


class ChatMessage(BaseModel):
    id: UUID
    session_id: UUID
    tenant_id: UUID
    role: Literal["user", "assistant", "system"]
    content: str
    citations: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatSessionDetail(ChatSession):
    messages: list[ChatMessage] = Field(default_factory=list)


class ChatMessageResponse(BaseModel):
    """Non-streaming send-message response."""

    user_message: ChatMessage
    assistant_message: ChatMessage
    provider: str | None = None
    model: str | None = None
    forced_local: bool = False
    insufficient_information: bool = False


class FeedbackCreate(BaseModel):
    rating: Literal["up", "down"]


class Feedback(BaseModel):
    id: UUID
    message_id: UUID
    tenant_id: UUID
    user_id: UUID
    rating: Literal["up", "down"]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
