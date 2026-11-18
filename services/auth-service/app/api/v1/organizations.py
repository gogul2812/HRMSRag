"""Organization APIs (backed by tenants table)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application import auth_service
from app.infrastructure.database import get_db_session
from rag_platform_auth_middleware import require_role
from rag_platform_observability import get_logger
from rag_platform_schemas.auth import (
    JWTClaims,
    Organization,
    OrganizationCreateWithAdmin,
    OrganizationPublic,
    OrganizationUpdate,
    OrgUserCreate,
    OrgUserUpdate,
    ResetPasswordRequest,
    SuperAdminBootstrap,
    User,
    UserRole,
)

router = APIRouter()
logger = get_logger(__name__)


def _require_org_id(claims: JWTClaims) -> uuid.UUID:
    org = claims.organization_id or claims.tenant_id
    if not org:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization context required",
        )
    return uuid.UUID(org)


@router.get("/public", response_model=list[OrganizationPublic])
async def public_organizations(db: AsyncSession = Depends(get_db_session)):
    """Active organizations for login/register dropdowns (no auth)."""
    orgs = await auth_service.list_public_organizations(db)
    return [OrganizationPublic(id=o.id, name=o.name) for o in orgs]


@router.post(
    "/bootstrap-super-admin",
    response_model=User,
    status_code=status.HTTP_201_CREATED,
)
async def bootstrap_super_admin(
    req: SuperAdminBootstrap,
    setup_token: Annotated[str, Header(alias="setup-token")],
    db: AsyncSession = Depends(get_db_session),
):
    """One-time Super Admin creation (setup-token)."""
    from app.config import settings

    if setup_token != settings.setup_token:
        raise HTTPException(status_code=403, detail="Invalid setup token")
    user = await auth_service.bootstrap_super_admin(db, req)
    logger.info("super_admin_bootstrapped", user_id=str(user.id))
    return user


# ---- Organization Admin: users within own org (before /{org_id}) -------------

@router.get("/me/users", response_model=list[User])
async def list_my_org_users(
    claims: Annotated[JWTClaims, Depends(require_role(UserRole.ADMIN))],
    db: AsyncSession = Depends(get_db_session),
):
    org_id = _require_org_id(claims)
    return await auth_service.list_org_users(db, org_id)


@router.post("/me/users", response_model=User, status_code=status.HTTP_201_CREATED)
async def create_my_org_user(
    req: OrgUserCreate,
    claims: Annotated[JWTClaims, Depends(require_role(UserRole.ADMIN))],
    db: AsyncSession = Depends(get_db_session),
):
    org_id = _require_org_id(claims)
    return await auth_service.create_org_user(db, org_id, req)


@router.patch("/me/users/{user_id}", response_model=User)
async def update_my_org_user(
    user_id: uuid.UUID,
    req: OrgUserUpdate,
    claims: Annotated[JWTClaims, Depends(require_role(UserRole.ADMIN))],
    db: AsyncSession = Depends(get_db_session),
):
    org_id = _require_org_id(claims)
    return await auth_service.update_org_user(db, org_id, user_id, req)


@router.delete("/me/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_org_user(
    user_id: uuid.UUID,
    claims: Annotated[JWTClaims, Depends(require_role(UserRole.ADMIN))],
    db: AsyncSession = Depends(get_db_session),
):
    org_id = _require_org_id(claims)
    if str(user_id) == claims.sub:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    await auth_service.delete_org_user(db, org_id, user_id)


@router.post("/me/users/{user_id}/reset-password", response_model=User)
async def reset_my_org_user_password(
    user_id: uuid.UUID,
    req: ResetPasswordRequest,
    claims: Annotated[JWTClaims, Depends(require_role(UserRole.ADMIN))],
    db: AsyncSession = Depends(get_db_session),
):
    org_id = _require_org_id(claims)
    return await auth_service.reset_org_user_password(
        db, org_id, user_id, req.new_password
    )


# ---- Super Admin organization CRUD ------------------------------------------

@router.get("", response_model=list[Organization])
async def list_organizations(
    claims: Annotated[JWTClaims, Depends(require_role(UserRole.SUPER_ADMIN))],
    db: AsyncSession = Depends(get_db_session),
):
    return await auth_service.list_organizations(db)


@router.post("", response_model=Organization, status_code=status.HTTP_201_CREATED)
async def create_organization(
    req: OrganizationCreateWithAdmin,
    claims: Annotated[JWTClaims, Depends(require_role(UserRole.SUPER_ADMIN))],
    db: AsyncSession = Depends(get_db_session),
):
    tenant, admin = await auth_service.create_organization_with_admin(
        db, req, created_by=uuid.UUID(claims.sub)
    )
    logger.info(
        "organization_created",
        org_id=str(tenant.id),
        admin_id=str(admin.id),
        by=claims.sub,
    )
    return tenant


@router.get("/{org_id}", response_model=Organization)
async def get_organization(
    org_id: uuid.UUID,
    claims: Annotated[JWTClaims, Depends(require_role(UserRole.SUPER_ADMIN))],
    db: AsyncSession = Depends(get_db_session),
):
    return await auth_service.get_organization(db, org_id)


@router.patch("/{org_id}", response_model=Organization)
async def update_organization(
    org_id: uuid.UUID,
    req: OrganizationUpdate,
    claims: Annotated[JWTClaims, Depends(require_role(UserRole.SUPER_ADMIN))],
    db: AsyncSession = Depends(get_db_session),
):
    return await auth_service.update_organization(db, org_id, req)


@router.post("/{org_id}/disable", response_model=Organization)
async def disable_organization(
    org_id: uuid.UUID,
    claims: Annotated[JWTClaims, Depends(require_role(UserRole.SUPER_ADMIN))],
    db: AsyncSession = Depends(get_db_session),
):
    return await auth_service.update_organization(
        db, org_id, OrganizationUpdate(is_active=False)
    )


# ---- Super Admin: manage users inside any organization ----------------------

@router.get("/{org_id}/users", response_model=list[User])
async def list_organization_users(
    org_id: uuid.UUID,
    claims: Annotated[JWTClaims, Depends(require_role(UserRole.SUPER_ADMIN))],
    db: AsyncSession = Depends(get_db_session),
):
    await auth_service.get_organization(db, org_id)
    return await auth_service.list_org_users(db, org_id)


@router.post(
    "/{org_id}/users",
    response_model=User,
    status_code=status.HTTP_201_CREATED,
)
async def create_organization_user(
    org_id: uuid.UUID,
    req: OrgUserCreate,
    claims: Annotated[JWTClaims, Depends(require_role(UserRole.SUPER_ADMIN))],
    db: AsyncSession = Depends(get_db_session),
):
    await auth_service.get_organization(db, org_id)
    return await auth_service.create_org_user(db, org_id, req)


@router.patch("/{org_id}/users/{user_id}", response_model=User)
async def update_organization_user(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    req: OrgUserUpdate,
    claims: Annotated[JWTClaims, Depends(require_role(UserRole.SUPER_ADMIN))],
    db: AsyncSession = Depends(get_db_session),
):
    await auth_service.get_organization(db, org_id)
    return await auth_service.update_org_user(db, org_id, user_id, req)


@router.post("/{org_id}/users/{user_id}/disable", response_model=User)
async def disable_organization_user(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    claims: Annotated[JWTClaims, Depends(require_role(UserRole.SUPER_ADMIN))],
    db: AsyncSession = Depends(get_db_session),
):
    await auth_service.get_organization(db, org_id)
    return await auth_service.update_org_user(
        db, org_id, user_id, OrgUserUpdate(is_active=False)
    )


@router.post("/{org_id}/users/{user_id}/enable", response_model=User)
async def enable_organization_user(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    claims: Annotated[JWTClaims, Depends(require_role(UserRole.SUPER_ADMIN))],
    db: AsyncSession = Depends(get_db_session),
):
    await auth_service.get_organization(db, org_id)
    return await auth_service.update_org_user(
        db, org_id, user_id, OrgUserUpdate(is_active=True)
    )


@router.delete("/{org_id}/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organization_user(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    claims: Annotated[JWTClaims, Depends(require_role(UserRole.SUPER_ADMIN))],
    db: AsyncSession = Depends(get_db_session),
):
    await auth_service.get_organization(db, org_id)
    await auth_service.delete_org_user(db, org_id, user_id)


@router.post("/{org_id}/users/{user_id}/reset-password", response_model=User)
async def reset_organization_user_password(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    req: ResetPasswordRequest,
    claims: Annotated[JWTClaims, Depends(require_role(UserRole.SUPER_ADMIN))],
    db: AsyncSession = Depends(get_db_session),
):
    await auth_service.get_organization(db, org_id)
    return await auth_service.reset_org_user_password(
        db, org_id, user_id, req.new_password
    )
