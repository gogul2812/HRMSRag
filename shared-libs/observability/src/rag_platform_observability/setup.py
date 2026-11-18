"""Unified observability bootstrap for every FastAPI service."""

from __future__ import annotations

from fastapi import FastAPI

from rag_platform_observability.logging import setup_logging
from rag_platform_observability.metrics import mount_metrics
from rag_platform_observability.tracing import instrument_fastapi, setup_tracing


def setup_observability(service_name: str, app: FastAPI | None = None) -> None:
    """
    Configure structured logging, tracing, and (when app given) /metrics.
    Call once at process start; pass `app` after FastAPI() construction.
    """
    setup_logging(service_name)
    setup_tracing(service_name)
    if app is not None:
        mount_metrics(app, service_name)
        instrument_fastapi(app)
