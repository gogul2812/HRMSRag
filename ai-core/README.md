# ai-core

Shared AI library for the RAG Platform (not a microservice).

Stage 3 implements Module 4 **Layers 1–3 only**:

| Layer | Package | Interface |
|---|---|---|
| 1 Parsing | `rag_platform_parsing` | `parse(file_bytes, filename) -> ParsedDocument` |
| 2 Chunking | `rag_platform_chunking` | `chunk(parsed_document, doc_id=..., tenant_id=...) -> list[Chunk]` |
| 3 Embedding | `rag_platform_embedding` | `embed(text) -> list[float]` (1024-d) |

Layers 4–8 (Qdrant storage, retrieval/rerank, LLM router, guardrails) are
later stages — do not implement them here.

## Quick start

```bash
cd ai-core

# Install packages (editable)
pip install -e ./parsing -e ./chunking -e ./embedding
pip install -e ".[test]"

# Generate binary samples (PDF + scanned PNG)
python samples/generate_samples.py

# Run Stage 3 DoD runner on all three sample types
python run_pipeline.py samples/sample_project.md
python run_pipeline.py samples/sample_table.pdf
python run_pipeline.py samples/sample_scanned.png
```

Set `EMBEDDING_MODEL_NAME=fake` for offline/fast runs (still returns 1024-d
vectors). Production/default is `BAAI/bge-large-en-v1.5`.

## Tests

```bash
cd ai-core
EMBEDDING_MODEL_NAME=fake pytest tests/ -v
```

## System dependencies

- **Tesseract OCR** binary on `PATH` (for scanned images)
- Docling may require additional system libraries for PDF rendering
