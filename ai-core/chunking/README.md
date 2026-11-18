# ai-core/chunking

**Technology:** LlamaIndex MarkdownNodeParser + SentenceSplitter

## Purpose

Table/header-aware chunking. A table row is never split mid-row.

### Interface

```python
from rag_platform_chunking import chunk
chunks = chunk(parsed_document, doc_id="...", tenant_id="...")
```

## Module

Module 4 — Layer 2 (Chunking) / Stage 3
