import os

from app.config import settings

os.environ.setdefault("LLM_ROUTER_MODE", settings.llm_router_mode)
os.environ.setdefault("OLLAMA_BASE_URL", settings.ollama_base_url)
os.environ.setdefault("OLLAMA_MODEL", settings.ollama_model)
os.environ.setdefault("PII_SCRUB_MODE", os.environ.get("PII_SCRUB_MODE", "regex"))

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
    title="LLM Orchestrator Service",
    description=(
        "Prompt assembly, sensitivity routing, litellm fallback chain, "
        "and declarative guardrail application."
    ),
    version="0.1.0",
)

setup_observability("llm-orchestrator-service", app)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(TenantContextMiddleware)
app.include_router(api_router, prefix="/api/v1")


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="llm-orchestrator-service",
        checks={"llm_router": settings.llm_router_mode},
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
