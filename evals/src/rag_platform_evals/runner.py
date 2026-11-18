"""Run per-tenant eval datasets and produce faithfulness baseline."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx

from rag_platform_evals.metrics import CaseScore, aggregate, score_case

DATASETS_DIR = Path(__file__).resolve().parents[2] / "datasets"


def load_dataset(path: Path | str) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        alt = DATASETS_DIR / path
        if alt.is_file():
            p = alt
        else:
            raise FileNotFoundError(path)
    return json.loads(p.read_text(encoding="utf-8"))


def _fake_answer(case: dict[str, Any]) -> tuple[str, list[str]]:
    """Deterministic offline answers grounded in dataset contexts (no live services)."""
    if case.get("expect_insufficient"):
        return (
            "I don't have enough relevant information in the knowledge base to answer that.",
            [],
        )
    contexts = list(case.get("ground_truth_contexts") or [])
    expected = case.get("expected_answer") or " ".join(contexts)
    return expected, contexts


async def _live_answer(
    case: dict[str, Any],
    *,
    base_url: str,
    token: str,
) -> tuple[str, list[str]]:
    """Call orchestrator with ground-truth contexts as chunks (stable eval)."""
    contexts = list(case.get("ground_truth_contexts") or [])
    if case.get("expect_insufficient"):
        chunks: list[dict] = []
    else:
        chunks = [
            {
                "text": c,
                "doc_id": f"eval-{case.get('id', 'x')}-{i}",
                "doc_type": "project",
                "chunk_index": i,
                "score": 0.9,
            }
            for i, c in enumerate(contexts)
        ]

    url = f"{base_url.rstrip('/')}/api/v1/orchestrate/generate"
    async with httpx.AsyncClient(timeout=120.0) as client:
        res = await client.post(
            url,
            headers={"Authorization": f"Bearer {token}"},
            json={
                "query": case["question"],
                "chunks": chunks,
                "system_prompt_override": (
                    "Answer ONLY using the provided context. If insufficient, say so."
                ),
            },
        )
        res.raise_for_status()
        body = res.json()
    answer = body.get("answer") or ""
    used = [c.get("excerpt") or c.get("text") or "" for c in (body.get("citations") or [])]
    if not used:
        used = contexts
    return answer, used


def run_offline(dataset: dict[str, Any]) -> dict[str, Any]:
    scores: list[CaseScore] = []
    for case in dataset.get("cases") or []:
        answer, contexts = _fake_answer(case)
        scores.append(
            score_case(
                case_id=case["id"],
                question=case["question"],
                answer=answer,
                contexts=contexts,
                expected_contexts=list(case.get("ground_truth_contexts") or []),
                must_include=list(case.get("must_include") or []),
                expect_insufficient=bool(case.get("expect_insufficient")),
            )
        )
    report = aggregate(dataset.get("tenant_key", "unknown"), "offline", scores)
    return report.to_dict()


async def run_live(
    dataset: dict[str, Any],
    *,
    base_url: str | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    base_url = base_url or os.environ.get("EVAL_API_BASE_URL") or os.environ.get(
        "NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000"
    )
    token = token or os.environ.get("EVAL_JWT", "")
    if not token:
        raise RuntimeError("EVAL_JWT (or pass token=) required for live eval")

    scores: list[CaseScore] = []
    for case in dataset.get("cases") or []:
        answer, contexts = await _live_answer(case, base_url=base_url, token=token)
        scores.append(
            score_case(
                case_id=case["id"],
                question=case["question"],
                answer=answer,
                contexts=contexts,
                expected_contexts=list(case.get("ground_truth_contexts") or []),
                must_include=list(case.get("must_include") or []),
                expect_insufficient=bool(case.get("expect_insufficient")),
            )
        )
    report = aggregate(dataset.get("tenant_key", "unknown"), "live", scores)
    return report.to_dict()
