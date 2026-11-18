"""
rag_platform_auth_middleware
============================
FastAPI dependencies for JWT validation and role enforcement.
"""

from rag_platform_auth_middleware.middleware import (
    TenantContextMiddleware,
    get_current_user,
    require_role,
)
from rag_platform_auth_middleware.tenant_context import set_tenant_guc

__all__ = [
    "get_current_user",
    "require_role",
    "TenantContextMiddleware",
    "set_tenant_guc",
]
