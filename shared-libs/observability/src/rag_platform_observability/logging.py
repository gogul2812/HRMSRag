import logging
import os
import sys
import uuid

import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

# Context variables for structlog
structlog.contextvars.clear_contextvars()


def setup_logging(service_name: str) -> None:
    """
    Configures standard library logging and structlog to output JSON.
    Call this exactly once at service startup.
    """
    log_level_str = os.environ.get("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure standard logging to pass through structlog
    handler = logging.StreamHandler(sys.stdout)
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)
        
    root_logger.addHandler(handler)

    # Bind the service name globally
    structlog.contextvars.bind_contextvars(service=service_name)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Returns a structlog logger."""
    return structlog.get_logger(name)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware that generates a request_id and binds it, along with
    tenant_id and user_id (if available), to the structlog contextvars.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        # Prefer gateway-injected headers so logs include tenant before route deps run
        tenant_id = request.headers.get("X-Tenant-ID") or getattr(
            request.state, "tenant_id", None
        )
        user_id = request.headers.get("X-User-ID") or getattr(request.state, "user_id", None)

        bind: dict = {"request_id": request_id}
        if tenant_id:
            bind["tenant_id"] = tenant_id
            request.state.tenant_id = tenant_id
        if user_id:
            bind["user_id"] = user_id
            request.state.user_id = user_id

        # Attach OpenTelemetry trace/span ids when available
        try:
            from opentelemetry import trace

            span = trace.get_current_span()
            ctx = span.get_span_context() if span else None
            if ctx and ctx.is_valid:
                bind["trace_id"] = format(ctx.trace_id, "032x")
                bind["span_id"] = format(ctx.span_id, "016x")
        except Exception:
            pass

        structlog.contextvars.bind_contextvars(**bind)

        response = await call_next(request)

        # Re-read state in case auth deps filled it later
        tenant_id = getattr(request.state, "tenant_id", tenant_id)
        user_id = getattr(request.state, "user_id", user_id)

        logger = get_logger("access")
        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            tenant_id=tenant_id,
            user_id=user_id,
        )

        response.headers["X-Request-ID"] = request_id
        structlog.contextvars.clear_contextvars()
        return response