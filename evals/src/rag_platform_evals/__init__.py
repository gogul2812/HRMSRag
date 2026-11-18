"""rag_platform_evals — Stage 11 evaluation & load testing."""

from rag_platform_evals.metrics import aggregate, faithfulness_score, score_case
from rag_platform_evals.runner import load_dataset, run_offline

__all__ = [
    "aggregate",
    "faithfulness_score",
    "score_case",
    "load_dataset",
    "run_offline",
]
