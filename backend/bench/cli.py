from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from bench.metrics import summarize, summarize_breakdowns, summarize_by_mode
from bench.report import atomic_csv, atomic_json


def git_metadata() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[2]

    def command(*args: str) -> str | None:
        completed = subprocess.run(
            ["git", *args], cwd=root, text=True, capture_output=True, check=False
        )
        return completed.stdout.strip() if completed.returncode == 0 else None

    status = command("status", "--porcelain")
    return {
        "commit_sha": command("rev-parse", "HEAD"),
        "branch": command("branch", "--show-current"),
        "working_tree_dirty": bool(status) if status is not None else None,
    }


def aggregate(
    input_path: Path,
    output_dir: Path,
    manifest_metadata: dict[str, Any] | None = None,
) -> dict:
    records = [
        json.loads(line)
        for line in input_path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    source_bytes = input_path.read_bytes()
    scoreboard = {
        "metrics": summarize(records),
        "arms": summarize_by_mode(records),
        "breakdowns": summarize_breakdowns(records),
        "source_record_count": len(records),
        "source_sha256": f"sha256:{hashlib.sha256(source_bytes).hexdigest()}",
    }
    atomic_json(output_dir / "scoreboard.json", scoreboard)
    manifest = {
        "run_id": output_dir.name,
        "source": input_path.name,
        "source_sha256": scoreboard["source_sha256"],
        "record_count": len(records),
        "modes": sorted(scoreboard["arms"]),
        "git": git_metadata(),
    }
    if manifest_metadata:
        manifest.update(manifest_metadata)
    atomic_json(output_dir / "run_manifest.json", manifest)
    atomic_json(output_dir / "results.json", {"records": records})
    atomic_csv(output_dir / "attempts.csv", records)
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
