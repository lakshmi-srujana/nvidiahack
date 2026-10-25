from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Protocol

from app.contracts import Plan, VerificationResult
from app.errors import ServiceError
from bench.attacks import canonical_hash
from bench.report import atomic_json
from bench.runner import Mode, evaluate
from bench.schemas import AttackCase


class BenchmarkAdapter(Protocol):
    name: str
    is_mock: bool

    async def generate_initial(self, case: AttackCase) -> Plan: ...

    async def verify(self, case: AttackCase, plan: Plan) -> VerificationResult: ...

    async def repair(
        self, case: AttackCase, plan: Plan, verdict: VerificationResult
    ) -> Plan: ...

    def metadata(self) -> dict: ...


def read_records(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_records(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for record in sorted(records, key=lambda item: (item["case_id"], item["mode"])):
            handle.write(json.dumps(record, sort_keys=True, default=str) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


async def run_batch(
    *,
    cases: list[AttackCase],
    adapter: BenchmarkAdapter,
    output_dir: Path,
    run_id: str,
    modes: set[Mode] | None = None,
    max_repairs: int = 3,
    max_cases: int | None = None,
    concurrency: int = 1,
    resume: bool = False,
) -> list[dict]:
    if concurrency < 1:
        raise ValueError("concurrency must be at least one")
    selected_modes = modes or set(Mode)
    attempts_path = output_dir / "attempts.jsonl"
    existing = read_records(attempts_path) if resume else []
    completed = {(record["case_id"], record["mode"]) for record in existing}
    records = list(existing)
    output_dir.mkdir(parents=True, exist_ok=True)
    initial_dir = output_dir / "initial_candidates"
    semaphore = asyncio.Semaphore(concurrency)
    write_lock = asyncio.Lock()

    async def append(new_records: list[dict]) -> None:
        async with write_lock:
            records.extend(new_records)
            write_records(attempts_path, records)

    async def run_case(case: AttackCase) -> None:
        pending = [mode for mode in Mode if mode in selected_modes and (case.case_id, mode.value) not in completed]
        if not pending:
            return
        async with semaphore:
            initial_path = initial_dir / f"{case.case_id}.json"
            try:
                if resume and initial_path.is_file():
                    initial = Plan.model_validate_json(initial_path.read_text(encoding="utf-8"))
                elif resume and any(record["case_id"] == case.case_id for record in existing):
                    raise ValueError(
                        f"cannot resume case {case.case_id}: its stored initial candidate is missing"
                    )
                else:
                    initial = await adapter.generate_initial(case)
                    atomic_json(initial_path, initial.model_dump(mode="json"))
            except Exception as exc:
                code = exc.code.value if isinstance(exc, ServiceError) else "GENERATION_FAILED"
                await append(
                    [
                        {
                            "run_id": run_id,
                            "case_id": case.case_id,
                            "mode": mode.value,
                            "initial_plan_hash": None,
                            "candidate_plan_hashes": [],
                            "initial_verdict": None,
                            "verifier_statuses": [],
                            "violated_rule_ids": [],
                            "repair_attempts": 0,
                            "safe_plan_accepted": False,
                            "latency_ms": None,
                            "error_code": code,
                            "attack_class": case.attack_class.value,
                            "suite_version": case.suite_version,
                            "test_case_hash": canonical_hash(case.model_dump(mode="json")),
                            "adapter": adapter.name,
                        }
                        for mode in pending
                    ]
                )
                return

            case_hash = canonical_hash(case.model_dump(mode="json"))
            new_records: list[dict] = []
            for mode in pending:
                record = await evaluate(
                    case_id=case.case_id,
                    mode=mode,
                    initial=initial.model_copy(deep=True),
                    verify=lambda plan: adapter.verify(case, plan),
                    repair=lambda plan, verdict: adapter.repair(case, plan, verdict),
                    max_repairs=max_repairs,
                    run_id=run_id,
                )
                record.update(
                    {
                        "attack_class": case.attack_class.value,
                        "suite_version": case.suite_version,
                        "test_case_hash": case_hash,
                        "adapter": adapter.name,
                    }
                )
                record_metadata = getattr(adapter, "record_metadata", None)
                if callable(record_metadata):
                    extra = record_metadata(case, mode)
                    if isinstance(extra, dict):
                        allowed = {
                            "llm_input_tokens",
                            "llm_output_tokens",
                            "estimated_model_cost_usd",
                            "tavily_calls",
                            "prompt_revisions",
                            "models_used",
                        }
                        record.update({key: value for key, value in extra.items() if key in allowed})
                new_records.append(record)
            await append(new_records)

    selected_cases = cases[:max_cases] if max_cases is not None else cases
    await asyncio.gather(*(run_case(case) for case in selected_cases))
    write_records(attempts_path, records)
    return sorted(records, key=lambda item: (item["case_id"], item["mode"]))
