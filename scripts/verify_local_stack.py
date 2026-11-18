"""Start local services and run smoke verification (auth → ingest → chat)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "logs" / "verify"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def health(port: int, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def http_json(method: str, url: str, body: dict | None = None, headers: dict | None = None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read().decode()
            return r.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw}
        return e.code, payload


def start_service(name: str, rel: str, port: int) -> subprocess.Popen:
    cwd = ROOT / rel
    out = open(LOG_DIR / f"{name}.out.log", "w", encoding="utf-8")
    err = open(LOG_DIR / f"{name}.err.log", "w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(cwd),
        stdout=out,
        stderr=err,
        env=os.environ.copy(),
    )
    print(f"started {name} pid={proc.pid} port={port}")
    return proc


def main() -> int:
    load_dotenv(ROOT / ".env")
    # Verification overrides
    os.environ["EMBEDDING_MODEL_NAME"] = "fake"
    os.environ["RERANKER_MODEL_NAME"] = "fake"
    os.environ["LLM_ROUTER_MODE"] = "fake"
    os.environ["CHAT_FAKE_ORCHESTRATOR"] = "1"
    os.environ["CELERY_TASK_ALWAYS_EAGER"] = "1"
    os.environ["PII_SCRUB_MODE"] = "regex"
    os.environ["SETUP_TOKEN"] = os.environ.get("SETUP_TOKEN") or "local-setup-token"
    os.environ["QDRANT_HOST"] = "127.0.0.1"
    os.environ["DATABASE_URL"] = (
        "postgresql+asyncpg://raguser:RagDevVerify2026@127.0.0.1:15432/ragplatform"
    )
    os.environ["DATABASE_URL_SYNC"] = (
        "postgresql://raguser:RagDevVerify2026@127.0.0.1:15432/ragplatform"
    )
    os.environ["REDIS_URL"] = "redis://:RagDevRedis2026@127.0.0.1:16379/0"
    os.environ["CELERY_BROKER_URL"] = os.environ["REDIS_URL"]
    os.environ["CELERY_RESULT_BACKEND"] = os.environ["REDIS_URL"]
    os.environ["CELERY_TASK_ALWAYS_EAGER"] = "1"
    os.environ["OTEL_SDK_DISABLED"] = "true"

    services = [
        ("auth-service", "services/auth-service", 8001),
        ("gateway", "services/gateway", 8000),
        ("admin-config-service", "services/admin-config-service", 8002),
        ("ingestion-service", "services/ingestion-service", 8003),
        ("retrieval-service", "services/retrieval-service", 8004),
        ("chat-service", "services/chat-service", 8006),
    ]

    procs: list[subprocess.Popen] = []
    try:
        for name, rel, port in services:
            if health(port):
                print(f"{name} already healthy on {port}")
                continue
            procs.append(start_service(name, rel, port))

        deadline = time.time() + 90
        while time.time() < deadline:
            statuses = {port: health(port) for _, _, port in services}
            if all(statuses.values()):
                print("ALL_HEALTHY", statuses)
                break
            time.sleep(2)
        else:
            print("HEALTH_TIMEOUT", {p: health(p) for _, _, p in services})
            for name, _, _ in services:
                err = LOG_DIR / f"{name}.err.log"
                if err.exists():
                    print(f"--- {name} err ---")
                    print(err.read_text(encoding="utf-8", errors="replace")[-1500:])
            return 1

        setup = os.environ["SETUP_TOKEN"]
        # Bootstrap via auth direct (gateway blocks tenants without JWT)
        code, tenant = http_json(
            "POST",
            "http://127.0.0.1:8001/api/v1/tenants",
            {"name": "Verify Tenant", "domain": f"verify-{int(time.time())}"},
            {"setup-token": setup},
        )
        print("create_tenant", code, tenant)
        if code != 201:
            return 1
        tenant_id = tenant["id"]

        code, admin = http_json(
            "POST",
            "http://127.0.0.1:8001/api/v1/auth/register-admin",
            {
                "email": f"admin-{int(time.time())}@example.com",
                "password": "StrongPassword123!",
                "tenant_id": tenant_id,
                "role": "admin",
            },
            {"setup-token": setup},
        )
        print("register_admin", code, admin)
        if code != 201:
            return 1

        code, user = http_json(
            "POST",
            "http://127.0.0.1:8001/api/v1/auth/register",
            {
                "email": f"user-{int(time.time())}@example.com",
                "password": "StrongPassword123!",
                "tenant_id": tenant_id,
                "role": "end_user",
            },
        )
        print("register_user", code, user)
        if code != 201:
            return 1

        # Login via gateway
        code, tok = http_json(
            "POST",
            "http://127.0.0.1:8000/api/v1/auth/login",
            {
                "email": admin["email"],
                "password": "StrongPassword123!",
                "tenant_id": tenant_id,
            },
        )
        print("gateway_login_admin", code, list(tok.keys()) if isinstance(tok, dict) else tok)
        if code != 200 or "access_token" not in tok:
            return 1
        admin_token = tok["access_token"]

        code, tok_u = http_json(
            "POST",
            "http://127.0.0.1:8000/api/v1/auth/login",
            {
                "email": user["email"],
                "password": "StrongPassword123!",
                "tenant_id": tenant_id,
            },
        )
        print("gateway_login_user", code)
        if code != 200:
            return 1
        user_token = tok_u["access_token"]

        # Upload a small markdown doc via gateway → ingestion
        sample = ROOT / "logs" / "verify" / "sample.md"
        sample.write_text(
            "# Project Phoenix\n\nLeave policy is 20 days annual leave.\n",
            encoding="utf-8",
        )
        boundary = "---- ragboundary"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="sample.md"\r\n'
            f"Content-Type: text/markdown\r\n\r\n"
            f"{sample.read_text(encoding='utf-8')}\r\n"
            f"--{boundary}--\r\n"
        ).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:8000/api/v1/ingest/upload",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {admin_token}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                upload = json.loads(r.read().decode())
                upload_code = r.status
        except urllib.error.HTTPError as e:
            upload_code = e.code
            upload = json.loads(e.read().decode() or "{}")
        print("upload", upload_code, upload)
        if upload_code not in (200, 201, 202):
            return 1

        doc = upload.get("document") if isinstance(upload, dict) else None
        doc_id = None
        if isinstance(doc, dict):
            doc_id = doc.get("id")
        doc_id = doc_id or upload.get("id") or upload.get("document_id")
        status_val = None
        if doc_id:
            for _ in range(30):
                code, doc = http_json(
                    "GET",
                    f"http://127.0.0.1:8000/api/v1/ingest/documents/{doc_id}",
                    headers={"Authorization": f"Bearer {admin_token}"},
                )
                status_val = (doc or {}).get("status")
                print("doc_status", code, status_val)
                if status_val in ("indexed", "ready", "completed", "failed"):
                    break
                time.sleep(2)

        # Chat: create session then stream (fake orchestrator)
        code, session = http_json(
            "POST",
            "http://127.0.0.1:8000/api/v1/chat/sessions",
            {"title": "verify"},
            {"Authorization": f"Bearer {user_token}"},
        )
        print("create_session", code, session)
        chat_ok = False
        if code == 201 and session.get("id"):
            chat_body = json.dumps({"content": "What is the leave policy?"}).encode()
            req = urllib.request.Request(
                f"http://127.0.0.1:8000/api/v1/chat/sessions/{session['id']}/stream",
                data=chat_body,
                method="POST",
                headers={
                    "Authorization": f"Bearer {user_token}",
                    "Content-Type": "application/json",
                    "Accept": "text/event-stream",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    chunks = r.read().decode(errors="replace")
                    print("chat_stream_bytes", len(chunks))
                    print("chat_stream_preview", chunks[:400].replace("\n", "\\n"))
                    chat_ok = len(chunks) > 0 and r.status == 200
            except urllib.error.HTTPError as e:
                print("chat_stream_error", e.code, e.read().decode()[:500])
        else:
            print("create_session_failed", code, session)

        print(
            "SUMMARY",
            json.dumps(
                {
                    "migrations": "0005",
                    "auth_login": True,
                    "upload_code": upload_code,
                    "doc_status": status_val,
                    "chat_ok": chat_ok,
                }
            ),
        )
        return 0 if upload_code in (200, 201, 202) else 1
    finally:
        for p in procs:
            p.terminate()
        time.sleep(1)
        for p in procs:
            if p.poll() is None:
                p.kill()


if __name__ == "__main__":
    raise SystemExit(main())
