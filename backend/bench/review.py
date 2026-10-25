from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from bench.attacks import load_suite, suite_hash
from bench.report import atomic_json


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Record explicit human approval of an immutable attack suite"
    )
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--approve",
        action="store_true",
        help="Confirm every case and expected behavior was manually reviewed",
    )
    args = parser.parse_args()
    if not args.approve:
        parser.error("--approve is required after manual case review")
    cases, hashes = load_suite(args.suite)
    classes = sorted({case.attack_class.value for case in cases})
    benign = sum("benign" in case.validity_tags for case in cases)
    atomic_json(
        args.output,
        {
            "status": "APPROVED",
            "reviewer": args.reviewer,
            "reviewed_at_utc": datetime.now(timezone.utc).isoformat(),
            "suite": args.suite.name,
            "suite_sha256": suite_hash(hashes),
            "case_count": len(cases),
            "attack_classes": classes,
            "benign_control_count": benign,
            "case_hashes": hashes,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
