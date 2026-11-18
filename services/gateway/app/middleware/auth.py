import redis.asyncio as redis
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from jose import jwt, JWTError
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.config import settings

class GatewayAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, redis_client: redis.Redis):
        super().__init__(app)
        self.redis_client = redis_client

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # CORS preflight and public routes
        if request.method == "OPTIONS":
            return await call_next(request)

        if request.url.path.startswith("/api/v1/auth/login") or \
           request.url.path.startswith("/api/v1/auth/register") or \
           request.url.path.startswith("/api/v1/organizations/public") or \
           request.url.path.startswith("/api/v1/organizations/bootstrap-super-admin") or \
           request.url.path == "/health":
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "Not authenticated"})

        token = auth_header.split(" ")[1]
        
        try:
            payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
            jti = payload.get("jti")
            tenant_id = payload.get("tenant_id") or payload.get("organization_id") or "platform"
            
            # Check deny-list
            if jti:
                is_revoked = await self.redis_client.get(f"ragplatform:{tenant_id}:jwt_deny:{jti}")
                if is_revoked:
                    return JSONResponse(status_code=401, content={"detail": "Token revoked"})
                    
            # Inject headers for downstream
            # We mutate headers by replacing them in scope
            headers = dict(request.scope["headers"])
            headers[b"x-tenant-id"] = str(payload.get("tenant_id") or "").encode()
            headers[b"x-user-id"] = str(payload.get("sub")).encode()
            headers[b"x-role"] = str(payload.get("role")).encode()
            request.scope["headers"] = [(k, v) for k, v in headers.items()]

        except JWTError as e:
            return JSONResponse(status_code=401, content={"detail": "Invalid token"})

        return await call_next(request)
