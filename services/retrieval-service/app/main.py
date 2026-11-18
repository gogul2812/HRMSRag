import os

from app.config import settings

os.environ.setdefault("EMBEDDING_MODEL_NAME", settings.embedding_model_name)
os.environ.setdefault("EMBEDDING_DEVICE", settings.embedding_device)
os.environ.setdefault("RERANKER_MODEL_NAME", settings.reranker_model_name)
os.environ.setdefault("RERANKER_DEVICE", settings.reranker_device)

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.router import api_router
from rag_platform_auth_middleware import TenantContextMiddleware
from rag_platform_observability import (
    RequestContextMiddleware,
    get_logger,
    setup_observability,
)
from rag_platform_schemas.common import ErrorResponse, HealthResponse

app = FastAPI(
    title="Retrieval Service",
    description=(
        "Tenant-scoped hybrid retrieval (dense + lexical) with cross-encoder "
        "reranking and score threshold cutoff."
    ),
    version="0.1.0",
)

setup_observability("retrieval-service", app)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(TenantContextMiddleware)
app.include_router(api_router, prefix="/api/v1")


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="retrieval-service",
        checks={"qdrant": "ok"},
    )


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
