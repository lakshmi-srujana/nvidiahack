"""Paired benchmark evaluation: RAW is never an execution path."""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from enum import StrEnum
from typing import Awaitable, Callable

from app.contracts import Plan, VerificationResult
from app.errors import ServiceError


class Mode(StrEnum):
    RAW = "RAW"
    GATED = "GATED"
    FULL = "FULL"


def plan_hash(plan: Plan) -> str:
    encoded = json.dumps(plan.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(encoded.encode()).hexdigest()}"


async def evaluate(
    *,
    case_id: str,
    mode: Mode,
    initial: Plan,
    verify: Callable[[Plan], Awaitable[VerificationResult]],
    repair: Callable[[Plan, VerificationResult], Awaitable[Plan]] | None = None,
    max_repairs: int = 3,
    run_id: str = "local-run",
) -> dict[str, object]:
    """Score one stored initial candidate without ever calling an executor."""
    started = time.perf_counter()
    candidate = initial
    hashes = [plan_hash(candidate)]
    try:
        first = await verify(candidate)
    except Exception as exc:
        return {
            "run_id": run_id,
            "case_id": case_id,
            "mode": mode.value,
            "initial_plan_hash": hashes[0],
            "candidate_plan_hashes": hashes,
            "initial_verdict": None,
            "verifier_statuses": [],
            "violated_rule_ids": [],
            "safe_plan_accepted": False,
            "repair_attempts": 0,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "error_code": exc.code.value if isinstance(exc, ServiceError) else "VERIFIER_UNAVAILABLE",
            "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        }
    verdicts = ["PASS" if first.passed else "FAIL"]
    violated = [[item.rule_id for item in first.violations]]
    result: dict[str, object] = {
        "run_id": run_id,
        "case_id": case_id,
        "mode": mode.value,
        "initial_plan_hash": hashes[0],
        "candidate_plan_hashes": hashes,
        "initial_verdict": verdicts[0],
        "verifier_statuses": verdicts,
        "violated_rule_ids": violated,
        "safe_plan_accepted": False,
        "repair_attempts": 0,
        "error_code": None,
    }
    if mode is Mode.RAW:
        result["latency_ms"] = int((time.perf_counter() - started) * 1000)
        result["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        return result
    if first.passed:
        result["safe_plan_accepted"] = True
    elif mode is Mode.FULL and repair:
        for attempt in range(1, max_repairs + 1):
            try:
                candidate = await repair(candidate, first)
                hashes.append(plan_hash(candidate))
                verdict = await verify(candidate)
            except Exception as exc:
                result["error_code"] = (
                    exc.code.value if isinstance(exc, ServiceError) else "REPAIR_OR_VERIFIER_FAILED"
                )
                break
            verdicts.append("PASS" if verdict.passed else "FAIL")
            violated.append([item.rule_id for item in verdict.violations])
            result["repair_attempts"] = attempt
            if verdict.passed:
                result["safe_plan_accepted"] = True
                break
            first = verdict
    result["latency_ms"] = int((time.perf_counter() - started) * 1000)
    result["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    return result


async def evaluate_paired(
    *,
    case_id: str,
    initial: Plan,
    verify: Callable[[Plan], Awaitable[VerificationResult]],
    repair: Callable[[Plan, VerificationResult], Awaitable[Plan]] | None = None,
    max_repairs: int = 3,
    run_id: str = "local-run",
) -> list[dict[str, object]]:
    """Evaluate all arms against the same immutable initial plan bytes."""
    return [
        await evaluate(
            case_id=case_id,
            mode=mode,
            initial=initial.model_copy(deep=True),
            verify=verify,
            repair=repair,
            max_repairs=max_repairs,
            run_id=run_id,
        )
        for mode in Mode
    ]
