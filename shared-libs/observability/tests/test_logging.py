import json
import logging
from io import StringIO
import structlog
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from rag_platform_observability.logging import (
    RequestContextMiddleware,
    get_logger,
    setup_logging,
)

def test_setup_logging(capsys):
    setup_logging("test-service")
    logger = get_logger("test-logger")
    
    logger.info("hello_world", foo="bar")
    
    captured = capsys.readouterr()
    log_line = captured.out.strip()
    
    # Verify it's valid JSON
    data = json.loads(log_line)
    
    assert data["event"] == "hello_world"
    assert data["foo"] == "bar"
    assert data["service"] == "test-service"
    assert data["logger"] == "test-logger"
    assert data["level"] == "info"
    assert "timestamp" in data

app = FastAPI()
app.add_middleware(RequestContextMiddleware)

@app.get("/test")
async def test_route(request: Request):
    request.state.tenant_id = "tenant-123"
    request.state.user_id = "user-456"
    return {"status": "ok"}

client = TestClient(app)

def test_request_context_middleware(capsys):
    setup_logging("test-service")
    
    response = client.get("/test", headers={"X-Request-ID": "req-999"})
    
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req-999"
    
    # Check access log
    captured = capsys.readouterr()
    lines = captured.out.strip().split("\n")
    
    # We should have the access log
    access_log = None
    for line in lines:
        data = json.loads(line)
        if data.get("event") == "request_completed":
            access_log = data
            break
            
    assert access_log is not None
    assert access_log["request_id"] == "req-999"
    assert access_log["tenant_id"] == "tenant-123"
    assert access_log["user_id"] == "user-456"
    assert access_log["method"] == "GET"
    assert access_log["path"] == "/test"
    assert access_log["status_code"] == 200
