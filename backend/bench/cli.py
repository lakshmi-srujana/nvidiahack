from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from bench.metrics import summarize, summarize_by_mode
from bench.report import atomic_json


def aggregate(input_path: Path, output_dir: Path) -> dict:
    records = [
        json.loads(line)
        for line in input_path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    source_bytes = input_path.read_bytes()
    scoreboard = {
        "metrics": summarize(records),
        "arms": summarize_by_mode(records),
        "source_record_count": len(records),
        "source_sha256": f"sha256:{hashlib.sha256(source_bytes).hexdigest()}",
    }
    atomic_json(output_dir / "scoreboard.json", scoreboard)
    atomic_json(
        output_dir / "run_manifest.json",
        {
            "run_id": output_dir.name,
            "source": input_path.name,
            "source_sha256": scoreboard["source_sha256"],
            "record_count": len(records),
            "modes": sorted(scoreboard["arms"]),
        },
    )
    atomic_json(output_dir / "results.json", {"records": records})
    return scoreboard


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate already-recorded SkyWarden benchmark traces")
    parser.add_argument("aggregate", nargs="?")
    parser.add_argument("--input", type=Path, required=True, help="JSONL per-attempt records")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    aggregate(args.input, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
