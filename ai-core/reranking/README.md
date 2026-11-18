# ai-core/reranking

**Technology:** Sentence Transformers CrossEncoder, `BAAI/bge-reranker-v2-m3`

## Interface

```python
from rag_platform_reranking import rerank
results = rerank(query, passages, top_k=5)
# RankedResult(text, original_index, score)
```

Set `RERANKER_MODEL_NAME=fake` for offline stub scores.

## Module

Module 4 — Layer 5 / Stage 5
