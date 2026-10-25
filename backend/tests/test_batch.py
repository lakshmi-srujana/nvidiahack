from pathlib import Path

import pytest

from bench.attacks import load_suite
from bench.batch import run_batch
from bench.cli import aggregate
from bench.fixture_adapter import FixtureBenchmarkAdapter
from bench.runner import Mode


class CountingAdapter(FixtureBenchmarkAdapter):
    def __init__(self) -> None:
        self.generated = 0

    async def generate_initial(self, case):
        self.generated += 1
        return await super().generate_initial(case)


@pytest.mark.asyncio
async def test_batch_runner_is_paired_bounded_and_resumable(tmp_path: Path) -> None:
    suite = Path(__file__).resolve().parents[1] / "bench" / "cases" / "fixed-v1.jsonl"
    cases, _ = load_suite(suite)
    adapter = CountingAdapter()
    records = await run_batch(
        cases=cases,
        adapter=adapter,
        output_dir=tmp_path,
        run_id="batch-test",
        max_cases=3,
        concurrency=2,
    )

    assert len(records) == 9
    assert adapter.generated == 3
    for case_id in {record["case_id"] for record in records}:
        hashes = {
            record["initial_plan_hash"]
            for record in records
            if record["case_id"] == case_id
        }
        assert len(hashes) == 1

    resumed = await run_batch(
        cases=cases,
        adapter=adapter,
        output_dir=tmp_path,
        run_id="batch-test",
        max_cases=3,
        concurrency=2,
        resume=True,
    )
    assert len(resumed) == 9
    assert adapter.generated == 3

    scoreboard = aggregate(tmp_path / "attempts.jsonl", tmp_path)
    assert scoreboard["source_record_count"] == 9
    assert "BENIGN_CONTROL" in scoreboard["breakdowns"]["by_attack_class"]
    assert (tmp_path / "attempts.csv").is_file()
    assert (tmp_path / "run_manifest.json").is_file()


@pytest.mark.asyncio
async def test_resume_does_not_regenerate_a_missing_paired_candidate(tmp_path: Path) -> None:
    suite = Path(__file__).resolve().parents[1] / "bench" / "cases" / "fixed-v1.jsonl"
    cases, _ = load_suite(suite)
    adapter = CountingAdapter()
    await run_batch(
        cases=cases,
        adapter=adapter,
        output_dir=tmp_path,
        run_id="batch-test",
        max_cases=1,
        modes={Mode.RAW},
    )
    (tmp_path / "initial_candidates" / f"{cases[0].case_id}.json").unlink()

    records = await run_batch(
        cases=cases,
        adapter=adapter,
        output_dir=tmp_path,
        run_id="batch-test",
        max_cases=1,
        resume=True,
    )

    assert adapter.generated == 1
    failed = [record for record in records if record["mode"] != "RAW"]
    assert len(failed) == 2
    assert {record["error_code"] for record in failed} == {"GENERATION_FAILED"}
