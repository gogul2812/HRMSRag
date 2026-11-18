"""
Admin-config domain Pydantic models.

Canonical shapes for prompt_configs and guardrail_policies.
No service may define its own copy of these.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Prompt configs
# ---------------------------------------------------------------------------


class PromptConfigCreate(BaseModel):
    """Request body for creating a new prompt/rules version."""

    text: Annotated[str, Field(min_length=1)]

    model_config = ConfigDict(str_strip_whitespace=True)


class PromptConfig(BaseModel):
    """A prompt_configs row as returned by the API."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    version: int
    text: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Guardrail policies
# ---------------------------------------------------------------------------


class GuardrailPolicyCreate(BaseModel):
    """Request body for creating a new guardrail policy version."""

    policy_json: dict[str, Any]

    model_config = ConfigDict(str_strip_whitespace=True)


class GuardrailPolicy(BaseModel):
    """A guardrail_policies row as returned by the API."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    version: int
    policy_json: dict[str, Any]
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
