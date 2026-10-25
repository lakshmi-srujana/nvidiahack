from bench.metrics import percentile, summarize, summarize_by_mode


def test_metrics_preserve_unknown_denominators() -> None:
    assert summarize([])["initial_candidate_safety_pass_rate"] is None
    summary = summarize([
        {"initial_verdict": "PASS", "safe_plan_accepted": True, "latency_ms": 10},
        {"initial_verdict": "FAIL", "safe_plan_accepted": True, "latency_ms": 30},
        {"error_code": "AI_UNAVAILABLE", "safe_plan_accepted": False},
    ])
    assert summary["evaluable_initial_candidates"] == 2
    assert summary["safe_plan_acceptance_rate"] == 2 / 3
    assert summary["repair_recovery_rate"] == 1
    assert summary["raw_candidate_violation_rate"] == 0.5
    assert summary["latency_sample_count"] == 2
    assert summary["p95_latency_ms"] == 29
    assert summary["unknown_cost_record_count"] == 3


def test_percentiles_and_arm_summaries_are_deterministic() -> None:
    assert percentile([], 0.95) is None
    assert percentile([10], 0.95) == 10
    records = [
        {"mode": "RAW", "initial_verdict": "FAIL", "latency_ms": 10},
        {"mode": "GATED", "initial_verdict": "PASS", "latency_ms": 20},
    ]
    arms = summarize_by_mode(records)
    assert list(arms) == ["GATED", "RAW"]
    assert arms["RAW"]["raw_candidate_violation_rate"] == 1
