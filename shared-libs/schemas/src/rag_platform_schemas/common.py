"""
Common / cross-domain Pydantic models.

Reused by every service for health checks, error responses, and pagination.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """A single error item (may be one of many in a validation failure)."""

    field: str | None = None  # None for non-field errors
    message: str


class ErrorResponse(BaseModel):
    """Standard error envelope returned by every service on 4xx / 5xx."""

    error: str  # machine-readable code, e.g. "invalid_credentials"
    message: str  # human-readable summary
    details: list[ErrorDetail] = Field(default_factory=list)
    request_id: str | None = None


class HealthResponse(BaseModel):
    """Shape of GET /health responses."""

    status: str  # "ok" | "degraded" | "down"
    service: str
    version: str = "0.1.0"
    checks: dict[str, str] = Field(default_factory=dict)


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated list wrapper."""

    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int
