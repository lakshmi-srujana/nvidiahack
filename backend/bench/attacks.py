from __future__ import annotations

import hashlib
import json
from pathlib import Path

from bench.schemas import AttackCase


def canonical_hash(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def load_suite(path: Path) -> tuple[list[AttackCase], dict[str, str]]:
    cases: list[AttackCase] = []
    hashes: dict[str, str] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            case = AttackCase.model_validate_json(line)
        except Exception as exc:
            raise ValueError(f"invalid attack case at {path}:{line_number}") from exc
        if case.case_id in hashes:
            raise ValueError(f"duplicate case_id: {case.case_id}")
        cases.append(case)
        hashes[case.case_id] = canonical_hash(case.model_dump(mode="json"))
    if not cases:
        raise ValueError("attack suite is empty")
    return cases, hashes


def suite_hash(hashes: dict[str, str]) -> str:
    return canonical_hash(dict(sorted(hashes.items())))
