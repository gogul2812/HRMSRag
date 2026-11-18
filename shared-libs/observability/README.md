# shared-libs/observability

**Technology:** OpenTelemetry, structlog, Prometheus client, Python 3.11+

## Purpose

Single observability setup for every microservice.

```python
from fastapi import FastAPI
from rag_platform_observability import setup_observability, RequestContextMiddleware, get_logger

app = FastAPI()
setup_observability("auth-service", app)  # logging + tracing + /metrics
app.add_middleware(RequestContextMiddleware)
logger = get_logger(__name__)
```

### Provides

1. **Structured JSON logging** — `tenant_id`, `request_id`, `trace_id` when available
2. **OpenTelemetry tracing** — OTLP when `OTEL_EXPORTER_OTLP_ENDPOINT` is set;
   set `OTEL_CONSOLE_EXPORT=1` for local span dumps
3. **Prometheus `/metrics`** — `rag_http_requests_total`, latency histograms,
   `rag_llm_provider_calls_total`

## Env

`LOG_LEVEL`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_SERVICE_NAME`, `OTEL_CONSOLE_EXPORT`
