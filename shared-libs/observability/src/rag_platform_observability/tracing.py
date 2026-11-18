"""OpenTelemetry tracing setup (OTLP when endpoint set; no-op otherwise)."""

from __future__ import annotations

import os
from typing import Any

_tracer_provider = None


def setup_tracing(service_name: str) -> Any:
    """
    Configure OTLP tracer provider when OTEL_EXPORTER_OTLP_ENDPOINT is set.
    Returns the tracer for `service_name`, or a no-op tracer.
    """
    global _tracer_provider
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    except ImportError:
        return _NoopTracer()

    resource = Resource.create(
        {
            "service.name": os.environ.get("OTEL_SERVICE_NAME", service_name),
            "service.instance.id": service_name,
        }
    )
    provider = TracerProvider(resource=resource)

    if endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )

            exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
            provider.add_span_processor(BatchSpanProcessor(exporter))
        except Exception:
            # Fall back to console so local DoD can still see spans
            if os.environ.get("OTEL_CONSOLE_EXPORT", "").lower() in {"1", "true", "yes"}:
                provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    elif os.environ.get("OTEL_CONSOLE_EXPORT", "").lower() in {"1", "true", "yes"}:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    _tracer_provider = provider
    return trace.get_tracer(service_name)


def get_tracer(service_name: str = "rag-platform"):
    try:
        from opentelemetry import trace

        return trace.get_tracer(service_name)
    except ImportError:
        return _NoopTracer()


def instrument_fastapi(app) -> None:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
    except Exception:
        pass


class _NoopSpan:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def set_attribute(self, *args, **kwargs):
        pass

    def record_exception(self, *args, **kwargs):
        pass


class _NoopTracer:
    def start_as_current_span(self, name: str, **kwargs):
        return _NoopSpan()
