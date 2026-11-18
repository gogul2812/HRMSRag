"""CLI: rag-load fallback | ingest | chat"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from rag_platform_evals.load.runner import (
    bulk_ingest,
    concurrent_chat,
    simulate_fallback_storm,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RAG Platform load tests")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_fb = sub.add_parser("fallback", help="Concurrent fake-router primary-fail fallback")
    p_fb.add_argument("--rounds", type=int, default=20)

    p_ing = sub.add_parser("ingest", help="Bulk upload files via gateway")
    p_ing.add_argument("--dir", required=True, help="Directory of files to upload")
    p_ing.add_argument("--token", default=os.environ.get("EVAL_JWT", ""))
    p_ing.add_argument("--base-url", default=os.environ.get("EVAL_API_BASE_URL", "http://localhost:8000"))
    p_ing.add_argument("--concurrency", type=int, default=8)
    p_ing.add_argument("--limit", type=int, default=100)

    p_chat = sub.add_parser("chat", help="Concurrent chat sessions")
    p_chat.add_argument("--token", action="append", default=[], help="JWT (repeat for multi-tenant)")
    p_chat.add_argument("--base-url", default=os.environ.get("EVAL_API_BASE_URL", "http://localhost:8000"))
    p_chat.add_argument("--concurrency", type=int, default=10)
    p_chat.add_argument(
        "--query",
        action="append",
        default=[],
        help="Chat query (repeatable)",
    )

    args = parser.parse_args(argv)
    results_dir = Path(__file__).resolve().parents[3] / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    if args.cmd == "fallback":
        result = asyncio.run(simulate_fallback_storm(rounds=args.rounds))
    elif args.cmd == "ingest":
        if not args.token:
            raise SystemExit("Provide --token or EVAL_JWT")
        root = Path(args.dir)
        files = [p for p in root.rglob("*") if p.is_file()][: args.limit]
        # Pad to 100 by repeating if needed (simulates bulk volume)
        while len(files) < min(args.limit, 100) and files:
            files.append(files[len(files) % len(set(files) or files)])
        result = asyncio.run(
            bulk_ingest(
                base_url=args.base_url,
                token=args.token,
                files=files[: args.limit],
                concurrency=args.concurrency,
            )
        )
    else:
        tokens = args.token or ([os.environ["EVAL_JWT"]] if os.environ.get("EVAL_JWT") else [])
        if not tokens:
            raise SystemExit("Provide --token or EVAL_JWT")
        queries = args.query or [
            "What tech stack does Project Phoenix use?",
            "Who specializes in FHIR on Phoenix?",
            "What is the target go-live?",
        ]
        result = asyncio.run(
            concurrent_chat(
                base_url=args.base_url,
                tokens=tokens,
                queries=queries * max(1, args.concurrency // len(queries)),
                concurrency=args.concurrency,
            )
        )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "result": result.to_dict(),
    }
    out = results_dir / f"load-{result.name}.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2))
    print(f"wrote {out}")
    return 0 if result.failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
