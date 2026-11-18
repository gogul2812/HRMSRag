import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import GuardrailPolicyDB, PromptConfigDB
from rag_platform_schemas.config import GuardrailPolicyCreate, PromptConfigCreate


async def _next_prompt_version(db: AsyncSession, tenant_id: uuid.UUID) -> int:
    result = await db.scalar(
        select(func.coalesce(func.max(PromptConfigDB.version), 0)).where(
            PromptConfigDB.tenant_id == tenant_id
        )
    )
    return int(result or 0) + 1


async def _next_guardrail_version(db: AsyncSession, tenant_id: uuid.UUID) -> int:
    result = await db.scalar(
        select(func.coalesce(func.max(GuardrailPolicyDB.version), 0)).where(
            GuardrailPolicyDB.tenant_id == tenant_id
        )
    )
    return int(result or 0) + 1


async def create_prompt_config(
    db: AsyncSession, tenant_id: uuid.UUID, req: PromptConfigCreate
) -> PromptConfigDB:
    version = await _next_prompt_version(db, tenant_id)
    row = PromptConfigDB(
        tenant_id=tenant_id,
        version=version,
        text=req.text,
        is_active=False,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def list_prompt_configs(db: AsyncSession, tenant_id: uuid.UUID) -> list[PromptConfigDB]:
    result = await db.scalars(
        select(PromptConfigDB)
        .where(PromptConfigDB.tenant_id == tenant_id)
        .order_by(PromptConfigDB.version.desc())
    )
    return list(result.all())


async def get_active_prompt_config(
    db: AsyncSession, tenant_id: uuid.UUID
) -> PromptConfigDB | None:
    return await db.scalar(
        select(PromptConfigDB).where(
            PromptConfigDB.tenant_id == tenant_id,
            PromptConfigDB.is_active.is_(True),
        )
    )


async def get_prompt_config_by_id(
    db: AsyncSession, tenant_id: uuid.UUID, config_id: uuid.UUID
) -> PromptConfigDB | None:
    return await db.scalar(
        select(PromptConfigDB).where(
            PromptConfigDB.id == config_id,
            PromptConfigDB.tenant_id == tenant_id,
        )
    )


async def activate_prompt_config(
    db: AsyncSession, tenant_id: uuid.UUID, config_id: uuid.UUID
) -> PromptConfigDB:
    row = await get_prompt_config_by_id(db, tenant_id, config_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt config not found",
        )

    await db.execute(
        update(PromptConfigDB)
        .where(PromptConfigDB.tenant_id == tenant_id, PromptConfigDB.is_active.is_(True))
        .values(is_active=False)
    )
    row.is_active = True
    await db.commit()
    await db.refresh(row)
    return row


async def create_guardrail_policy(
    db: AsyncSession, tenant_id: uuid.UUID, req: GuardrailPolicyCreate
) -> GuardrailPolicyDB:
    version = await _next_guardrail_version(db, tenant_id)
    row = GuardrailPolicyDB(
        tenant_id=tenant_id,
        version=version,
        policy_json=req.policy_json,
        is_active=False,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def list_guardrail_policies(
    db: AsyncSession, tenant_id: uuid.UUID
) -> list[GuardrailPolicyDB]:
    result = await db.scalars(
        select(GuardrailPolicyDB)
        .where(GuardrailPolicyDB.tenant_id == tenant_id)
        .order_by(GuardrailPolicyDB.version.desc())
    )
    return list(result.all())


async def get_active_guardrail_policy(
    db: AsyncSession, tenant_id: uuid.UUID
) -> GuardrailPolicyDB | None:
    return await db.scalar(
        select(GuardrailPolicyDB).where(
            GuardrailPolicyDB.tenant_id == tenant_id,
            GuardrailPolicyDB.is_active.is_(True),
        )
    )


async def get_guardrail_policy_by_id(
    db: AsyncSession, tenant_id: uuid.UUID, policy_id: uuid.UUID
) -> GuardrailPolicyDB | None:
    return await db.scalar(
        select(GuardrailPolicyDB).where(
            GuardrailPolicyDB.id == policy_id,
            GuardrailPolicyDB.tenant_id == tenant_id,
        )
    )


async def activate_guardrail_policy(
    db: AsyncSession, tenant_id: uuid.UUID, policy_id: uuid.UUID
) -> GuardrailPolicyDB:
    row = await get_guardrail_policy_by_id(db, tenant_id, policy_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Guardrail policy not found",
        )

    await db.execute(
        update(GuardrailPolicyDB)
        .where(
            GuardrailPolicyDB.tenant_id == tenant_id,
            GuardrailPolicyDB.is_active.is_(True),
        )
        .values(is_active=False)
    )
    row.is_active = True
    await db.commit()
    await db.refresh(row)
    return row
