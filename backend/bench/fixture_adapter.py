"""Explicitly fake adapter for pipeline tests; never use its metrics as project results."""
from __future__ import annotations

from app.contracts import Certificate, Plan, VerificationResult, Violation, Waypoint
from bench.schemas import AttackCase, AttackClass


class FixtureBenchmarkAdapter:
    name = "fixture-test-only"
    is_mock = True

    async def generate_initial(self, case: AttackCase) -> Plan:
        return Plan(
            mission_id=case.case_id,
            revision=1,
            snapshot_revision="fixture-world-1",
            waypoints=[
                Waypoint(longitude=77.58, latitude=12.96, altitude_agl_m=50, speed_mps=8),
                Waypoint(longitude=77.59, latitude=12.97, altitude_agl_m=50, speed_mps=8),
            ],
        )

    async def verify(self, case: AttackCase, plan: Plan) -> VerificationResult:
        if case.attack_class is AttackClass.BENIGN_CONTROL or plan.revision > 1:
            return VerificationResult(
                passed=True,
                certificate=Certificate(
                    certificate_ref="TEST-ONLY-BENCH-CERTIFICATE",
                    plan_id=plan.plan_id,
                    snapshot_revision=plan.snapshot_revision,
                    issuer="fixture-test-only",
                ),
            )
        return VerificationResult(
            passed=False,
            violations=[
                Violation(rule_id=case.attack_class.value, message="scripted fixture rejection")
            ],
        )

    async def repair(
        self, case: AttackCase, plan: Plan, verdict: VerificationResult
    ) -> Plan:
        return Plan(
            mission_id=plan.mission_id,
            revision=plan.revision + 1,
            snapshot_revision=plan.snapshot_revision,
            parent_plan_id=plan.plan_id,
            waypoints=[waypoint.model_copy(deep=True) for waypoint in plan.waypoints],
        )

    def metadata(self) -> dict:
        return {"adapter": self.name, "mock": True, "warning": "DO_NOT_PUBLISH_AS_REAL_RESULTS"}

    def record_metadata(self, case: AttackCase, mode) -> dict:
        return {
            "llm_input_tokens": None,
            "llm_output_tokens": None,
            "estimated_model_cost_usd": None,
            "tavily_calls": 0,
            "prompt_revisions": [],
            "models_used": [],
        }


def create() -> FixtureBenchmarkAdapter:
    return FixtureBenchmarkAdapter()
