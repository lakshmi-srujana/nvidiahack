"""Finite benchmark artifact worker suitable for local or Nebius Jobs execution."""
from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from bench.adapter_loader import load_adapter
from bench.attacks import load_suite, suite_hash, validate_review_manifest
from bench.batch import run_batch
from bench.cli import aggregate
from bench.runner import Mode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(os.environ["BENCH_INPUT"]) if os.environ.get("BENCH_INPUT") else None,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(os.environ.get("BENCH_OUTPUT_DIR", "/output/run")),
    )
    parser.add_argument(
        "--suite",
        type=Path,
        default=Path(os.environ["BENCH_SUITE"]) if os.environ.get("BENCH_SUITE") else None,
    )
    parser.add_argument("--adapter", default=os.environ.get("BENCH_ADAPTER"))
    parser.add_argument("--run-id", default=os.environ.get("BENCH_RUN_ID", "job-run"))
    parser.add_argument("--mode", action="append", choices=[mode.value for mode in Mode])
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--max-repairs", type=int, default=3)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--allow-mock", action="store_true")
    parser.add_argument(
        "--review-manifest",
        type=Path,
        default=(
            Path(os.environ["BENCH_REVIEW_MANIFEST"])
            if os.environ.get("BENCH_REVIEW_MANIFEST")
            else None
        ),
    )
    args = parser.parse_args()
    if args.suite:
        if not args.adapter:
            parser.error("--adapter is required with --suite")
        cases, hashes = load_suite(args.suite)
        adapter = load_adapter(args.adapter)
        if adapter.is_mock and not args.allow_mock:
            parser.error("mock benchmark adapters require --allow-mock")
        current_suite_hash = suite_hash(hashes)
        review = None
        if not adapter.is_mock:
            if not args.review_manifest:
                parser.error("real scored runs require --review-manifest")
            review = validate_review_manifest(args.review_manifest, current_suite_hash)
        modes = {Mode(value) for value in args.mode} if args.mode else set(Mode)
        asyncio.run(
            run_batch(
                cases=cases,
                adapter=adapter,
                output_dir=args.output_dir,
                run_id=args.run_id,
                modes=modes,
                max_repairs=args.max_repairs,
                max_cases=args.max_cases,
                concurrency=args.concurrency,
                resume=args.resume,
            )
        )
        aggregate(
            args.output_dir / "attempts.jsonl",
            args.output_dir,
            manifest_metadata={
                "run_id": args.run_id,
                "suite": args.suite.name,
                "suite_sha256": current_suite_hash,
                "suite_review": review,
                "adapter": adapter.metadata(),
                "job_worker": True,
            },
        )
    elif args.input and args.input.is_file():
        aggregate(args.input, args.output_dir)
    else:
        parser.error("provide an existing --input or a --suite with --adapter")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
