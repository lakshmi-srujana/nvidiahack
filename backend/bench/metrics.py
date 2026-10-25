from __future__ import annotations

from collections import Counter
from statistics import mean, median
from typing import Any


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Keep unavailable/non-evaluable outcomes visible rather than inventing zeros."""
    attempted = len(records)
    evaluable = [r for r in records if r.get("initial_verdict") in {"PASS", "FAIL"}]
    initial_pass = sum(r["initial_verdict"] == "PASS" for r in evaluable)
    accepted = sum(bool(r.get("safe_plan_accepted")) for r in records)
    repair_eligible = [r for r in records if r.get("initial_verdict") == "FAIL"]
    repaired = sum(bool(r.get("safe_plan_accepted")) for r in repair_eligible)
    latencies = [r["latency_ms"] for r in records if isinstance(r.get("latency_ms"), (int, float))]
    repair_rounds = [r["repair_attempts"] for r in repair_eligible if isinstance(r.get("repair_attempts"), int)]
    known_costs = [r["estimated_model_cost_usd"] for r in records if isinstance(r.get("estimated_model_cost_usd"), (int, float))]
    raw_fails = sum(r.get("initial_verdict") == "FAIL" for r in evaluable)
    return {
        "attempted_cases": attempted,
        "evaluable_initial_candidates": len(evaluable),
        "initial_candidate_safety_pass_rate": initial_pass / len(evaluable) if evaluable else None,
        "raw_candidate_violation_rate": raw_fails / len(evaluable) if evaluable else None,
        "safe_plan_acceptance_rate": accepted / attempted if attempted else None,
        "repair_recovery_rate": repaired / len(repair_eligible) if repair_eligible else None,
        "mean_repair_rounds_among_eligible": mean(repair_rounds) if repair_rounds else None,
        "median_repair_rounds_among_eligible": median(repair_rounds) if repair_rounds else None,
        "median_latency_ms": median(latencies) if latencies else None,
        "p95_latency_ms": percentile(latencies, 0.95),
        "latency_sample_count": len(latencies),
        "known_estimated_cost_usd": sum(known_costs) if known_costs else None,
        "unknown_cost_record_count": attempted - len(known_costs),
        "error_counts": dict(Counter(r.get("error_code") for r in records if r.get("error_code"))),
    }


def percentile(values: list[int | float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def summarize_by_mode(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    modes = sorted({str(record.get("mode")) for record in records if record.get("mode")})
    return {mode: summarize([record for record in records if record.get("mode") == mode]) for mode in modes}
