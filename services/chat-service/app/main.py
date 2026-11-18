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
    title="Chat Service",
    description=(
        "Chat sessions, message history, SSE streaming via llm-orchestrator-service, "
        "and message feedback."
    ),
    version="0.1.0",
)

setup_observability("chat-service", app)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(TenantContextMiddleware)
app.include_router(api_router, prefix="/api/v1")


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="chat-service",
        checks={"database": "ok"},
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
