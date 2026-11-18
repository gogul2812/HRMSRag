"""Per-tenant rate limiting at the gateway (Redis)."""

from __future__ import annotations

import os

import redis.asyncio as redis
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response


class TenantRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Sliding fixed-window limiter keyed by tenant (or IP for unauthenticated).
    Env: GATEWAY_RATE_LIMIT_PER_MINUTE (default 120).
    """

    def __init__(self, app, redis_client: redis.Redis):
        super().__init__(app)
        self.redis = redis_client
        self.limit = int(os.environ.get("GATEWAY_RATE_LIMIT_PER_MINUTE", "120"))

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in {"/health", "/metrics"} or request.method == "OPTIONS":
            return await call_next(request)

        tenant = request.headers.get("X-Tenant-ID")
        if not tenant:
            # Try to avoid rate-limiting login storms by IP
            client = request.client.host if request.client else "unknown"
            key = f"ragplatform:ratelimit:ip:{client}"
        else:
            key = f"ragplatform:ratelimit:tenant:{tenant}"

        try:
            count = await self.redis.incr(key)
            if count == 1:
                await self.redis.expire(key, 60)
            if count > self.limit:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded for this tenant"},
                    headers={"Retry-After": "60"},
                )
        except Exception:
            # Fail open if Redis is unavailable
            pass

        return await call_next(request)
