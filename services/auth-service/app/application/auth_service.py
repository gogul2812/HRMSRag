import re
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from passlib.context import CryptContext
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import UserDB, TenantDB
from app.application import token_service
from rag_platform_auth_middleware import set_tenant_guc
from rag_platform_schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserRole,
    OrganizationCreateWithAdmin,
    OrganizationUpdate,
    OrgUserCreate,
    OrgUserUpdate,
    SuperAdminBootstrap,
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def _slugify_domain(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "org"
    return f"{base}-{uuid.uuid4().hex[:8]}"


async def register_user(db: AsyncSession, req: RegisterRequest) -> UserDB:
    org_id = req.organization_id
    await set_tenant_guc(db, org_id)

    tenant = await db.scalar(select(TenantDB).where(TenantDB.id == org_id))
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    if not tenant.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Organization is disabled")

    existing_user = await db.scalar(
        select(UserDB).where(UserDB.email == req.email, UserDB.tenant_id == org_id)
    )
    if existing_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")

    new_user = UserDB(
        tenant_id=org_id,
        email=req.email,
        full_name=req.name,
        password_hash=get_password_hash(req.password),
        role=req.role.value,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


async def login_user(db: AsyncSession, req: LoginRequest) -> TokenResponse:
    org_id = req.organization_id

    if org_id is None:
        # Platform Super Admin login (no organization)
        user = await db.scalar(
            select(UserDB).where(
                UserDB.email == req.email,
                UserDB.tenant_id.is_(None),
                UserDB.role == UserRole.SUPER_ADMIN.value,
            )
        )
    else:
        await set_tenant_guc(db, org_id)
        tenant = await db.scalar(select(TenantDB).where(TenantDB.id == org_id))
        if not tenant or not tenant.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user = await db.scalar(
            select(UserDB).where(UserDB.email == req.email, UserDB.tenant_id == org_id)
        )

    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")

    tenant_claim = str(user.tenant_id) if user.tenant_id else ""
    access_token = token_service.create_access_token(str(user.id), tenant_claim, user.role)
    refresh_token = token_service.create_refresh_token(str(user.id), tenant_claim, user.role)

    from app.config import settings

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


async def bootstrap_super_admin(db: AsyncSession, req: SuperAdminBootstrap) -> UserDB:
    existing = await db.scalar(
        select(UserDB).where(UserDB.role == UserRole.SUPER_ADMIN.value, UserDB.tenant_id.is_(None))
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Super Admin already exists",
        )
    email_taken = await db.scalar(select(UserDB).where(UserDB.email == req.email))
    if email_taken:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")

    user = UserDB(
        tenant_id=None,
        email=req.email,
        full_name=req.name,
        password_hash=get_password_hash(req.password),
        role=UserRole.SUPER_ADMIN.value,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def list_public_organizations(db: AsyncSession) -> list[TenantDB]:
    result = await db.scalars(
        select(TenantDB).where(TenantDB.is_active.is_(True)).order_by(TenantDB.name)
    )
    return list(result.all())


async def list_organizations(db: AsyncSession) -> list[TenantDB]:
    result = await db.scalars(select(TenantDB).order_by(TenantDB.name))
    return list(result.all())


async def get_organization(db: AsyncSession, org_id: uuid.UUID) -> TenantDB:
    tenant = await db.scalar(select(TenantDB).where(TenantDB.id == org_id))
    if not tenant:
        raise HTTPException(status_code=404, detail="Organization not found")
    return tenant


async def create_organization_with_admin(
    db: AsyncSession, req: OrganizationCreateWithAdmin, created_by: uuid.UUID
) -> tuple[TenantDB, UserDB]:
    domain = _slugify_domain(req.name)
    while await db.scalar(select(TenantDB).where(TenantDB.domain == domain)):
        domain = _slugify_domain(req.name)

    tenant = TenantDB(
        name=req.name,
        domain=domain,
        is_active=True,
        created_by=created_by,
    )
    db.add(tenant)
    await db.flush()

    admin = UserDB(
        tenant_id=tenant.id,
        email=req.admin_email,
        full_name=req.admin_name,
        password_hash=get_password_hash(req.admin_password),
        role=UserRole.ADMIN.value,
    )
    db.add(admin)
    await db.commit()
    await db.refresh(tenant)
    await db.refresh(admin)
    return tenant, admin


async def update_organization(
    db: AsyncSession, org_id: uuid.UUID, req: OrganizationUpdate
) -> TenantDB:
    tenant = await get_organization(db, org_id)
    if req.name is not None:
        tenant.name = req.name
    if req.is_active is not None:
        tenant.is_active = req.is_active
    tenant.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(tenant)
    return tenant


async def list_org_users(db: AsyncSession, org_id: uuid.UUID) -> list[UserDB]:
    await set_tenant_guc(db, org_id)
    result = await db.scalars(
        select(UserDB)
        .where(UserDB.tenant_id == org_id)
        .order_by(UserDB.created_at.desc())
    )
    return list(result.all())


async def create_org_user(db: AsyncSession, org_id: uuid.UUID, req: OrgUserCreate) -> UserDB:
    await set_tenant_guc(db, org_id)
    tenant = await get_organization(db, org_id)
    if not tenant.is_active:
        raise HTTPException(status_code=400, detail="Organization is disabled")

    existing = await db.scalar(
        select(UserDB).where(UserDB.email == req.email, UserDB.tenant_id == org_id)
    )
    if existing:
        raise HTTPException(status_code=409, detail="User already exists")

    user = UserDB(
        tenant_id=org_id,
        email=req.email,
        full_name=req.name,
        password_hash=get_password_hash(req.password),
        role=req.role.value,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def update_org_user(
    db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID, req: OrgUserUpdate
) -> UserDB:
    await set_tenant_guc(db, org_id)
    user = await db.scalar(
        select(UserDB).where(UserDB.id == user_id, UserDB.tenant_id == org_id)
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role == UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Cannot modify Super Admin")

    if req.name is not None:
        user.full_name = req.name
    if req.email is not None:
        clash = await db.scalar(
            select(UserDB).where(
                UserDB.email == req.email,
                UserDB.tenant_id == org_id,
                UserDB.id != user_id,
            )
        )
        if clash:
            raise HTTPException(status_code=409, detail="Email already in use")
        user.email = req.email
    if req.role is not None:
        user.role = req.role.value
    if req.is_active is not None:
        user.is_active = req.is_active

    await db.commit()
    await db.refresh(user)
    return user


async def delete_org_user(db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID) -> None:
    await set_tenant_guc(db, org_id)
    user = await db.scalar(
        select(UserDB).where(UserDB.id == user_id, UserDB.tenant_id == org_id)
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role == UserRole.ADMIN.value:
        # Prevent deleting the last admin
        admin_count = await db.scalar(
            select(func.count())
            .select_from(UserDB)
            .where(
                UserDB.tenant_id == org_id,
                UserDB.role == UserRole.ADMIN.value,
                UserDB.is_active.is_(True),
            )
        )
        if admin_count and int(admin_count) <= 1:
            raise HTTPException(status_code=400, detail="Cannot delete the last Organization Admin")
    await db.delete(user)
    await db.commit()


async def reset_org_user_password(
    db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID, new_password: str
) -> UserDB:
    await set_tenant_guc(db, org_id)
    user = await db.scalar(
        select(UserDB).where(UserDB.id == user_id, UserDB.tenant_id == org_id)
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.password_hash = get_password_hash(new_password)
    await db.commit()
    await db.refresh(user)
    return user


async def update_own_profile(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    name: str | None = None,
    phone: str | None = None,
    job_title: str | None = None,
    department: str | None = None,
    location: str | None = None,
    fields_set: set[str] | None = None,
) -> UserDB:
    user = await db.scalar(select(UserDB).where(UserDB.id == user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    touched = fields_set or {
        k
        for k, v in {
            "name": name,
            "phone": phone,
            "job_title": job_title,
            "department": department,
            "location": location,
        }.items()
        if v is not None
    }
    if "name" in touched:
        user.full_name = name or None
    if "phone" in touched:
        user.phone = phone or None
    if "job_title" in touched:
        user.job_title = job_title or None
    if "department" in touched:
        user.department = department or None
    if "location" in touched:
        user.location = location or None
    await db.commit()
    await db.refresh(user)
    return user


async def change_own_password(
    db: AsyncSession, user_id: uuid.UUID, current_password: str, new_password: str
) -> None:
    user = await db.scalar(select(UserDB).where(UserDB.id == user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not verify_password(current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    user.password_hash = get_password_hash(new_password)
    await db.commit()

