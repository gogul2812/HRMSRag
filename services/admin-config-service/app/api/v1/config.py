import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application import config_service
from app.infrastructure.database import get_db_session
from rag_platform_auth_middleware import require_role
from rag_platform_observability import get_logger
from rag_platform_schemas.auth import JWTClaims, UserRole
from rag_platform_schemas.config import (
    GuardrailPolicy,
    GuardrailPolicyCreate,
    PromptConfig,
    PromptConfigCreate,
)

router = APIRouter()
logger = get_logger(__name__)

AdminClaims = Annotated[JWTClaims, Depends(require_role(UserRole.ADMIN))]
# Read-only "active config" lookups are called by the orchestrator on behalf of any
# chatting end user, not just admins — gate those with END_USER instead of ADMIN.
EndUserClaims = Annotated[JWTClaims, Depends(require_role(UserRole.END_USER))]
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


def _tenant_uuid(claims: JWTClaims) -> uuid.UUID:
    return uuid.UUID(str(claims.tenant_id))


# ---------------------------------------------------------------------------
# Prompt configs
# ---------------------------------------------------------------------------


@router.get(
    "/prompt",
    response_model=PromptConfig,
    summary="Get the active prompt config for the caller's tenant",
)
async def get_active_prompt(claims: EndUserClaims, db: DbSession) -> PromptConfig:
    tenant_id = _tenant_uuid(claims)
    row = await config_service.get_active_prompt_config(db, tenant_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active prompt config for this tenant",
        )
    logger.info("prompt_active_fetched", tenant_id=str(tenant_id), config_id=str(row.id))
    return row


@router.post(
    "/prompt",
    response_model=PromptConfig,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new prompt config version",
)
async def create_prompt(
    req: PromptConfigCreate, claims: AdminClaims, db: DbSession
) -> PromptConfig:
    tenant_id = _tenant_uuid(claims)
    row = await config_service.create_prompt_config(db, tenant_id, req)
    logger.info(
        "prompt_version_created",
        tenant_id=str(tenant_id),
        config_id=str(row.id),
        version=row.version,
    )
    return row


@router.get(
    "/prompt/versions",
    response_model=list[PromptConfig],
    summary="List all prompt config versions for the caller's tenant",
)
async def list_prompt_versions(claims: AdminClaims, db: DbSession) -> list[PromptConfig]:
    tenant_id = _tenant_uuid(claims)
    rows = await config_service.list_prompt_configs(db, tenant_id)
    logger.info("prompt_versions_listed", tenant_id=str(tenant_id), count=len(rows))
    return rows


@router.get(
    "/prompt/{config_id}",
    response_model=PromptConfig,
    summary="Get a prompt config by id (tenant-scoped)",
)
async def get_prompt_by_id(
    config_id: uuid.UUID, claims: AdminClaims, db: DbSession
) -> PromptConfig:
    tenant_id = _tenant_uuid(claims)
    row = await config_service.get_prompt_config_by_id(db, tenant_id, config_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt config not found",
        )
    return row


@router.put(
    "/prompt/{config_id}/activate",
    response_model=PromptConfig,
    summary="Activate a prompt config version (deactivates others for the tenant)",
)
async def activate_prompt(
    config_id: uuid.UUID, claims: AdminClaims, db: DbSession
) -> PromptConfig:
    tenant_id = _tenant_uuid(claims)
    row = await config_service.activate_prompt_config(db, tenant_id, config_id)
    logger.info(
        "prompt_version_activated",
        tenant_id=str(tenant_id),
        config_id=str(row.id),
        version=row.version,
    )
    return row


# ---------------------------------------------------------------------------
# Guardrail policies
# ---------------------------------------------------------------------------


@router.get(
    "/guardrails",
    response_model=GuardrailPolicy,
    summary="Get the active guardrail policy for the caller's tenant",
)
async def get_active_guardrails(claims: EndUserClaims, db: DbSession) -> GuardrailPolicy:
    tenant_id = _tenant_uuid(claims)
    row = await config_service.get_active_guardrail_policy(db, tenant_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active guardrail policy for this tenant",
        )
    logger.info("guardrail_active_fetched", tenant_id=str(tenant_id), policy_id=str(row.id))
    return row


@router.post(
    "/guardrails",
    response_model=GuardrailPolicy,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new guardrail policy version",
)
async def create_guardrails(
    req: GuardrailPolicyCreate, claims: AdminClaims, db: DbSession
) -> GuardrailPolicy:
    tenant_id = _tenant_uuid(claims)
    row = await config_service.create_guardrail_policy(db, tenant_id, req)
    logger.info(
        "guardrail_version_created",
        tenant_id=str(tenant_id),
        policy_id=str(row.id),
        version=row.version,
    )
    return row


@router.get(
    "/guardrails/versions",
    response_model=list[GuardrailPolicy],
    summary="List all guardrail policy versions for the caller's tenant",
)
async def list_guardrail_versions(
    claims: AdminClaims, db: DbSession
) -> list[GuardrailPolicy]:
    tenant_id = _tenant_uuid(claims)
    rows = await config_service.list_guardrail_policies(db, tenant_id)
    logger.info("guardrail_versions_listed", tenant_id=str(tenant_id), count=len(rows))
    return rows


@router.get(
    "/guardrails/{policy_id}",
    response_model=GuardrailPolicy,
    summary="Get a guardrail policy by id (tenant-scoped)",
)
async def get_guardrail_by_id(
    policy_id: uuid.UUID, claims: AdminClaims, db: DbSession
) -> GuardrailPolicy:
    tenant_id = _tenant_uuid(claims)
    row = await config_service.get_guardrail_policy_by_id(db, tenant_id, policy_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Guardrail policy not found",
        )
    return row


@router.put(
    "/guardrails/{policy_id}/activate",
    response_model=GuardrailPolicy,
    summary="Activate a guardrail policy version (deactivates others for the tenant)",
)
async def activate_guardrails(
    policy_id: uuid.UUID, claims: AdminClaims, db: DbSession
) -> GuardrailPolicy:
    tenant_id = _tenant_uuid(claims)
    row = await config_service.activate_guardrail_policy(db, tenant_id, policy_id)
    logger.info(
        "guardrail_version_activated",
        tenant_id=str(tenant_id),
        policy_id=str(row.id),
        version=row.version,
    )
    return row
