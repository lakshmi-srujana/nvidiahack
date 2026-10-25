import pytest

from app.contracts import Certificate, Plan, VerificationResult, Waypoint
from bench.runner import Mode, evaluate, evaluate_paired


def plan() -> Plan:
    return Plan(
        mission_id="mission",
        revision=1,
        snapshot_revision="world-1",
        waypoints=[
            Waypoint(longitude=77.58, latitude=12.96, altitude_agl_m=50, speed_mps=8),
            Waypoint(longitude=77.59, latitude=12.97, altitude_agl_m=50, speed_mps=8),
        ],
    )


@pytest.mark.asyncio
async def test_raw_never_admits_even_a_passing_candidate() -> None:
    candidate = plan()

    async def verifier(value: Plan) -> VerificationResult:
        return VerificationResult(
            passed=True,
            certificate=Certificate(
                certificate_ref="external",
                plan_id=value.plan_id,
                snapshot_revision="world-1",
                issuer="verifier",
            ),
        )

    record = await evaluate(case_id="case", mode=Mode.RAW, initial=candidate, verify=verifier)
    assert record["initial_verdict"] == "PASS"
    assert record["safe_plan_accepted"] is False


@pytest.mark.asyncio
async def test_paired_arms_share_identical_initial_candidate() -> None:
    candidate = plan()

    async def verifier(value: Plan) -> VerificationResult:
        return VerificationResult(
            passed=True,
            certificate=Certificate(
                certificate_ref="external",
                plan_id=value.plan_id,
                snapshot_revision="world-1",
                issuer="verifier",
            ),
        )

    records = await evaluate_paired(
        case_id="paired-case", initial=candidate, verify=verifier
    )
    assert [record["mode"] for record in records] == ["RAW", "GATED", "FULL"]
    assert len({record["initial_plan_hash"] for record in records}) == 1
    assert records[0]["safe_plan_accepted"] is False
    assert records[1]["safe_plan_accepted"] is True
    assert records[2]["safe_plan_accepted"] is True


@pytest.mark.asyncio
async def test_verifier_exception_is_recorded_not_dropped() -> None:
    async def broken_verifier(_value: Plan) -> VerificationResult:
        raise RuntimeError("offline")

    record = await evaluate(
        case_id="failure", mode=Mode.GATED, initial=plan(), verify=broken_verifier
    )
    assert record["initial_verdict"] is None
    assert record["error_code"] == "VERIFIER_UNAVAILABLE"
    assert record["safe_plan_accepted"] is False
