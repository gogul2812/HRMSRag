"""
Layer 2 — Chunking.

LlamaIndex header-aware / recursive splitting with a hard rule:
tables are never split mid-row.
"""

from __future__ import annotations

import re
from typing import Any

from llama_index.core.node_parser import MarkdownNodeParser, SentenceSplitter
from llama_index.core.schema import Document, TextNode

from rag_platform_chunking.models import Chunk
from rag_platform_parsing.models import ParsedDocument, ParsedTable

# Module 4: ~300–500 tokens, ~15% overlap. Using characters as a practical
# proxy (≈4 chars/token) when tokenizers are unavailable.
DEFAULT_CHUNK_SIZE = 1600  # ~400 tokens
DEFAULT_CHUNK_OVERLAP = 240  # ~15%


_TABLE_PLACEHOLDER = re.compile(r"<!--TABLE_(\d+)-->")


def chunk(
    parsed_document: ParsedDocument,
    *,
    doc_id: str,
    tenant_id: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[Chunk]:
    """
    Split a ParsedDocument into Chunks.

    Interface per Module 4: ``chunk(parsed_document) -> list[Chunk]``.
    ``doc_id`` / ``tenant_id`` are required so every chunk carries tenant
    isolation metadata from the first stage onward.
    """
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    working_text, table_map = _protect_tables(
        parsed_document.raw_text, parsed_document.tables
    )

    nodes = _split_text(working_text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    chunks: list[Chunk] = []
    for idx, node in enumerate(nodes):
        text = _restore_tables(node.get_content(), table_map)
        # Drop empty / whitespace-only chunks
        if not text.strip():
            continue
        section = _infer_section(text)
        page = _infer_page(parsed_document, text)
        meta: dict[str, Any] = {
            "contains_table": bool(_TABLE_PLACEHOLDER.search(node.get_content()))
            or _looks_like_table(text),
            "filename": parsed_document.metadata.filename,
        }
        if section:
            meta["section"] = section
        chunks.append(
            Chunk(
                text=text,
                chunk_index=len(chunks),
                doc_id=doc_id,
                tenant_id=tenant_id,
                section=section,
                page=page,
                metadata=meta,
            )
        )
    return chunks


def _protect_tables(
    text: str, tables: list[ParsedTable]
) -> tuple[str, dict[str, str]]:
    """
    Replace each known table markdown block with an atomic placeholder so the
    splitter cannot cut through a row.
    """
    table_map: dict[str, str] = {}
    working = text

    # Prefer explicit ParsedTable.markdown blocks
    for i, table in enumerate(tables):
        md = (table.markdown or "").strip()
        if not md:
            md = _table_to_markdown(table)
        if not md or md not in working:
            continue
        key = f"<!--TABLE_{i}-->"
        table_map[key] = md
        working = working.replace(md, key, 1)

    # Also protect any remaining GFM tables in the text
    working, extra = _protect_inline_markdown_tables(working, start_index=len(table_map))
    table_map.update(extra)
    return working, table_map


def _table_to_markdown(table: ParsedTable) -> str:
    if not table.headers and not table.rows:
        return ""
    headers = table.headers or [f"col_{i}" for i in range(len(table.rows[0]))]
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    lines = ["| " + " | ".join(headers) + " |", sep]
    for row in table.rows:
        # pad/truncate to header width
        cells = list(row) + [""] * max(0, len(headers) - len(row))
        lines.append("| " + " | ".join(cells[: len(headers)]) + " |")
    return "\n".join(lines)


def _protect_inline_markdown_tables(
    text: str, start_index: int
) -> tuple[str, dict[str, str]]:
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    table_map: dict[str, str] = {}
    i = 0
    idx = start_index
    while i < len(lines):
        line = lines[i]
        bare = line.rstrip("\n")
        if (
            "|" in bare
            and i + 1 < len(lines)
            and re.match(r"^\s*\|?[\s:-]+\|[\s|:-]+$", lines[i + 1].rstrip("\n"))
        ):
            block_lines = [lines[i]]
            j = i + 1
            while j < len(lines) and "|" in lines[j]:
                block_lines.append(lines[j])
                j += 1
            block = "".join(block_lines).rstrip("\n")
            key = f"<!--TABLE_{idx}-->"
            table_map[key] = block
            out.append(key + "\n")
            idx += 1
            i = j
            continue
        out.append(line)
        i += 1
    return "".join(out), table_map


def _restore_tables(text: str, table_map: dict[str, str]) -> str:
    restored = text
    for key, md in table_map.items():
        restored = restored.replace(key, md)
    return restored


def _split_text(text: str, *, chunk_size: int, chunk_overlap: int) -> list[TextNode]:
    document = Document(text=text)
    # Header-aware first for markdown-ish docs
    try:
        md_parser = MarkdownNodeParser()
        nodes = md_parser.get_nodes_from_documents([document])
    except Exception:
        nodes = [TextNode(text=text)]

    # Further split oversized nodes with sentence splitter, but never split
    # placeholders (single-token atomic units).
    splitter = SentenceSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    final: list[TextNode] = []
    for node in nodes:
        content = node.get_content()
        if _TABLE_PLACEHOLDER.fullmatch(content.strip()):
            final.append(TextNode(text=content.strip()))
            continue
        if len(content) <= chunk_size:
            final.append(TextNode(text=content))
            continue
        # If the node is mostly a table placeholder + a little text, keep together
        if _TABLE_PLACEHOLDER.search(content) and len(content) <= chunk_size * 1.5:
            final.append(TextNode(text=content))
            continue
        sub_docs = [Document(text=content)]
        final.extend(splitter.get_nodes_from_documents(sub_docs))
    return final


def _infer_section(text: str) -> str | None:
    for line in text.splitlines():
        m = re.match(r"^(#{1,6})\s+(.+)$", line.strip())
        if m:
            return m.group(2).strip()
    return None


def _infer_page(parsed: ParsedDocument, text: str) -> int | None:
    if not parsed.pages:
        return None
    if len(parsed.pages) == 1:
        return parsed.pages[0].page_number
    # Heuristic: pick the page whose text shares the most prefix overlap
    best_page = parsed.pages[0].page_number
    best_score = -1
    snippet = text[:120]
    for page in parsed.pages:
        score = 1 if snippet and snippet in page.text else 0
        if score > best_score:
            best_score = score
            best_page = page.page_number
    return best_page


def _looks_like_table(text: str) -> bool:
    lines = [ln for ln in text.splitlines() if "|" in ln]
    return len(lines) >= 2
