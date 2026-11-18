"""Unit tests for Stage 3 ai-core (Layers 1–3)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# Force stub embeddings for fast, offline unit tests (still 1024-d).
os.environ["EMBEDDING_MODEL_NAME"] = "fake"

from rag_platform_chunking import chunk
from rag_platform_embedding import embed, embed_texts, reset_model_cache
from rag_platform_parsing import parse

SAMPLES = Path(__file__).resolve().parents[1] / "samples"
MD_SAMPLE = SAMPLES / "sample_project.md"


@pytest.fixture(autouse=True)
def _reset_embedder():
    reset_model_cache()
    yield
    reset_model_cache()


def test_parse_markdown_preserves_table_structure():
    parsed = parse(MD_SAMPLE.read_bytes(), MD_SAMPLE.name)
    assert "Project Phoenix" in parsed.raw_text
    assert len(parsed.tables) >= 1
    table = parsed.tables[0]
    assert "Ava Chen" in " ".join(cell for row in table.rows for cell in row)
    assert table.headers  # structured, not flattened-only


def test_chunk_never_splits_table_mid_row():
    parsed = parse(MD_SAMPLE.read_bytes(), MD_SAMPLE.name)
    chunks = chunk(parsed, doc_id="doc-1", tenant_id="tenant-a")
    assert chunks
    assert all(c.tenant_id == "tenant-a" for c in chunks)
    assert all(c.doc_id == "doc-1" for c in chunks)

    table_chunks = [c for c in chunks if c.metadata.get("contains_table")]
    assert table_chunks, "expected at least one table-bearing chunk"
    for c in table_chunks:
        for line in c.text.splitlines():
            stripped = line.strip()
            if stripped.startswith("|"):
                assert stripped.endswith("|"), f"mid-row split: {line!r}"


def test_embed_returns_1024_dims():
    vec = embed("staffing feasibility for EHR migration")
    assert len(vec) == 1024
    assert all(isinstance(x, float) for x in vec)

    batch = embed_texts(["alpha", "beta"])
    assert len(batch) == 2
    assert {len(v) for v in batch} == {1024}


def test_pipeline_markdown_end_to_end():
    parsed = parse(MD_SAMPLE.read_bytes(), MD_SAMPLE.name)
    chunks = chunk(parsed, doc_id="md-1", tenant_id="t1")
    vectors = embed_texts([c.text for c in chunks])
    assert len(vectors) == len(chunks)
    assert all(len(v) == 1024 for v in vectors)


def test_generate_and_parse_pdf_with_table():
    pytest.importorskip("reportlab")
    import sys

    ai_core_root = Path(__file__).resolve().parents[1]
    if str(ai_core_root) not in sys.path:
        sys.path.insert(0, str(ai_core_root))
    from samples.generate_samples import write_pdf

    pdf_path = write_pdf()
    assert pdf_path.is_file()

    try:
        parsed = parse(pdf_path.read_bytes(), pdf_path.name)
    except Exception as exc:
        # Docling needs extra system libs in some environments
        pytest.skip(f"Docling unavailable in this environment: {exc}")

    assert parsed.raw_text.strip()
    # Prefer structured tables; fall back to markdown table detection in text
    joined = parsed.raw_text + "\n" + "\n".join(t.markdown for t in parsed.tables)
    assert "Northwind" in joined or "Supplier" in joined


def test_generate_and_ocr_scanned_image():
    pytest.importorskip("PIL")
    pytesseract = pytest.importorskip("pytesseract")
    import sys

    ai_core_root = Path(__file__).resolve().parents[1]
    if str(ai_core_root) not in sys.path:
        sys.path.insert(0, str(ai_core_root))
    from samples.generate_samples import write_scanned_png

    # Skip if system tesseract binary is missing
    try:
        pytesseract.get_tesseract_version()
    except Exception as exc:
        pytest.skip(f"Tesseract binary not installed: {exc}")

    png_path = write_scanned_png()
    parsed = parse(png_path.read_bytes(), png_path.name)
    assert parsed.metadata.extra.get("parser") == "tesseract"
    # OCR is imperfect; require at least one known token
    text = parsed.raw_text.upper()
    assert any(tok in text for tok in ("JANE", "EMP", "DOE", "EMPLOYEE", "CLINICAL"))
