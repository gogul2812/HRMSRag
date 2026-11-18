"""Stage 11 unit tests for offline eval metrics + runner."""

from __future__ import annotations

from pathlib import Path

from rag_platform_evals.metrics import faithfulness_score, score_case
from rag_platform_evals.runner import load_dataset, run_offline

DATA = Path(__file__).resolve().parents[1] / "datasets" / "sample_healthcare.json"


def test_faithfulness_high_when_grounded():
    answer = "Project Phoenix uses FastAPI and PostgreSQL with Qdrant."
    contexts = [
        "Backend: FastAPI, Python 3.11",
        "Database: PostgreSQL 16",
        "Vector store: Qdrant",
    ]
    score = faithfulness_score(answer, contexts)
    assert score >= 0.35


def test_faithfulness_insufficient_with_empty_context():
    answer = "I don't have enough relevant information in the knowledge base."
    assert faithfulness_score(answer, []) == 1.0


def test_offline_dataset_produces_faithfulness_baseline():
    dataset = load_dataset(DATA)
    report = run_offline(dataset)
    assert report["tenant_key"] == "sample-healthcare"
    assert report["mode"] == "offline"
    assert report["case_count"] == 5
    assert report["faithfulness_mean"] >= 0.7
    assert all("faithfulness" in c for c in report["cases"])


def test_score_case_must_include():
    s = score_case(
        case_id="x",
        question="What stack?",
        answer="FastAPI and Qdrant on Postgres",
        contexts=["FastAPI", "Qdrant", "Postgres"],
        expected_contexts=["FastAPI", "Qdrant"],
        must_include=["fastapi", "qdrant"],
    )
    assert s.must_include_hit_rate == 1.0
