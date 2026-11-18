"""Prometheus metrics helpers."""

from __future__ import annotations

import time
from typing import Callable

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

REQUEST_COUNT = Counter(
    "rag_http_requests_total",
    "Total HTTP requests",
    ["service", "method", "path", "status"],
)
REQUEST_LATENCY = Histogram(
    "rag_http_request_duration_seconds",
    "HTTP request latency",
    ["service", "method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
LLM_PROVIDER_COUNT = Counter(
    "rag_llm_provider_calls_total",
    "LLM router provider attempts",
    ["service", "provider", "result"],
)
RETRIEVAL_COUNT = Counter(
    "rag_retrieval_queries_total",
    "Retrieval queries",
    ["service", "insufficient"],
)


def mount_metrics(app: FastAPI, service_name: str) -> None:
    """Attach /metrics and HTTP instrumentation middleware."""

    class MetricsMiddleware(BaseHTTPMiddleware):
        async def dispatch(
            self, request: Request, call_next: RequestResponseEndpoint
        ) -> Response:
            if request.url.path in {"/metrics", "/health"}:
                return await call_next(request)
            start = time.perf_counter()
            response = await call_next(request)
            elapsed = time.perf_counter() - start
            path = request.url.path
            # Avoid high-cardinality path params explosion for common prefixes
            label_path = path if path.count("/") <= 4 else "/".join(path.split("/")[:4]) + "/*"
            REQUEST_COUNT.labels(
                service_name, request.method, label_path, str(response.status_code)
            ).inc()
            REQUEST_LATENCY.labels(service_name, request.method, label_path).observe(elapsed)
            return response

    app.add_middleware(MetricsMiddleware)

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
