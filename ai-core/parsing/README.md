# ai-core/parsing

**Technology:** Docling (primary), pypdf (digital PDF fallback), Tesseract OCR, Python 3.11+

## Purpose

Unified document parsing used by `ingestion-service`. Library only — no API.

### Interface

```python
from rag_platform_parsing import parse
parsed = parse(file_bytes, filename)  # -> ParsedDocument
```

### Install

```bash
pip install -e ./parsing
pip install -e './parsing[docling]'   # optional, recommended for PDF/DOCX
```

## Module

Module 4 — Layer 1 (Parsing) / Stage 3
