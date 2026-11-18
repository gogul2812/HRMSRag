#!/usr/bin/env python3
"""
Stage 3 pipeline runner (Module 9).

Usage (from rag-platform/ai-core):
  python run_pipeline.py samples/sample_project.md
  python run_pipeline.py samples/sample_table.pdf
  python run_pipeline.py samples/sample_scanned.png

Prints chunks and embedding dimensions to the console — no API, no database.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

from rag_platform_chunking import chunk
from rag_platform_embedding import embed_texts
from rag_platform_parsing import parse


def run(path: Path, *, tenant_id: str, doc_id: str) -> dict:
    file_bytes = path.read_bytes()
    parsed = parse(file_bytes, path.name)
    chunks = chunk(parsed, doc_id=doc_id, tenant_id=tenant_id)
    vectors = embed_texts([c.text for c in chunks]) if chunks else []

    print("=" * 72)
    print(f"FILE: {path.name}")
    print(f"parser: {parsed.metadata.extra.get('parser')}")
    print(f"pages: {parsed.metadata.page_count}  tables: {len(parsed.tables)}")
    print(f"chunks: {len(chunks)}")
    print("-" * 72)

    for c, vec in zip(chunks, vectors, strict=True):
        preview = c.text.replace("\n", "\\n")
        if len(preview) > 180:
            preview = preview[:180] + "…"
        print(
            f"[chunk {c.chunk_index}] section={c.section!r} page={c.page} "
            f"dim={len(vec)} table={c.metadata.get('contains_table')}"
        )
        print(f"  {preview}")
        # Prove mid-row integrity: every table row line still has balanced pipes
        if c.metadata.get("contains_table"):
            _assert_table_rows_intact(c.text)

    if vectors:
        dims = {len(v) for v in vectors}
        print("-" * 72)
        print(f"embedding dims: {dims}  (expected {{1024}})")
        if dims != {1024}:
            raise SystemExit(f"FATAL: expected 1024-dim vectors, got {dims}")

    print("=" * 72)
    return {
        "filename": path.name,
        "chunk_count": len(chunks),
        "table_count": len(parsed.tables),
        "embedding_dims": [len(v) for v in vectors],
    }


def _assert_table_rows_intact(text: str) -> None:
    for line in text.splitlines():
        if "|" not in line:
            continue
        # Separator or header/data row — must not be a truncated mid-cell fragment
        # without closing pipe structure.
        stripped = line.strip()
        if stripped.startswith("|") and not stripped.endswith("|"):
            raise SystemExit(f"Broken table row detected: {line!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stage 3 parse→chunk→embed runner")
    parser.add_argument("file", type=Path, help="Path to .md / .pdf / image sample")
    parser.add_argument("--tenant-id", default="demo-tenant")
    parser.add_argument("--doc-id", default=None)
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args(argv)

    path = args.file
    if not path.is_file():
        print(f"File not found: {path}", file=sys.stderr)
        return 1

    summary = run(
        path,
        tenant_id=args.tenant_id,
        doc_id=args.doc_id or str(uuid.uuid4()),
    )
    if args.json_summary:
        print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
