"""Stage 2 live DoD smoke test against admin-config-service + Postgres."""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
import uuid
import urllib.request

import asyncpg
import httpx
from jose import jwt


async def seed_tenants() -> tuple[uuid.UUID, uuid.UUID]:
    url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(url)
    t_a, t_b = uuid.uuid4(), uuid.uuid4()
    await conn.execute(
        "INSERT INTO tenants (id, name, domain) VALUES ($1, $2, $3)",
        t_a,
        "Smoke A",
        f"smoke-a-{t_a.hex[:8]}",
    )
    await conn.execute(
        "INSERT INTO tenants (id, name, domain) VALUES ($1, $2, $3)",
        t_b,
        "Smoke B",
        f"smoke-b-{t_b.hex[:8]}",
    )
    await conn.close()
    return t_a, t_b


def make_token(role: str, tenant_id: uuid.UUID) -> str:
    secret = os.environ["JWT_SECRET_KEY"]
    now = int(time.time())
    return jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "tenant_id": str(tenant_id),
            "role": role,
            "jti": str(uuid.uuid4()),
            "exp": now + 3600,
            "iat": now,
            "type": "access",
        },
        secret,
        algorithm=os.environ.get("JWT_ALGORITHM", "HS256"),
    )


def wait_for_health(url: str, timeout_s: float = 30) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return
        except Exception:
            time.sleep(0.4)
    raise RuntimeError(f"Service did not become healthy: {url}")


def main() -> None:
    t_a, t_b = asyncio.run(seed_tenants())
    admin_a = make_token("admin", t_a)
    admin_b = make_token("admin", t_b)
    end_user = make_token("end_user", t_a)

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8002",
        ],
        cwd="/app/services/admin-config-service",
        env=os.environ.copy(),
    )
    try:
        wait_for_health("http://127.0.0.1:8002/health")
        base = "http://127.0.0.1:8002/api/v1/config"
        with httpx.Client(timeout=30.0) as client:
            r1 = client.post(
                f"{base}/prompt",
                headers={"Authorization": f"Bearer {admin_a}"},
                json={"text": "Rules v1"},
            )
            r2 = client.post(
                f"{base}/prompt",
                headers={"Authorization": f"Bearer {admin_a}"},
                json={"text": "Rules v2 — active"},
            )
            assert r1.status_code == 201 and r2.status_code == 201, (r1.text, r2.text)
            v2_id = r2.json()["id"]

            act = client.put(
                f"{base}/prompt/{v2_id}/activate",
                headers={"Authorization": f"Bearer {admin_a}"},
            )
            assert act.status_code == 200, act.text

            active = client.get(
                f"{base}/prompt",
                headers={"Authorization": f"Bearer {admin_a}"},
            )
            assert active.status_code == 200
            body = active.json()
            assert body["version"] == 2
            assert body["text"] == "Rules v2 — active"
            assert body["is_active"] is True

            assert (
                client.get(
                    f"{base}/prompt/{v2_id}",
                    headers={"Authorization": f"Bearer {admin_b}"},
                ).status_code
                == 404
            )
            assert (
                client.put(
                    f"{base}/prompt/{v2_id}/activate",
                    headers={"Authorization": f"Bearer {admin_b}"},
                ).status_code
                == 404
            )

            assert (
                client.get(
                    f"{base}/prompt",
                    headers={"Authorization": f"Bearer {end_user}"},
                ).status_code
                == 403
            )
            assert (
                client.post(
                    f"{base}/prompt",
                    headers={"Authorization": f"Bearer {end_user}"},
                    json={"text": "x"},
                ).status_code
                == 403
            )

        print("STAGE2_LIVE_SMOKE_OK")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    main()
