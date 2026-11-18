"""Bootstrap the shared Qdrant collection ``document_chunks`` (Module 5 §3)."""

from __future__ import annotations

import os
import sys

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

COLLECTION = "document_chunks"
VECTOR_SIZE = 1024


def main() -> int:
    host = os.environ.get("QDRANT_HOST", "localhost")
    port = int(os.environ.get("QDRANT_PORT", "6333"))
    api_key = os.environ.get("QDRANT_API_KEY") or None
    # Empty string → None (compose often sets QDRANT_API_KEY=)
    if api_key is not None and not api_key.strip():
        api_key = None

    client_kwargs = {
        "host": host,
        "port": port,
        "api_key": api_key,
    }
    try:
        client = QdrantClient(**client_kwargs, check_compatibility=False)
    except TypeError:
        client = QdrantClient(**client_kwargs)
    existing = {c.name for c in client.get_collections().collections}
    if COLLECTION in existing:
        print(f"Collection '{COLLECTION}' already exists — OK")
        return 0

    client.create_collection(
        collection_name=COLLECTION,
        vectors_config=qm.VectorParams(
            size=VECTOR_SIZE,
            distance=qm.Distance.COSINE,
            hnsw_config=qm.HnswConfigDiff(m=16, ef_construct=128),
        ),
    )
    for field in ("tenant_id", "doc_id", "doc_type"):
        client.create_payload_index(
            collection_name=COLLECTION,
            field_name=field,
            field_schema=qm.PayloadSchemaType.KEYWORD,
        )
    # Required for the lexical MatchText leg of hybrid search (retrieval-service
    # falls back to a brute-force scroll+BM25 scan on every query without this).
    client.create_payload_index(
        collection_name=COLLECTION,
        field_name="text",
        field_schema=qm.TextIndexParams(
            type=qm.TextIndexType.TEXT,
            tokenizer=qm.TokenizerType.WORD,
            min_token_len=2,
            lowercase=True,
        ),
    )
    print(f"Created collection '{COLLECTION}' (dim={VECTOR_SIZE}, cosine, hnsw tuned, text index)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
