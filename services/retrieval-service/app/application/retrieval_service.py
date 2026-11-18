"""
Hybrid retrieval: dense vector search + lexical (BM25-style / MatchText) fusion,
then cross-encoder rerank, then threshold cutoff.
"""

from __future__ import annotations

import math
import re
from typing import Any

from qdrant_client.http import models as qm

from app.config import settings
from app.infrastructure.qdrant_client import get_qdrant_client
from rag_platform_embedding import embed
from rag_platform_observability import get_logger
from rag_platform_reranking import rerank
from rag_platform_schemas.retrieval import RetrieveRequest, RetrieveResponse, RetrievedChunk

logger = get_logger(__name__)


def retrieve(*, tenant_id: str, req: RetrieveRequest) -> RetrieveResponse:
    """
    Run hybrid search + rerank scoped to ``tenant_id``.

    Tenant filter is mandatory — never optional.
    """
    client = get_qdrant_client()
    collection = settings.qdrant_collection

    must: list[qm.FieldCondition] = [
        qm.FieldCondition(key="tenant_id", match=qm.MatchValue(value=tenant_id)),
    ]
    if req.doc_type:
        must.append(
            qm.FieldCondition(key="doc_type", match=qm.MatchValue(value=req.doc_type))
        )
    tenant_filter = qm.Filter(must=must)

    query_vector = embed(req.query)
    dense_hits = _dense_search(
        client, collection, query_vector, tenant_filter, settings.retrieval_dense_limit
    )
    lexical_hits = _lexical_search(
        client, collection, req.query, tenant_filter, settings.retrieval_lexical_limit
    )

    fused = _rrf_fuse(dense_hits, lexical_hits, limit=req.candidate_limit)
    if not fused:
        logger.info(
            "retrieval_empty",
            tenant_id=tenant_id,
            query=req.query[:80],
        )
        return RetrieveResponse(
            query=req.query,
            tenant_id=tenant_id,
            chunks=[],
            insufficient_information=True,
            best_score=None,
            message="No candidates found for this tenant.",
        )

    passages = [h["text"] for h in fused]
    ranked = rerank(req.query, passages, top_k=req.top_k)

    chunks: list[RetrievedChunk] = []
    for r in ranked:
        base = fused[r.original_index]
        chunks.append(
            RetrievedChunk(
                text=r.text,
                score=float(r.score),
                doc_id=str(base["doc_id"]),
                doc_type=base.get("doc_type"),
                chunk_index=base.get("chunk_index"),
                section=base.get("section"),
                page=base.get("page"),
                tenant_id=tenant_id,
                payload=base.get("payload") or {},
            )
        )

    best = chunks[0].score if chunks else None
    insufficient = best is None or best < settings.retrieval_score_threshold
    if insufficient:
        return RetrieveResponse(
            query=req.query,
            tenant_id=tenant_id,
            chunks=[],
            insufficient_information=True,
            best_score=best,
            message=(
                "Insufficient information: best rerank score "
                f"{best} below threshold {settings.retrieval_score_threshold}."
            ),
        )

    return RetrieveResponse(
        query=req.query,
        tenant_id=tenant_id,
        chunks=chunks,
        insufficient_information=False,
        best_score=best,
        message=None,
    )


def _dense_search(client, collection, vector, query_filter, limit: int) -> list[dict]:
    # qdrant-client 1.12+ uses query_points (/points/query). Older clients had search.
    # Prefer query_points; fall back to search for older client installs.
    if hasattr(client, "query_points"):
        result = client.query_points(
            collection_name=collection,
            query=vector,
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
        )
        points = getattr(result, "points", result)
        return [_point_to_hit(p, source="dense") for p in points]

    points = client.search(
        collection_name=collection,
        query_vector=vector,
        query_filter=query_filter,
        limit=limit,
        with_payload=True,
    )
    return [_point_to_hit(p, source="dense") for p in points]


def _lexical_search(client, collection, query: str, query_filter, limit: int) -> list[dict]:
    """
    Lexical leg of hybrid search.

    Prefer Qdrant MatchText on payload ``text`` when available; otherwise fall
    back to scrolling tenant points and scoring with a local BM25-ish overlap.
    """
    # Try MatchText first
    try:
        text_filter = qm.Filter(
            must=[
                *query_filter.must,
                qm.FieldCondition(key="text", match=qm.MatchText(text=query)),
            ]
        )
        points, _ = client.scroll(
            collection_name=collection,
            scroll_filter=text_filter,
            limit=limit,
            with_payload=True,
        )
        if points:
            return [_point_to_hit(p, source="lexical", score=1.0) for p in points]
    except Exception as exc:
        logger.debug("MatchText lexical search unavailable: %s", exc)

    # Fallback: scroll tenant corpus (capped) and BM25-rank locally
    try:
        points, _ = client.scroll(
            collection_name=collection,
            scroll_filter=query_filter,
            limit=max(limit * 5, 50),
            with_payload=True,
        )
    except Exception as exc:
        logger.warning("Lexical scroll failed: %s", exc)
        return []

    scored: list[tuple[float, Any]] = []
    for p in points:
        text = (p.payload or {}).get("text") or ""
        score = _bm25_lite(query, text)
        if score > 0:
            scored.append((score, p))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [
        _point_to_hit(p, source="lexical", score=s) for s, p in scored[:limit]
    ]


def _bm25_lite(query: str, text: str, k1: float = 1.2, b: float = 0.75) -> float:
    """Lightweight BM25-style score for a single document (no IDF corpus)."""
    q_tokens = re.findall(r"[a-z0-9]+", query.lower())
    if not q_tokens:
        return 0.0
    t_tokens = re.findall(r"[a-z0-9]+", text.lower())
    if not t_tokens:
        return 0.0
    avgdl = 80.0
    dl = len(t_tokens)
    tf: dict[str, int] = {}
    for tok in t_tokens:
        tf[tok] = tf.get(tok, 0) + 1
    score = 0.0
    for qt in set(q_tokens):
        f = tf.get(qt, 0)
        if f == 0:
            continue
        # Pseudo-IDF: rarer in query boosts slightly via presence
        idf = math.log(1.0 + 1.5)
        denom = f + k1 * (1 - b + b * dl / avgdl)
        score += idf * (f * (k1 + 1)) / denom
    return float(score)


def _rrf_fuse(
    dense: list[dict], lexical: list[dict], *, limit: int, k: int = 60
) -> list[dict]:
    """Reciprocal Rank Fusion of dense + lexical candidate lists."""
    scores: dict[str, float] = {}
    meta: dict[str, dict] = {}

    def key_of(hit: dict) -> str:
        return f"{hit['doc_id']}:{hit.get('chunk_index')}:{hash(hit['text'][:120])}"

    for rank, hit in enumerate(dense):
        key = key_of(hit)
        scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
        meta[key] = hit
    for rank, hit in enumerate(lexical):
        key = key_of(hit)
        scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
        meta.setdefault(key, hit)

    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return [meta[key] for key, _ in ordered[:limit]]


def _point_to_hit(point, *, source: str, score: float | None = None) -> dict:
    payload = dict(point.payload or {})
    text = payload.get("text") or ""
    return {
        "id": str(point.id),
        "text": text,
        "doc_id": payload.get("doc_id"),
        "doc_type": payload.get("doc_type"),
        "chunk_index": payload.get("chunk_index"),
        "section": payload.get("section"),
        "page": payload.get("page"),
        "score": float(score if score is not None else getattr(point, "score", 0.0) or 0.0),
        "source": source,
        "payload": payload,
    }
