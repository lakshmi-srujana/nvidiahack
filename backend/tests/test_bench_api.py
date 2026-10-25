import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from bench.cli import aggregate


def create_run(tmp_path: Path) -> Path:
    attempts = tmp_path / "attempts.jsonl"
    attempts.write_text(
        json.dumps(
            {
                "run_id": "run-1",
                "case_id": "case-1",
                "mode": "RAW",
                "initial_verdict": "FAIL",
                "safe_plan_accepted": False,
                "repair_attempts": 0,
                "latency_ms": 12,
                "error_code": None,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "run-1"
    aggregate(attempts, output)
    return output


def test_aggregation_is_deterministic_and_writes_manifest(tmp_path: Path) -> None:
    output = create_run(tmp_path)
    first = (output / "scoreboard.json").read_bytes()
    aggregate(tmp_path / "attempts.jsonl", output)
    second = (output / "scoreboard.json").read_bytes()
    assert first == second
    manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["record_count"] == 1
    assert manifest["modes"] == ["RAW"]


def test_benchmark_artifact_endpoints(tmp_path: Path) -> None:
    create_run(tmp_path)
    settings = Settings(app_mode="test", bench_output_root=tmp_path, _env_file=None)
    with TestClient(create_app(settings)) as client:
        listed = client.get("/api/v1/benchmarks")
        summary = client.get("/api/v1/benchmarks/run-1")
        scoreboard = client.get("/api/v1/benchmarks/run-1/scoreboard")
        case = client.get("/api/v1/benchmarks/run-1/cases/case-1")
        traversal = client.get("/api/v1/benchmarks/../scoreboard")

    assert listed.json()["runs"][0]["run_id"] == "run-1"
    assert summary.json()["manifest"]["record_count"] == 1
    assert scoreboard.json()["source_record_count"] == 1
    assert case.json()["records"][0]["case_id"] == "case-1"
    assert traversal.status_code == 404
