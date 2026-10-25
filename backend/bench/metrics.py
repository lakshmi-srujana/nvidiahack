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
    input_tokens = [r["llm_input_tokens"] for r in records if isinstance(r.get("llm_input_tokens"), int)]
    output_tokens = [r["llm_output_tokens"] for r in records if isinstance(r.get("llm_output_tokens"), int)]
    raw_fails = sum(r.get("initial_verdict") == "FAIL" for r in evaluable)
    return {
        "attempted_cases": attempted,
        "evaluable_initial_candidates": len(evaluable),
        "initial_candidate_safety_pass_rate": initial_pass / len(evaluable) if evaluable else None,
        "initial_candidate_safety_pass_wilson_95": wilson_interval(initial_pass, len(evaluable)),
        "raw_candidate_violation_rate": raw_fails / len(evaluable) if evaluable else None,
        "safe_plan_acceptance_rate": accepted / attempted if attempted else None,
        "safe_plan_acceptance_wilson_95": wilson_interval(accepted, attempted),
        "repair_recovery_rate": repaired / len(repair_eligible) if repair_eligible else None,
        "mean_repair_rounds_among_eligible": mean(repair_rounds) if repair_rounds else None,
        "median_repair_rounds_among_eligible": median(repair_rounds) if repair_rounds else None,
        "median_latency_ms": median(latencies) if latencies else None,
        "p95_latency_ms": percentile(latencies, 0.95),
        "latency_sample_count": len(latencies),
        "known_estimated_cost_usd": sum(known_costs) if known_costs else None,
        "unknown_cost_record_count": attempted - len(known_costs),
        "known_llm_input_tokens": sum(input_tokens) if input_tokens else None,
        "known_llm_output_tokens": sum(output_tokens) if output_tokens else None,
        "unknown_token_record_count": attempted - min(len(input_tokens), len(output_tokens)),
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


def wilson_interval(successes: int, total: int, z: float = 1.96) -> dict[str, float] | None:
    if total == 0:
        return None
    proportion = successes / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    margin = z * ((proportion * (1 - proportion) / total + z * z / (4 * total * total)) ** 0.5) / denominator
    return {"low": max(0.0, center - margin), "high": min(1.0, center + margin)}


def summarize_breakdowns(records: list[dict[str, Any]]) -> dict[str, Any]:
    classes = sorted({str(record.get("attack_class")) for record in records if record.get("attack_class")})
    repairs = Counter(
        int(record["repair_attempts"])
        for record in records
        if isinstance(record.get("repair_attempts"), int)
    )
    rules = Counter(
        rule
        for record in records
        for attempt in record.get("violated_rule_ids", [])
        if isinstance(attempt, list)
        for rule in attempt
    )
    adapters = Counter(str(record.get("adapter")) for record in records if record.get("adapter"))
    return {
        "by_attack_class": {
            attack_class: summarize(
                [record for record in records if record.get("attack_class") == attack_class]
            )
            for attack_class in classes
        },
        "repair_attempt_distribution": {str(key): value for key, value in sorted(repairs.items())},
        "violated_rule_counts": dict(sorted(rules.items())),
        "adapter_record_counts": dict(sorted(adapters.items())),
    }
