from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Protocol

from app.context import ContextBundle
from app.contracts import (
    EventFamily,
    Mission,
    Plan,
    Point,
    SimulationEvent,
    TrustedSnapshot,
    VerificationResult,
    Waypoint,
)
from app.errors import ErrorCode, ServiceError
from app.mission.parser import NebiusMissionParser, validate_survey_request
from app.ports import ExecutionPort, VerifierPort, WorldPort


class ProposalEngine(Protocol):
    async def propose(self, mission: Mission, snapshot: TrustedSnapshot, *, stage: str, previous: Plan | None = None, violations: list[object] | None = None, evidence: tuple[object, ...] = ()) -> Plan: ...


class ContextProvider(Protocol):
    async def context_for(self, mission: Mission) -> ContextBundle: ...


class StatusPublisher(Protocol):
    async def publish(
        self,
        mission_id: str,
        message_type: str,
        *,
        operation_id: str | None = None,
        stage: str | None = None,
        payload: dict | None = None,
    ) -> dict: ...


class StaticProposalEngine:
    """Test-only deterministic candidate generator; never wire this into production."""
    is_mock = True

    async def propose(self, mission: Mission, snapshot: TrustedSnapshot, *, stage: str, previous: Plan | None = None, violations: list[object] | None = None, evidence: tuple[object, ...] = ()) -> Plan:
        area = mission.approved_area
        points = [area[0], area[1], area[2], area[0]]
        return Plan(
            mission_id=mission.mission_id,
            revision=(previous.revision + 1 if previous else 1),
            snapshot_revision=snapshot.world_state.revision,
            parent_plan_id=previous.plan_id if previous else None,
            waypoints=[Waypoint(longitude=p.longitude, latitude=p.latitude, altitude_agl_m=50.0, speed_mps=8.0) for p in points],
        )


@dataclass
class Operation:
    operation_id: str
    mission_id: str
    mission_revision: int = 1
    status: str = "PENDING"
    attempt: int = 0
    plans: list[Plan] = field(default_factory=list)
    verdicts: list[VerificationResult] = field(default_factory=list)
    handoff_ref: str | None = None
    error: ServiceError | None = None
    context_status: str = "NOT_CONFIGURED"
    context_latency_ms: int | None = None
    context_warnings: tuple[str, ...] = ()


class MissionService:
    def __init__(self, world: WorldPort, verifier: VerifierPort, execution: ExecutionPort, engine: ProposalEngine, max_repairs: int = 3, context_provider: ContextProvider | None = None, status_publisher: StatusPublisher | None = None, mission_parser: NebiusMissionParser | None = None) -> None:
        self.world, self.verifier, self.execution, self.engine = world, verifier, execution, engine
        self.max_repairs = max_repairs
        self.context_provider = context_provider
        self.status_publisher = status_publisher
        self.mission_parser = mission_parser
        self._lock = asyncio.Lock()
        self._event_lock = asyncio.Lock()
        self.operations: dict[str, Operation] = {}
        self._request_operations: dict[tuple[str, int, str], Operation] = {}
        self._event_receipts: dict[str, dict[str, object]] = {}
        self._event_sequence: dict[str, int] = {}

    @staticmethod
    def parse_instruction(operator_instruction: str, approved_area: list, approved_location_label: str, operator_id: str) -> Mission:
        return validate_survey_request(
            operator_instruction, approved_area, approved_location_label, operator_id
        )

    async def parse(
        self,
        operator_instruction: str,
        approved_area: list[Point],
        approved_location_label: str,
        operator_id: str,
    ) -> Mission:
        if self.mission_parser is None:
            return self.parse_instruction(
                operator_instruction, approved_area, approved_location_label, operator_id
            )
        return await self.mission_parser.parse(
            operator_instruction, approved_area, approved_location_label, operator_id
        )

    async def plan(
        self,
        mission: Mission,
        operation_id: str,
        *,
        initial_stage: str = "planner",
        idempotency_key: str | None = None,
    ) -> Operation:
        request_key = (
            (mission.mission_id, mission.revision, idempotency_key)
            if idempotency_key
            else None
        )
        if request_key and request_key in self._request_operations:
            return self._request_operations[request_key]
        if self._lock.locked():
            raise ServiceError(ErrorCode.MISSION_BUSY, "another mission operation is active", True)
        async with self._lock:
            operation = Operation(
                operation_id=operation_id,
                mission_id=mission.mission_id,
                mission_revision=mission.revision,
                status="PLANNING",
            )
            self.operations[mission.mission_id] = operation
            if request_key:
                self._request_operations[request_key] = operation
            await self._publish(operation, "PLANNING_STARTED", stage=initial_stage)
            candidate: Plan | None = None
            try:
                snapshot = await self.world.get_snapshot(mission.mission_id)
                evidence: tuple[object, ...] = ()
                if self.context_provider is not None:
                    context = await self.context_provider.context_for(mission)
                    operation.context_status = context.status.value
                    operation.context_latency_ms = context.latency_ms
                    operation.context_warnings = context.warnings
                    evidence = context.items
                for attempt in range(self.max_repairs + 1):
                    operation.attempt = attempt
                    if attempt:
                        await self._publish(
                            operation,
                            "REPAIR_STARTED",
                            stage="repair",
                            payload={"attempt": attempt},
                        )
                    candidate = await self.engine.propose(mission, snapshot, stage=initial_stage if attempt == 0 else "repair", previous=candidate, violations=(operation.verdicts[-1].violations if operation.verdicts else None), evidence=evidence)
                    if candidate.mission_id != mission.mission_id or candidate.snapshot_revision != snapshot.world_state.revision:
                        raise ServiceError(ErrorCode.STATE_STALE, "candidate does not bind to current trusted snapshot")
                    operation.plans.append(candidate)
                    await self._publish(
                        operation,
                        "CANDIDATE_PROPOSED",
                        stage=initial_stage if attempt == 0 else "repair",
                        payload={"attempt": attempt, "plan_id": candidate.plan_id},
                    )
                    verdict = await self.verifier.verify(candidate, mission, snapshot)
                    operation.verdicts.append(verdict)
                    await self._publish(
                        operation,
                        "VERIFIER_RETURNED",
                        stage="verify",
                        payload={"attempt": attempt, "passed": verdict.passed},
                    )
                    if verdict.passed:
                        # Re-read the world before handoff; a verifier pass over a stale world is not usable.
                        latest = await self.world.get_snapshot(mission.mission_id)
                        if latest.world_state.revision != snapshot.world_state.revision:
                            raise ServiceError(ErrorCode.STATE_STALE, "world changed before plan handoff")
                        assert verdict.certificate is not None
                        if verdict.certificate.plan_id != candidate.plan_id or verdict.certificate.snapshot_revision != snapshot.world_state.revision:
                            raise ServiceError(ErrorCode.VERIFIER_FAILED, "certificate does not match candidate and snapshot")
                        operation.handoff_ref = await self.execution.request_plan_handoff(candidate, verdict.certificate)
                        operation.status = "VERIFIED"
                        await self._publish(
                            operation,
                            "PLAN_VERIFIED",
                            stage="handoff",
                            payload={"attempt": attempt, "handoff_ref": operation.handoff_ref},
                        )
                        return operation
                operation.status = "REJECTED"
                operation.error = ServiceError(ErrorCode.REPAIR_EXHAUSTED, "no plan passed verification within repair budget")
                await self._publish(operation, "PLANNING_REJECTED", stage="verify")
                return operation
            except ServiceError as exc:
                operation.status = "FAILED"
                operation.error = exc
                await self._publish(
                    operation,
                    "BACKEND_ERROR",
                    payload={"error_code": exc.code.value},
                )
                return operation
            except Exception:
                operation.status = "FAILED"
                operation.error = ServiceError(ErrorCode.VERIFIER_UNAVAILABLE, "verifier or trusted-world adapter failed", True)
                await self._publish(
                    operation,
                    "BACKEND_ERROR",
                    payload={"error_code": operation.error.code.value},
                )
                return operation

    async def _publish(
        self,
        operation: Operation,
        message_type: str,
        *,
        stage: str | None = None,
        payload: dict | None = None,
    ) -> None:
        if self.status_publisher is not None:
            await self.status_publisher.publish(
                operation.mission_id,
                message_type,
                operation_id=operation.operation_id,
                stage=stage,
                payload=payload,
            )

    async def receive_event(self, event: SimulationEvent, mission: Mission, operation_id: str) -> dict[str, object]:
        if event.mission_id != mission.mission_id:
            raise ServiceError(ErrorCode.VALIDATION_FAILED, "event mission does not match active mission")

        async with self._event_lock:
            if event.event_id in self._event_receipts:
                return self._event_receipts[event.event_id]
            last = self._event_sequence.get(event.mission_id, -1)
            if event.sequence <= last:
                raise ServiceError(ErrorCode.EVENT_OUT_OF_ORDER, "event sequence is not newer")
            latest = await self.world.get_snapshot(mission.mission_id)
            if latest.world_state.revision != event.state_revision:
                raise ServiceError(ErrorCode.STATE_STALE, "event does not match trusted state revision")

            if event.family is EventFamily.SURVIVOR_DETECTED:
                receipt: dict[str, object] = {
                    "status": "RECORDED_NO_REPLAN",
                    "event_id": event.event_id,
                }
            elif event.family in {EventFamily.LOW_BATTERY, EventFamily.WIND_SPIKE}:
                # The external deterministic runtime must act first. No contract currently
                # supplies the explicit permission needed for an AI contingency proposal.
                receipt = {
                    "status": "RUNTIME_ACTION_REQUIRED_NO_REPLAN",
                    "event_id": event.event_id,
                }
            else:
                if event.family is EventFamily.OPERATOR_MISSION_CHANGE:
                    previous = self.operations.get(mission.mission_id)
                    if previous and mission.revision <= previous.mission_revision:
                        raise ServiceError(
                            ErrorCode.VALIDATION_FAILED,
                            "operator mission change requires a newer approved mission revision",
                        )
                operation = await self.plan(mission, operation_id, initial_stage="replanner")
                receipt = {
                    "status": operation.status,
                    "event_id": event.event_id,
                    "operation_id": operation_id,
                }
            self._event_sequence[event.mission_id] = event.sequence
            self._event_receipts[event.event_id] = receipt
            return receipt
