"""
Layer 5 — Reranking.

Model: BAAI/bge-reranker-v2-m3 via sentence-transformers CrossEncoder.
Set RERANKER_MODEL_NAME=fake for offline stub scores (tests).
"""

from __future__ import annotations

import logging
import math
import re
import threading
import time
from typing import Sequence

from rag_platform_reranking.config import settings
from rag_platform_reranking.models import RankedResult

logger = logging.getLogger(__name__)

_model = None
_model_lock = threading.Lock()


def _load_model():
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is not None:
            return _model
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is required for real reranking. "
                "Install with: pip install 'rag-platform-reranking[model]' "
                "or set RERANKER_MODEL_NAME=fake for offline stub scores."
            ) from exc
        logger.info(
            "Loading reranker %s on %s",
            settings.reranker_model_name,
            settings.reranker_device,
        )
        _model = CrossEncoder(
            settings.reranker_model_name,
            device=settings.reranker_device,
        )
        return _model


def rerank(
    query: str,
    passages: Sequence[str],
    top_k: int = 5,
    device: str | None = None,
) -> list[RankedResult]:
    """
    Score (query, passage) pairs and return top_k by descending score.

    Interface per Module 4 / ai-core README.
    """
    if not passages:
        return []
    if top_k < 1:
        raise ValueError("top_k must be >= 1")

    if settings.reranker_model_name.strip().lower() in {"fake", "stub", "test"}:
        scored = [
            RankedResult(text=p, original_index=i, score=_fake_score(query, p))
            for i, p in enumerate(passages)
        ]
    else:
        model = _load_model()
        if device and hasattr(model, "model"):
            try:
                model.model.to(device)
            except Exception:
                pass
        pairs = [(query, p) for p in passages]
        raw_scores = _predict_with_retry(model, pairs)
        scored = [
            RankedResult(text=p, original_index=i, score=float(s))
            for i, (p, s) in enumerate(zip(passages, raw_scores, strict=True))
        ]

    scored.sort(key=lambda r: r.score, reverse=True)
    return scored[:top_k]


def _predict_with_retry(model, pairs: list[tuple[str, str]]):
    """Bounded candidate set (top_k/candidate_limit are capped) — retry, no batching needed."""
    last_exc: Exception | None = None
    for attempt in range(settings.reranker_max_retries + 1):
        try:
            return model.predict(pairs, show_progress_bar=False)
        except Exception as exc:  # noqa: BLE001 - deliberately broad, retried below
            last_exc = exc
            if attempt < settings.reranker_max_retries:
                wait = 0.5 * (2**attempt)
                logger.warning(
                    "rerank predict failed (attempt %s/%s): %s — retrying in %.1fs",
                    attempt + 1,
                    settings.reranker_max_retries + 1,
                    exc,
                    wait,
                )
                time.sleep(wait)
    raise RuntimeError(f"Reranking failed after retries: {last_exc}") from last_exc


def _normalize_token(tok: str) -> str:
    """Light stemming so leave/leaves and day/days still match in fake mode."""
    if len(tok) > 4 and tok.endswith("ies"):
        return tok[:-3] + "y"
    if len(tok) > 3 and tok.endswith("s") and not tok.endswith("ss"):
        return tok[:-1]
    return tok


def _fake_score(query: str, passage: str) -> float:
    """Deterministic lexical overlap score in ~[0, 1] for tests."""
    q_raw = re.findall(r"[a-z0-9]+", query.lower())
    p_raw = re.findall(r"[a-z0-9]+", passage.lower())
    if not q_raw:
        return 0.0
    # Drop ultra-common function words so phrasing noise doesn't crush score
    stop = {
        "a", "an", "the", "i", "we", "you", "me", "my", "our", "u", "do", "does",
        "did", "is", "are", "was", "were", "have", "has", "had", "to", "for",
        "of", "in", "on", "at", "and", "or", "what", "how", "can", "many",
    }
    q_tokens = {_normalize_token(t) for t in q_raw if t not in stop}
    p_tokens = {_normalize_token(t) for t in p_raw}
    if not q_tokens:
        q_tokens = {_normalize_token(t) for t in q_raw}
    overlap = len(q_tokens & p_tokens) / len(q_tokens)
    # Slight length penalty so empty junk doesn't win
    return float(overlap * (1.0 - math.exp(-len(passage) / 80.0)))


def reset_model_cache() -> None:
    global _model
    with _model_lock:
        _model = None
