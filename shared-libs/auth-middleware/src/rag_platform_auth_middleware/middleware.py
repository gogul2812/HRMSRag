import os
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from rag_platform_schemas.auth import JWTClaims, UserRole
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

# The algorithm and secret are standard for all services so we fetch them from env
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "")
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")

security = HTTPBearer()


async def get_current_user(
    request: Request, credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)]
) -> JWTClaims:
    """
    FastAPI dependency that decodes and validates the JWT from the Authorization header.
    Raises 401 if invalid, expired, or missing.
    Does NOT check the Redis deny-list (the Gateway does that).
    """
    if not JWT_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT_SECRET_KEY is not configured",
        )

    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        claims = JWTClaims(**payload)
        
        if claims.type != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        # Also bind to request state for middleware access
        request.state.tenant_id = claims.tenant_id
        request.state.user_id = claims.sub
        request.state.role = claims.role
        
        return claims
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid claims: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_role(required_role: UserRole) -> Callable:
    """
    Dependency factory that ensures the token has at least the required role.
    Super_admin > admin > end_user.
    """

    async def role_checker(claims: Annotated[JWTClaims, Depends(get_current_user)]) -> JWTClaims:
        # Simple hierarchy:
        # super_admin can do anything
        if claims.role == UserRole.SUPER_ADMIN:
            return claims
            
        # admin can do anything end_user can do
        if required_role == UserRole.END_USER:
            return claims
            
        # exact match
        if claims.role == required_role:
            return claims
            
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )

    return role_checker


class TenantContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware that ensures tenant_id is available in request state.
    For downstream services (behind gateway), the gateway sends headers.
    This middleware extracts them if present, so we don't always have to
    decode the JWT if the gateway already did.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # If the gateway sent context headers, use them
        tenant_id = request.headers.get("X-Tenant-ID")
        user_id = request.headers.get("X-User-ID")
        role = request.headers.get("X-Role")

        if tenant_id:
            request.state.tenant_id = tenant_id
        if user_id:
            request.state.user_id = user_id
        if role:
            try:
                request.state.role = UserRole(role)
            except ValueError:
                request.state.role = None
        
        # If not sent by gateway, they will be set by the Depends() later if the route requires auth
        
        response = await call_next(request)
        return response
