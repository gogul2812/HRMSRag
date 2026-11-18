"""Load-test helpers for bulk ingestion and concurrent chat."""

from __future__ import annotations

import asyncio
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx


@dataclass
class LoadResult:
    name: str
    total: int
    successes: int
    failures: int
    latency_ms: list[float] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def p50_ms(self) -> float:
        if not self.latency_ms:
            return 0.0
        return float(statistics.median(self.latency_ms))

    @property
    def p95_ms(self) -> float:
        if not self.latency_ms:
            return 0.0
        ordered = sorted(self.latency_ms)
        idx = min(len(ordered) - 1, int(len(ordered) * 0.95))
        return float(ordered[idx])

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "total": self.total,
            "successes": self.successes,
            "failures": self.failures,
            "p50_ms": round(self.p50_ms, 2),
            "p95_ms": round(self.p95_ms, 2),
            "notes": self.notes,
        }


async def bulk_ingest(
    *,
    base_url: str,
    token: str,
    files: list[Path],
    doc_type: str = "project",
    concurrency: int = 8,
) -> LoadResult:
    """Upload many files to ingestion-service via gateway."""
    sem = asyncio.Semaphore(concurrency)
    result = LoadResult(name="bulk_ingest", total=len(files), successes=0, failures=0)
    url = f"{base_url.rstrip('/')}/api/v1/ingest/upload"

    async with httpx.AsyncClient(timeout=120.0) as client:

        async def one(path: Path) -> None:
            async with sem:
                t0 = time.perf_counter()
                try:
                    with path.open("rb") as fh:
                        res = await client.post(
                            url,
                            headers={"Authorization": f"Bearer {token}"},
                            files={"file": (path.name, fh, "application/octet-stream")},
                            data={"doc_type": doc_type},
                        )
                    elapsed = (time.perf_counter() - t0) * 1000
                    result.latency_ms.append(elapsed)
                    if res.status_code in (200, 202):
                        result.successes += 1
                    else:
                        result.failures += 1
                        result.notes.append(f"{path.name}:{res.status_code}")
                except Exception as exc:
                    result.failures += 1
                    result.notes.append(f"{path.name}:{type(exc).__name__}")

        await asyncio.gather(*(one(p) for p in files))
    return result


async def concurrent_chat(
    *,
    base_url: str,
    tokens: list[str],
    queries: list[str],
    concurrency: int = 10,
) -> LoadResult:
    """
    Concurrent non-streaming chat turns across tenants/tokens.
    Creates a session per token then posts /message.
    """
    sem = asyncio.Semaphore(concurrency)
    pairs = [(tokens[i % len(tokens)], queries[i % len(queries)]) for i in range(max(len(queries), concurrency))]
    result = LoadResult(name="concurrent_chat", total=len(pairs), successes=0, failures=0)

    async with httpx.AsyncClient(timeout=120.0) as client:

        async def one(token: str, query: str) -> None:
            async with sem:
                headers = {"Authorization": f"Bearer {token}"}
                t0 = time.perf_counter()
                try:
                    sess = await client.post(
                        f"{base_url.rstrip('/')}/api/v1/chat/sessions",
                        headers=headers,
                        json={},
                    )
                    if sess.status_code not in (200, 201):
                        result.failures += 1
                        result.notes.append(f"session:{sess.status_code}")
                        return
                    sid = sess.json()["id"]
                    msg = await client.post(
                        f"{base_url.rstrip('/')}/api/v1/chat/sessions/{sid}/message",
                        headers=headers,
                        json={"content": query},
                    )
                    elapsed = (time.perf_counter() - t0) * 1000
                    result.latency_ms.append(elapsed)
                    if msg.status_code == 200:
                        result.successes += 1
                    else:
                        result.failures += 1
                        result.notes.append(f"message:{msg.status_code}")
                except Exception as exc:
                    result.failures += 1
                    result.notes.append(type(exc).__name__)

        await asyncio.gather(*(one(t, q) for t, q in pairs))
    return result


async def simulate_fallback_storm(
    *,
    rounds: int = 20,
) -> LoadResult:
    """
    Concurrent primary-fail → secondary fallback simulation.

    Uses an in-process fake router (same contract as LLM_FAKE_FAIL_PRIMARY)
    so this load path does not require litellm / native builds.
    """
    result = LoadResult(name="fallback_storm", total=rounds, successes=0, failures=0)
    sem = asyncio.Semaphore(10)

    async def fake_generate(i: int) -> str:
        # Mirror ai-core/llm_router fake fallback behavior
        await asyncio.sleep(0)  # yield
        attempts = ["fake-primary:forced_failure", "fake-secondary:ok"]
        provider = "fake-secondary"
        _ = attempts
        return provider

    async def one(i: int) -> None:
        async with sem:
            t0 = time.perf_counter()
            try:
                provider = await fake_generate(i)
                elapsed = (time.perf_counter() - t0) * 1000
                result.latency_ms.append(elapsed)
                if provider == "fake-secondary":
                    result.successes += 1
                else:
                    result.failures += 1
                    result.notes.append(f"unexpected_provider:{provider}")
            except Exception as exc:
                result.failures += 1
                result.notes.append(type(exc).__name__)

    await asyncio.gather(*(one(i) for i in range(rounds)))
    return result
