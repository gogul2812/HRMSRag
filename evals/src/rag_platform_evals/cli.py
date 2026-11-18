"""CLI: rag-eval --dataset sample_healthcare.json [--live] [--out baseline.json]"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from rag_platform_evals.runner import DATASETS_DIR, load_dataset, run_live, run_offline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RAG Platform evaluation runner")
    parser.add_argument(
        "--dataset",
        default="sample_healthcare.json",
        help="Dataset filename under evals/datasets/ or absolute path",
    )
    parser.add_argument("--live", action="store_true", help="Call live orchestrator API")
    parser.add_argument(
        "--out",
        default="",
        help="Write JSON report path (default: evals/results/<tenant>-<mode>.json)",
    )
    args = parser.parse_args(argv)

    dataset_path = Path(args.dataset)
    if not dataset_path.is_file():
        dataset_path = DATASETS_DIR / args.dataset
    dataset = load_dataset(dataset_path)

    if args.live:
        report = asyncio.run(run_live(dataset))
    else:
        report = run_offline(dataset)

    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    report["dataset"] = str(dataset_path.name)

    out = Path(args.out) if args.out else (
        Path(__file__).resolve().parents[2]
        / "results"
        / f"{report['tenant_key']}-{report['mode']}.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"tenant={report['tenant_key']} mode={report['mode']}")
    print(f"faithfulness_mean={report['faithfulness_mean']}")
    print(f"answer_relevancy_mean={report['answer_relevancy_mean']}")
    print(f"context_precision_mean={report['context_precision_mean']}")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
