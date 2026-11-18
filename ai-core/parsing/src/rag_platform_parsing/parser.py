"""
Layer 1 — Parsing.

Primary: Docling for PDF/DOCX (and structured export).
Fallback: Tesseract OCR for image / scanned inputs.
Markdown: direct read with structure preserved.
"""

from __future__ import annotations

import io
import logging
import mimetypes
import re
from pathlib import Path

from rag_platform_parsing.models import (
    DocumentMetadata,
    ParsedDocument,
    ParsedPage,
    ParsedTable,
)

logger = logging.getLogger(__name__)

_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
_MARKDOWN_SUFFIXES = {".md", ".markdown"}


def parse(file_bytes: bytes, filename: str) -> ParsedDocument:
    """
    Parse a document into structured text + tables.

    Interface per Module 4: ``parse(file_bytes, filename) -> ParsedDocument``.
    """
    if not file_bytes:
        raise ValueError("Empty file_bytes")

    suffix = Path(filename).suffix.lower()
    content_type = mimetypes.guess_type(filename)[0]

    if suffix in _MARKDOWN_SUFFIXES:
        return _parse_markdown(file_bytes, filename, content_type)

    if suffix in _IMAGE_SUFFIXES:
        return _parse_image_ocr(file_bytes, filename, content_type)

    # PDF / DOCX / other office formats → Docling, then digital-PDF fallback, then OCR
    try:
        return _parse_with_docling(file_bytes, filename, content_type)
    except Exception as exc:
        logger.warning(
            "Docling parse failed for %s (%s); trying fallbacks",
            filename,
            exc,
        )
        if suffix == ".pdf":
            try:
                return _parse_pdf_pypdf(file_bytes, filename, content_type)
            except Exception as pdf_exc:
                logger.warning("pypdf fallback failed for %s (%s)", filename, pdf_exc)
            return _parse_image_ocr(file_bytes, filename, content_type)
        if suffix in _IMAGE_SUFFIXES:
            return _parse_image_ocr(file_bytes, filename, content_type)
        raise


def _parse_pdf_pypdf(
    file_bytes: bytes, filename: str, content_type: str | None
) -> ParsedDocument:
    """Lightweight digital-PDF text extraction when Docling is unavailable."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(file_bytes))
    pages: list[ParsedPage] = []
    texts: list[str] = []
    for i, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ""
        texts.append(page_text)
        pages.append(ParsedPage(page_number=i, text=page_text))
    raw = "\n\n".join(texts)
    tables = _extract_markdown_tables(raw)
    # pypdf often yields whitespace-aligned tables; keep raw text for chunking
    return ParsedDocument(
        raw_text=raw,
        pages=pages,
        tables=tables,
        metadata=DocumentMetadata(
            filename=filename,
            content_type=content_type or "application/pdf",
            page_count=len(pages),
            extra={"parser": "pypdf"},
        ),
    )

def _parse_markdown(
    file_bytes: bytes, filename: str, content_type: str | None
) -> ParsedDocument:
    text = file_bytes.decode("utf-8", errors="replace")
    tables = _extract_markdown_tables(text)
    return ParsedDocument(
        raw_text=text,
        pages=[ParsedPage(page_number=1, text=text)],
        tables=tables,
        metadata=DocumentMetadata(
            filename=filename,
            content_type=content_type or "text/markdown",
            page_count=1,
            extra={"parser": "markdown"},
        ),
    )


def _extract_markdown_tables(text: str) -> list[ParsedTable]:
    """Extract GitHub-flavored markdown tables as structured objects."""
    tables: list[ParsedTable] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines) - 1:
        if (
            "|" in lines[i]
            and i + 1 < len(lines)
            and re.match(r"^\s*\|?[\s:-]+\|[\s|:-]+$", lines[i + 1])
        ):
            block = [lines[i]]
            j = i + 1
            while j < len(lines) and "|" in lines[j]:
                block.append(lines[j])
                j += 1
            headers, rows = _md_table_rows(block)
            md = "\n".join(block)
            tables.append(
                ParsedTable(page=1, headers=headers, rows=rows, markdown=md)
            )
            i = j
            continue
        i += 1
    return tables


def _md_table_rows(block: list[str]) -> tuple[list[str], list[list[str]]]:
    def split_row(line: str) -> list[str]:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        return cells

    headers = split_row(block[0])
    rows: list[list[str]] = []
    for line in block[2:]:  # skip header + separator
        if not line.strip():
            continue
        rows.append(split_row(line))
    return headers, rows


def _parse_with_docling(
    file_bytes: bytes, filename: str, content_type: str | None
) -> ParsedDocument:
    try:
        from docling.datamodel.base_models import DocumentStream
        from docling.document_converter import DocumentConverter
    except ImportError as exc:
        raise RuntimeError(
            "Docling is required to parse this file type. "
            "Install with: pip install 'rag-platform-parsing[docling]'"
        ) from exc

    converter = DocumentConverter()
    stream = DocumentStream(name=filename, stream=io.BytesIO(file_bytes))
    result = converter.convert(stream)
    doc = result.document

    markdown = doc.export_to_markdown()
    tables = _tables_from_docling(doc)
    # Prefer markdown-extracted tables if Docling table export is empty
    if not tables:
        tables = _extract_markdown_tables(markdown)

    pages: list[ParsedPage] = []
    try:
        # Best-effort page iteration across Docling versions
        page_count = getattr(doc, "num_pages", None) or len(getattr(doc, "pages", []) or []) or 1
    except Exception:
        page_count = 1

    if hasattr(doc, "pages") and doc.pages:
        for idx, page in enumerate(doc.pages, start=1):
            page_text = getattr(page, "text", None) or ""
            pages.append(ParsedPage(page_number=idx, text=page_text))
    else:
        pages = [ParsedPage(page_number=1, text=markdown)]

    return ParsedDocument(
        raw_text=markdown,
        pages=pages,
        tables=tables,
        metadata=DocumentMetadata(
            filename=filename,
            content_type=content_type,
            page_count=page_count if isinstance(page_count, int) else len(pages),
            extra={"parser": "docling"},
        ),
    )


def _tables_from_docling(doc: object) -> list[ParsedTable]:
    tables: list[ParsedTable] = []
    doc_tables = getattr(doc, "tables", None) or []
    for t in doc_tables:
        try:
            # Docling TableItem often supports export_to_markdown / export_to_dataframe
            if hasattr(t, "export_to_markdown"):
                md = t.export_to_markdown()
            elif hasattr(t, "export_to_dataframe"):
                df = t.export_to_dataframe()
                md = df.to_markdown(index=False)
            else:
                md = str(t)
            headers, rows = _md_table_rows(md.splitlines()) if "|" in md else ([], [])
            if not headers and not rows and md.strip():
                # keep markdown even if row parse fails
                tables.append(ParsedTable(markdown=md))
            else:
                tables.append(ParsedTable(headers=headers, rows=rows, markdown=md))
        except Exception as exc:
            logger.warning("Failed to export Docling table: %s", exc)
    return tables


def _parse_image_ocr(
    file_bytes: bytes, filename: str, content_type: str | None
) -> ParsedDocument:
    from PIL import Image
    import pytesseract

    image = Image.open(io.BytesIO(file_bytes))
    text = pytesseract.image_to_string(image)
    return ParsedDocument(
        raw_text=text,
        pages=[ParsedPage(page_number=1, text=text)],
        tables=_extract_markdown_tables(text),
        metadata=DocumentMetadata(
            filename=filename,
            content_type=content_type or "image/*",
            page_count=1,
            extra={"parser": "tesseract"},
        ),
    )
