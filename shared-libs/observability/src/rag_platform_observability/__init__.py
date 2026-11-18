"""
rag_platform_observability
==========================
Structured logging, Prometheus metrics, and OpenTelemetry tracing.
"""

from rag_platform_observability.logging import (
    RequestContextMiddleware,
    get_logger,
    setup_logging,
)
from rag_platform_observability.metrics import (
    LLM_PROVIDER_COUNT,
    REQUEST_COUNT,
    REQUEST_LATENCY,
    RETRIEVAL_COUNT,
    mount_metrics,
)
from rag_platform_observability.setup import setup_observability
from rag_platform_observability.tracing import get_tracer, setup_tracing

__all__ = [
    "setup_logging",
    "setup_observability",
    "get_logger",
    "RequestContextMiddleware",
    "mount_metrics",
    "setup_tracing",
    "get_tracer",
    "REQUEST_COUNT",
    "REQUEST_LATENCY",
    "LLM_PROVIDER_COUNT",
    "RETRIEVAL_COUNT",
]
