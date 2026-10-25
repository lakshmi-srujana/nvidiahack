from __future__ import annotations

from typing import Protocol

from app.contracts import (
    Certificate,
    DroneState,
    Mission,
    Plan,
    Point,
    SafetyPolicy,
    TrustedSnapshot,
    VerificationResult,
    WorldState,
)


class WorldPort(Protocol):
    async def get_snapshot(self, mission_id: str) -> TrustedSnapshot: ...


class VerifierPort(Protocol):
    async def verify(self, plan: Plan, mission: Mission, snapshot: TrustedSnapshot) -> VerificationResult: ...


class ExecutionPort(Protocol):
    async def request_plan_handoff(self, plan: Plan, certificate: Certificate) -> str: ...


class MockWorldPort:
    """Development/test fixture only; it cannot be wired in production."""
    is_mock = True

    def __init__(self, revision: str = "world-1") -> None:
        self.snapshot = TrustedSnapshot(
            drone_state=DroneState(position=Point(longitude=77.59, latitude=12.97), battery_percent=85),
            world_state=WorldState(revision=revision),
            safety_policy=SafetyPolicy(revision="policy-1", reference="test-policy"),
        )

    async def get_snapshot(self, mission_id: str) -> TrustedSnapshot:
        return self.snapshot.model_copy(deep=True)


class MockVerifierPort:
    """Scriptable verifier fixture. It does not implement any flight-safety rules."""
    is_mock = True

    def __init__(self, verdicts: list[VerificationResult] | None = None) -> None:
        self.verdicts = list(verdicts or [])
        self.calls: list[Plan] = []

    async def verify(self, plan: Plan, mission: Mission, snapshot: TrustedSnapshot) -> VerificationResult:
        self.calls.append(plan)
        if self.verdicts:
            return self.verdicts.pop(0)
        return VerificationResult(
            passed=True,
            certificate=Certificate(
                certificate_ref="TEST-ONLY-CERTIFICATE",
                plan_id=plan.plan_id,
                snapshot_revision=snapshot.world_state.revision,
                issuer="test-mock-verifier",
            ),
        )


class MockExecutionPort:
    is_mock = True

    def __init__(self) -> None:
        self.handoffs: list[tuple[Plan, Certificate]] = []

    async def request_plan_handoff(self, plan: Plan, certificate: Certificate) -> str:
        if certificate.plan_id != plan.plan_id:
            raise ValueError("certificate does not authorize this plan")
        self.handoffs.append((plan, certificate))
        return f"test-handoff:{plan.plan_id}"
