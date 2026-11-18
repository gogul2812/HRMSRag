import uuid
from datetime import datetime, timezone, timedelta
from typing import Literal

from jose import jwt
import redis.asyncio as redis
from rag_platform_schemas.auth import JWTClaims, UserRole
from app.config import settings

def create_access_token(user_id: str, tenant_id: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)

    payload = {
        "sub": user_id,
        "tenant_id": tenant_id or "",
        "organization_id": tenant_id or "",
        "role": role,
        "jti": str(uuid.uuid4()),
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp()),
        "type": "access",
    }

    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

def create_refresh_token(user_id: str, tenant_id: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.jwt_refresh_token_expire_days)

    payload = {
        "sub": user_id,
        "tenant_id": tenant_id or "",
        "organization_id": tenant_id or "",
        "role": role,
        "jti": str(uuid.uuid4()),
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp()),
        "type": "refresh",
    }

    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

async def revoke_token(token: str, redis_client: redis.Redis) -> None:
    """Adds the token's JTI to the Redis deny-list."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        jti = payload.get("jti")
        exp = payload.get("exp")
        tenant_id = payload.get("tenant_id") or "platform"

        if jti and exp:
            now = int(datetime.now(timezone.utc).timestamp())
            ttl = exp - now
            if ttl > 0:
                key = f"ragplatform:{tenant_id}:jwt_deny:{jti}"
                await redis_client.setex(key, ttl, "revoked")
    except Exception:
        # If token is invalid/expired, it's already effectively revoked
        pass
