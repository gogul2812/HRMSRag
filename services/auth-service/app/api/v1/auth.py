import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis

from app.application import auth_service, token_service
from app.domain.models import UserDB
from app.infrastructure.database import get_db_session
from app.infrastructure.redis_client import get_redis
from rag_platform_auth_middleware import get_current_user
from rag_platform_schemas.auth import (
    ChangePasswordRequest,
    JWTClaims,
    LoginRequest,
    ProfileUpdate,
    RegisterRequest,
    TokenResponse,
    User,
    UserRole,
)
from rag_platform_observability import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
async def register(
    req: RegisterRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Register a new end user inside an organization."""
    req.role = UserRole.END_USER
    user = await auth_service.register_user(db, req)
    logger.info(
        "user_registered",
        user_id=str(user.id),
        organization_id=str(user.tenant_id),
        role=user.role,
    )
    return user


@router.post("/register-admin", response_model=User, status_code=status.HTTP_201_CREATED)
async def register_admin(
    req: RegisterRequest,
    setup_token: str | None = Header(None, alias="setup-token"),
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Register an Organization Admin.

    Allowed via setup-token, Super Admin JWT, or existing admin JWT for the same org.
    Prefer Super Admin create-organization flow for new orgs.
    """
    from app.config import settings
    from jose import jwt, JWTError

    org_id = req.organization_id
    is_authorized = False

    if setup_token and setup_token == settings.setup_token:
        is_authorized = True
    elif authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        try:
            payload = jwt.decode(
                token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
            )
            role = payload.get("role")
            token_org = payload.get("organization_id") or payload.get("tenant_id") or ""
            if role == "super_admin":
                is_authorized = True
            elif role == "admin" and str(token_org) == str(org_id):
                is_authorized = True
        except JWTError:
            pass

    if not is_authorized:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create admin users",
        )

    req.role = UserRole.ADMIN
    user = await auth_service.register_user(db, req)
    logger.info(
        "admin_registered",
        user_id=str(user.id),
        organization_id=str(user.tenant_id),
    )
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    req: LoginRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Authenticate by organization + email (or Super Admin without organization)."""
    tokens = await auth_service.login_user(db, req)
    logger.info(
        "user_logged_in",
        email=req.email,
        organization_id=str(req.organization_id) if req.organization_id else None,
    )
    return tokens


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    authorization: Annotated[str, Header()],
    redis_client: redis.Redis = Depends(get_redis),
):
    """Revoke current token by adding to deny-list."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=400, detail="Invalid authorization header")

    token = authorization.split(" ")[1]
    await token_service.revoke_token(token, redis_client)
    logger.info("user_logged_out")


@router.get("/me", response_model=User)
async def get_me(
    claims: JWTClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Whoami endpoint."""
    user = await db.scalar(select(UserDB).where(UserDB.id == uuid.UUID(claims.sub)))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/me", response_model=User)
async def update_me(
    body: ProfileUpdate,
    claims: JWTClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Update own profile (personal + professional details)."""
    data = body.model_dump(exclude_unset=True)
    user = await auth_service.update_own_profile(
        db,
        uuid.UUID(claims.sub),
        name=data.get("name"),
        phone=data.get("phone"),
        job_title=data.get("job_title"),
        department=data.get("department"),
        location=data.get("location"),
        fields_set=set(data.keys()),
    )
    logger.info("profile_updated", user_id=str(user.id))
    return user


@router.post("/me/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: ChangePasswordRequest,
    claims: JWTClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Change own password (requires current password)."""
    await auth_service.change_own_password(
        db,
        uuid.UUID(claims.sub),
        current_password=body.current_password,
        new_password=body.new_password,
    )
    logger.info("password_changed", user_id=claims.sub)
