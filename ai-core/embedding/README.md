# ai-core/embedding

**Technology:** Sentence Transformers, BGE-large-en-v1.5 (1024-d)

## Purpose

Local embedding wrapper. Nothing is sent to a third-party API.

### Interface

```python
from rag_platform_embedding import embed, embed_texts
vec = embed("query text")           # list[float] length 1024
vecs = embed_texts(["a", "b"])
```

### Install

```bash
pip install -e ./embedding
pip install -e './embedding[model]'  # sentence-transformers + torch
```

Set `EMBEDDING_MODEL_NAME=fake` for offline stub vectors (still 1024-d).

## Module

Module 4 — Layer 3 (Embedding) / Stage 3
