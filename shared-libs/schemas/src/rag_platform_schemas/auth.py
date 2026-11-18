"""
Auth-domain Pydantic models.

Canonical shapes for Users, Organizations (tenants), JWT claims, and token
request/response payloads. No service may define its own copy of these.

Organization == Tenant in the data layer (tenants table / tenant_id column).
Auth APIs expose organization_* field names for the new login UX.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class UserRole(StrEnum):
    """Roles embedded in JWT claims and stored in the users table."""

    ADMIN = "admin"  # Organization Admin
    END_USER = "end_user"  # Organization User
    SUPER_ADMIN = "super_admin"  # Platform; no organization


# ---------------------------------------------------------------------------
# Organization (= Tenant) models
# ---------------------------------------------------------------------------


class TenantCreate(BaseModel):
    """Legacy create-tenant body (setup-token). Prefer OrganizationCreateWithAdmin."""

    name: Annotated[str, Field(min_length=1, max_length=120)]
    domain: Annotated[str, Field(min_length=1, max_length=120, pattern=r"^[a-z0-9\-]+$")]

    model_config = ConfigDict(str_strip_whitespace=True)


class Tenant(BaseModel):
    """Tenant / organization as returned by internal APIs."""

    id: uuid.UUID
    name: str
    domain: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrganizationPublic(BaseModel):
    """Public org list item for login/register dropdowns."""

    id: uuid.UUID
    name: str

    model_config = ConfigDict(from_attributes=True)


class Organization(BaseModel):
    """Full organization record for Super Admin management."""

    id: uuid.UUID
    name: str
    domain: str
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None
    created_by: uuid.UUID | None = None

    model_config = ConfigDict(from_attributes=True)


class OrganizationCreateWithAdmin(BaseModel):
    """Super Admin creates an organization and its first Organization Admin."""

    name: Annotated[str, Field(min_length=1, max_length=120)]
    admin_name: Annotated[str, Field(min_length=1, max_length=120)]
    admin_email: EmailStr
    admin_password: Annotated[str, Field(min_length=8, max_length=128)]

    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("admin_password")
    @classmethod
    def password_not_trivial(cls, v: str) -> str:
        if v.lower() in {"password", "12345678", "password1"}:
            raise ValueError("Password is too common.")
        return v


class OrganizationUpdate(BaseModel):
    """Patch organization metadata / status."""

    name: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    is_active: bool | None = None

    model_config = ConfigDict(str_strip_whitespace=True)


# ---------------------------------------------------------------------------
# User models
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    """Public registration into an organization (always end_user)."""

    email: EmailStr
    password: Annotated[str, Field(min_length=8, max_length=128)]
    name: Annotated[str, Field(min_length=1, max_length=120)] = "User"
    organization_id: uuid.UUID
    # Accepted for backward compatibility during transition; ignored if organization_id set
    tenant_id: uuid.UUID | None = None
    role: UserRole = UserRole.END_USER

    model_config = ConfigDict(str_strip_whitespace=True)

    @model_validator(mode="before")
    @classmethod
    def prefer_organization_id(cls, data: object) -> object:
        if isinstance(data, dict):
            if data.get("organization_id") is None and data.get("tenant_id") is not None:
                data = {**data, "organization_id": data["tenant_id"]}
        return data

    @field_validator("password")
    @classmethod
    def password_not_trivial(cls, v: str) -> str:
        if v.lower() in {"password", "12345678", "password1"}:
            raise ValueError("Password is too common.")
        return v


class OrgUserCreate(BaseModel):
    """Organization Admin creates a user in their own org."""

    name: Annotated[str, Field(min_length=1, max_length=120)]
    email: EmailStr
    password: Annotated[str, Field(min_length=8, max_length=128)]
    role: UserRole = UserRole.END_USER

    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("role")
    @classmethod
    def role_allowed(cls, v: UserRole) -> UserRole:
        if v == UserRole.SUPER_ADMIN:
            raise ValueError("Cannot create super_admin via org user APIs")
        return v

    @field_validator("password")
    @classmethod
    def password_not_trivial(cls, v: str) -> str:
        if v.lower() in {"password", "12345678", "password1"}:
            raise ValueError("Password is too common.")
        return v


class OrgUserUpdate(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    email: EmailStr | None = None
    role: UserRole | None = None
    is_active: bool | None = None

    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("role")
    @classmethod
    def role_allowed(cls, v: UserRole | None) -> UserRole | None:
        if v == UserRole.SUPER_ADMIN:
            raise ValueError("Cannot assign super_admin via org user APIs")
        return v


class ResetPasswordRequest(BaseModel):
    new_password: Annotated[str, Field(min_length=8, max_length=128)]

    @field_validator("new_password")
    @classmethod
    def password_not_trivial(cls, v: str) -> str:
        if v.lower() in {"password", "12345678", "password1"}:
            raise ValueError("Password is too common.")
        return v


class User(BaseModel):
    """User as returned by the API (never includes password_hash)."""

    id: uuid.UUID
    tenant_id: uuid.UUID | None = None
    organization_id: uuid.UUID | None = None
    email: str
    full_name: str | None = None
    phone: str | None = None
    job_title: str | None = None
    department: str | None = None
    location: str | None = None
    role: UserRole
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def sync_org_id(self) -> User:
        if self.organization_id is None and self.tenant_id is not None:
            self.organization_id = self.tenant_id
        return self


class ProfileUpdate(BaseModel):
    """Self-service profile update (personal + professional)."""

    name: Annotated[str, Field(max_length=120)] | None = None
    phone: Annotated[str, Field(max_length=40)] | None = None
    job_title: Annotated[str, Field(max_length=120)] | None = None
    department: Annotated[str, Field(max_length=120)] | None = None
    location: Annotated[str, Field(max_length=120)] | None = None

    model_config = ConfigDict(str_strip_whitespace=True)


class ChangePasswordRequest(BaseModel):
    current_password: Annotated[str, Field(min_length=1, max_length=128)]
    new_password: Annotated[str, Field(min_length=8, max_length=128)]

    @field_validator("new_password")
    @classmethod
    def password_not_trivial(cls, v: str) -> str:
        if v.lower() in {"password", "12345678", "password1"}:
            raise ValueError("Password is too common.")
        return v


class SuperAdminBootstrap(BaseModel):
    """One-time platform Super Admin creation via setup-token."""

    name: Annotated[str, Field(min_length=1, max_length=120)] = "Super Admin"
    email: EmailStr
    password: Annotated[str, Field(min_length=8, max_length=128)]

    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("password")
    @classmethod
    def password_not_trivial(cls, v: str) -> str:
        if v.lower() in {"password", "12345678", "password1"}:
            raise ValueError("Password is too common.")
        return v


# ---------------------------------------------------------------------------
# Auth request / response models
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    """
    Login body.

    - Organization users: provide ``organization_id`` + email + password.
    - Super Admin: omit ``organization_id`` (platform login).
    """

    email: EmailStr
    password: str
    organization_id: uuid.UUID | None = None
    # Backward compatible alias
    tenant_id: uuid.UUID | None = None

    model_config = ConfigDict(str_strip_whitespace=True)

    @model_validator(mode="before")
    @classmethod
    def prefer_organization_id(cls, data: object) -> object:
        if isinstance(data, dict):
            if data.get("organization_id") is None and data.get("tenant_id") is not None:
                data = {**data, "organization_id": data["tenant_id"]}
        return data


class TokenResponse(BaseModel):
    """Successful login / refresh response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until access_token expires


# ---------------------------------------------------------------------------
# JWT Claims
# ---------------------------------------------------------------------------


class JWTClaims(BaseModel):
    """
    Decoded, validated JWT payload.

    ``sub``              — user UUID (string)
    ``tenant_id``        — organization UUID string (empty for Super Admin)
    ``organization_id``  — same as tenant_id when set; empty for Super Admin
    ``role``             — UserRole value
    ``jti``              — unique token ID (for deny-list lookup)
    ``exp`` / ``iat``    — UNIX timestamps
    ``type``             — "access" | "refresh"
    """

    sub: str
    tenant_id: str = ""
    organization_id: str = ""
    role: UserRole
    jti: str
    exp: int
    iat: int
    type: str = "access"

    @model_validator(mode="before")
    @classmethod
    def sync_org_claim(cls, data: object) -> object:
        if isinstance(data, dict):
            tid = data.get("tenant_id") or ""
            oid = data.get("organization_id") or ""
            if not oid and tid:
                data = {**data, "organization_id": tid}
            if not tid and oid:
                data = {**data, "tenant_id": oid}
        return data
