"""
Layer 3 — Embedding.

Model: BGE-large-en-v1.5 via sentence-transformers (local, 1024-dim).
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Sequence

from rag_platform_embedding.config import settings

logger = logging.getLogger(__name__)

_model = None
_model_lock = threading.Lock()
_EXPECTED_DIM = 1024


def _load_model():
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is not None:
            return _model
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is required for real embeddings. "
                "Install with: pip install 'rag-platform-embedding[model]' "
                "or set EMBEDDING_MODEL_NAME=fake for offline stub vectors."
            ) from exc

        logger.info(
            "Loading embedding model %s on %s",
            settings.embedding_model_name,
            settings.embedding_device,
        )
        _model = SentenceTransformer(
            settings.embedding_model_name,
            device=settings.embedding_device,
        )
        return _model


def embed(text: str) -> list[float]:
    """
    Embed a single string.

    Interface per Module 4: ``embed(text: str) -> vector[1024]``.
    """
    vectors = embed_texts([text])
    return vectors[0]


def embed_texts(texts: Sequence[str], device: str | None = None) -> list[list[float]]:
    """
    Batch-embed texts. Returns one 1024-d float vector per input.
    """
    if not texts:
        return []

    # Deterministic stub for unit tests / offline CI (still 1024-d).
    if settings.embedding_model_name.strip().lower() in {"fake", "stub", "test"}:
        return [_fake_vector(t) for t in texts]

    model = _load_model()
    target_device = device or settings.embedding_device
    if target_device and hasattr(model, "to"):
        model.to(target_device)

    all_texts = list(texts)
    batch_size = max(1, settings.embedding_batch_size)
    result: list[list[float]] = []
    for start in range(0, len(all_texts), batch_size):
        batch = all_texts[start : start + batch_size]
        vectors = _encode_with_retry(model, batch)
        for vec in vectors:
            as_list = [float(x) for x in vec]
            if len(as_list) != _EXPECTED_DIM:
                raise RuntimeError(
                    f"Expected {_EXPECTED_DIM}-dim embedding, got {len(as_list)}. "
                    f"Model={settings.embedding_model_name}"
                )
            result.append(as_list)
        if len(all_texts) > batch_size:
            logger.info(
                "embed_texts progress %s/%s", min(start + batch_size, len(all_texts)), len(all_texts)
            )
    return result


def _encode_with_retry(model, batch: list[str]):
    """One sub-batch, retried with backoff for transient failures (OOM, driver hiccups)."""
    last_exc: Exception | None = None
    for attempt in range(settings.embedding_max_retries + 1):
        try:
            return model.encode(batch, normalize_embeddings=True, show_progress_bar=False)
        except Exception as exc:  # noqa: BLE001 - deliberately broad, retried below
            last_exc = exc
            if attempt < settings.embedding_max_retries:
                wait = 0.5 * (2**attempt)
                logger.warning(
                    "embed batch failed (attempt %s/%s): %s — retrying in %.1fs",
                    attempt + 1,
                    settings.embedding_max_retries + 1,
                    exc,
                    wait,
                )
                time.sleep(wait)
    raise RuntimeError(f"Embedding failed after retries: {last_exc}") from last_exc


def _fake_vector(text: str) -> list[float]:
    """Stable pseudo-embedding for tests (sum of char codes → seeded floats)."""
    seed = sum(ord(c) for c in text) or 1
    return [((seed * (i + 1)) % 997) / 997.0 for i in range(_EXPECTED_DIM)]


def reset_model_cache() -> None:
    """Test helper — drop the singleton so a new model name can load."""
    global _model
    with _model_lock:
        _model = None
