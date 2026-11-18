"""Tenant session context for Postgres RLS (SET LOCAL app.current_tenant_id)."""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def set_tenant_guc(session: AsyncSession, tenant_id: uuid.UUID | str | None) -> None:
    """
    Bind the request tenant for the current transaction.

    RLS policies (migration 0005) filter rows by app_current_tenant_id().
    No-op on SQLite (local unit tests).
    """
    if tenant_id is None:
        return
    bind = session.get_bind()
    dialect = getattr(bind, "dialect", None)
    name = getattr(dialect, "name", "") if dialect else ""
    if name == "sqlite":
        return
    tid = str(tenant_id)
    await session.execute(
        text("SELECT set_config('app.current_tenant_id', :tid, true)"),
        {"tid": tid},
    )
