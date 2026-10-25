import json
from pathlib import Path

import pytest

from bench.attacks import load_suite, suite_hash, validate_review_manifest


def test_review_manifest_must_match_current_suite(tmp_path: Path) -> None:
    suite = Path(__file__).resolve().parents[1] / "bench" / "cases" / "fixed-v1.jsonl"
    _, hashes = load_suite(suite)
    expected = suite_hash(hashes)
    manifest = tmp_path / "review.json"
    manifest.write_text(
        json.dumps(
            {
                "status": "APPROVED",
                "reviewer": "reviewer",
                "reviewed_at_utc": "2026-10-26T00:00:00Z",
                "suite_sha256": expected,
            }
        ),
        encoding="utf-8",
    )
    assert validate_review_manifest(manifest, expected)["reviewer"] == "reviewer"
    with pytest.raises(ValueError, match="changed after review"):
        validate_review_manifest(manifest, "sha256:different")
