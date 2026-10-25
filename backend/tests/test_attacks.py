from pathlib import Path

import pytest

from bench.attacks import load_suite, suite_hash


def test_fixed_attack_suite_is_valid_and_unique() -> None:
    path = Path(__file__).resolve().parents[1] / "bench" / "cases" / "fixed-v1.jsonl"
    cases, hashes = load_suite(path)
    assert len(cases) >= 30
    assert len(hashes) == len(cases)
    assert len({case.attack_class for case in cases}) >= 12
    assert suite_hash(hashes).startswith("sha256:")


def test_duplicate_case_ids_are_rejected(tmp_path: Path) -> None:
    row = '{"case_id":"duplicate-case","suite_version":"v1","attack_class":"BENIGN_CONTROL","expected_behavior":"PASS"}'
    path = tmp_path / "duplicates.jsonl"
    path.write_text(f"{row}\n{row}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate case_id"):
        load_suite(path)
