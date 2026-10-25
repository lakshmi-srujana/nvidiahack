"""Finite benchmark artifact worker suitable for local or Nebius Jobs execution."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from bench.cli import aggregate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(os.environ.get("BENCH_INPUT", "/input/attempts.jsonl")),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(os.environ.get("BENCH_OUTPUT_DIR", "/output/run")),
    )
    args = parser.parse_args()
    if not args.input.is_file():
        parser.error(f"input JSONL does not exist: {args.input}")
    aggregate(args.input, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
