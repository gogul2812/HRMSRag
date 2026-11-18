"""Stage 10 — observability metrics smoke tests."""

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest

from rag_platform_observability import setup_observability


@pytest.mark.asyncio
async def test_metrics_endpoint_exposes_prometheus():
    app = FastAPI()
    setup_observability("test-service", app)

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.get("/ping")
        res = await client.get("/metrics")
        assert res.status_code == 200
        body = res.text
        assert "rag_http_requests_total" in body or "python_info" in body
