from contextlib import asynccontextmanager

import httpx
import redis.asyncio as redis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.health import router as health_router
from app.api.router import router as api_router
from app.config import settings
from app.middleware.auth import GatewayAuthMiddleware
from app.middleware.rate_limit import TenantRateLimitMiddleware
from rag_platform_schemas.common import ErrorResponse
from rag_platform_observability import RequestContextMiddleware, get_logger, setup_observability


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0))
    app.state.redis = redis.from_url(settings.redis_url, decode_responses=True)
    yield
    await app.state.http_client.aclose()
    await app.state.redis.aclose()


app = FastAPI(
    title="API Gateway",
    description="RAG Platform API Gateway",
    version="0.1.0",
    lifespan=lifespan,
    redirect_slashes=False,
)

setup_observability("gateway", app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "https://polyphonic-spin-fabulous-charity.trycloudflare.com",
        "https://promotional-cargo-owned-presidential.trycloudflare.com",  # Admin UI tunnel
        "https://crop-meters-continued-centers.trycloudflare.com",         # User UI tunnel
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestContextMiddleware)

redis_client = redis.from_url(settings.redis_url, decode_responses=True)
app.add_middleware(TenantRateLimitMiddleware, redis_client=redis_client)
app.add_middleware(GatewayAuthMiddleware, redis_client=redis_client)

app.include_router(health_router)
app.include_router(api_router, prefix="/api/v1")


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger = get_logger("error_handler")
    logger.error("Unhandled exception", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="internal_server_error",
            message="An unexpected error occurred.",
        ).model_dump(),
    )
