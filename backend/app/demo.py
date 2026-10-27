"""Local, single-drone integration of the AI proposal and simulator components.

The sample policies and scenarios are prototype assumptions, not approved flight rules.
"""
# ruff: noqa: E402
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, model_validator

# The simulator packages live at the repository root; in the container they
# are copied next to app/ instead.
repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from simulator.engine import MissionSimulator
from simulator.scenarios import (
    create_battery_critical_scenario,
    create_dam_breach_scenario,
    create_flood_scenario,
    create_high_wind_scenario,
)
from verifier.engine import SafetyVerifier
from verifier.models import GeoPolygon, SimulationEventType
from verifier.models import Plan as SafetyPlan
from verifier.models import Waypoint as SafetyWaypoint
from verifier.rules import haversine_distance_m

from app.contracts import (
    Certificate,
    DroneState,
    Mission,
    Plan,
    Point,
    SafetyPolicy,
    TrustedSnapshot,
    VerificationResult,
    Violation,
    WorldState,
)
from app.llm.router import ModelRouter
from app.mission.nebius_engine import NebiusProposalEngine
from app.mission.service import MissionService

SCENARIOS = {
    "flood": create_flood_scenario,
    "dam": create_dam_breach_scenario,
    "wind": create_high_wind_scenario,
    "battery": create_battery_critical_scenario,
}


class EventInput(BaseModel):
    family: str


class SurveyInput(BaseModel):
    instruction: str = Field(min_length=1, max_length=1000)
    west: float = Field(ge=-180, le=180)
    east: float = Field(ge=-180, le=180)
    south: float = Field(ge=-90, le=90)
    north: float = Field(ge=-90, le=90)

    @model_validator(mode="after")
    def rectangle_is_ordered(self):
        if self.west >= self.east or self.south >= self.north:
            raise ValueError("West must be less than east and south must be less than north")
        if self.east - self.west > 0.1 or self.north - self.south > 0.1:
            raise ValueError("Demo survey area must be within 0.1 degrees per side")
        return self


class DemoRuntime:
    """All state is server-side and deliberately process-local for the demo."""

    is_mock = False

    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.load("flood")

    def load(self, name: str) -> None:
        if name not in SCENARIOS:
            raise HTTPException(404, "Unknown scenario")
        self.name = name
        self.scenario = SCENARIOS[name]()
        self.sim = MissionSimulator(
            self.scenario["drone"], self.scenario["world"], self.scenario["mission"]
        )
        self.plan = self.scenario["plan"]
        self.verdict = None
        self.certificate = None
        self.pending = {}
        self.replan_attempts = 0
        self.status = "DRAFT"

    def state(self) -> dict:
        return {
            "scenario": self.name, "title": self.scenario["title"], "status": self.status,
            "mission": self.scenario["mission"].model_dump(mode="json"),
            "world": self.sim.world.model_dump(mode="json"),
            "drone": self.sim.drone.model_dump(mode="json"),
            "plan": self.plan.model_dump(mode="json"),
            "verdict": self.verdict.model_dump(mode="json") if self.verdict else None,
            "certificate": self.certificate.model_dump(mode="json") if self.certificate else None,
            "replan_attempts": self.replan_attempts,
            "events": [event.model_dump(mode="json") for event in self.sim.events],
        }

    def create_survey(self, data: SurveyInput) -> None:
        from app.mission.parser import validate_survey_request

        coords = [(data.west, data.south), (data.east, data.south),
                  (data.east, data.north), (data.west, data.north), (data.west, data.south)]
        area = [Point(longitude=x, latitude=y) for x, y in coords]
        parsed = validate_survey_request(data.instruction, area, "Operator survey area", "demo-operator")
        self.load("flood")
        self.name = "custom"
        self.scenario["title"] = "Operator survey area"
        polygon = GeoPolygon(coordinates=[coords])
        self.sim.world.survey_area = polygon
        self.sim.world.geofence_boundary = polygon
        self.sim.world.restricted_zones = []
        self.sim.drone.location = coords[0]
        self.sim.drone.home_position = coords[0]
        self.scenario["mission"].mission_id = parsed.mission_id
        self.scenario["mission"].survey_area = polygon
        self.scenario["mission"].operator_instruction = data.instruction
        self.plan.mission_id = parsed.mission_id
        self.plan.plan_id = f"PLAN-{uuid4()}"
        self.plan.waypoints = [SafetyWaypoint(waypoint_id=f"WP-{i+1}", longitude=x,
            latitude=y, altitude_agl_m=45.0, speed_mps=8.0) for i, (x, y) in enumerate(coords)]
        distance = sum(haversine_distance_m(a, b) for a, b in zip(coords, coords[1:], strict=False))
        self.plan.estimated_duration_s = distance / 8.0
        self.plan.estimated_energy_wh = distance * 0.04 + 5.0

    def verify_current(self) -> None:
        self.verdict, self.certificate = SafetyVerifier(self.scenario["policy"]).verify(
            self.plan, self.scenario["mission"], self.sim.world, self.sim.drone
        )
        self.status = "CERTIFIED" if self.certificate else "REJECTED"

    def launch(self) -> None:
        if self.status != "CERTIFIED" or not self.certificate:
            raise HTTPException(409, "A current passing certificate is required before launch")
        # Re-check the actual current state at the execution boundary.
        old_digest = self.certificate.plan_digest
        self.verify_current()
        if not self.certificate or self.certificate.plan_digest != old_digest:
            raise HTTPException(409, "Plan or safety state changed; launch refused")
        self.sim.plan = self.plan.model_copy(deep=True)
        self.sim.drone.is_airborne = True
        self.sim.is_paused = False
        self.status = "ACTIVE"

    def tick(self) -> None:
        if self.status != "ACTIVE":
            raise HTTPException(409, "Launch a certified mission first")
        self.sim.tick(1.0)
        if not self.sim.drone.is_airborne:
            self.status = "COMPLETED"
        elif self.sim.drone.battery_pct < self.scenario["policy"].battery_reserve_pct:
            self.sim.is_paused = True
            self.status = "INTERVENTION_REQUIRED"
            self.certificate = None

    def inject(self, family: str) -> None:
        if self.status != "ACTIVE":
            raise HTTPException(409, "An active simulation is required")
        if family == "SURVIVOR_DETECTED":
            self.sim.inject_survivor_detected()
        elif family == "LOW_BATTERY":
            self.sim.drone.battery_pct = 18.0
            self.sim.drone.battery_wh = 18.0
            self.sim.inject_low_battery()
        elif family == "WIND_SPIKE":
            self.sim.inject_wind_spike()
        elif family == "NEW_RESTRICTED_ZONE":
            zone = create_dam_breach_scenario()["world"].restricted_zones[-1]
            self.sim.inject_new_restricted_zone(zone.zone_id, zone.name, zone.boundary)
        elif family == "OPERATOR_MISSION_CHANGE":
            self.sim.emit_event(
                SimulationEventType.OPERATOR_MISSION_CHANGE,
                {"message": "Operator requested mission review"}, source="OPERATOR",
            )
        else:
            raise HTTPException(422, "Unknown event family")
        # Stop movement until the changed state is explicitly reverified.
        self.sim.is_paused = True
        self.certificate = None
        self.status = "INTERVENTION_REQUIRED"
        self.sim.world.world_revision += 1
        self.replan_attempts = 0

    def replan(self) -> None:
        if self.status not in {"INTERVENTION_REQUIRED", "REJECTED"}:
            raise HTTPException(409, "A paused mission requiring review is needed")
        if self.replan_attempts >= 3:
            raise HTTPException(409, "Three replan attempts exhausted; operator intervention required")
        self.replan_attempts += 1
        remaining = self.plan.waypoints[self.sim.drone.current_waypoint_index:]
        if not remaining:
            raise HTTPException(409, "There are no remaining waypoints to replan")
        current = self.sim.drone.location
        start = SafetyWaypoint(waypoint_id="CURRENT-POSITION", longitude=current[0],
            latitude=current[1], altitude_agl_m=remaining[0].altitude_agl_m, speed_mps=remaining[0].speed_mps)
        candidate = self.plan.model_copy(deep=True)
        candidate.plan_id = f"PLAN-{uuid4()}"
        candidate.revision += 1
        candidate.waypoints = [start, *remaining]
        legs = list(zip(candidate.waypoints, candidate.waypoints[1:], strict=False))
        distance = sum(haversine_distance_m((a.longitude, a.latitude), (b.longitude, b.latitude)) for a, b in legs)
        candidate.estimated_duration_s = sum(haversine_distance_m((a.longitude, a.latitude), (b.longitude, b.latitude)) / b.speed_mps + (b.dwell_s or 0) for a, b in legs)
        candidate.estimated_energy_wh = distance * 0.04 + 5.0
        self.plan = candidate
        self.verify_current()
        self.sim.drone.current_waypoint_index = 0
        self.sim.emit_event(SimulationEventType.OPERATOR_MISSION_CHANGE,
            {"status": "REPLAN_CERTIFIED" if self.certificate else "REPLAN_REJECTED", "attempt": self.replan_attempts, "plan_id": self.plan.plan_id}, source="SIMULATOR")

    def mission_dto(self) -> Mission:
        m = self.scenario["mission"]
        coords = m.survey_area.coordinates[0]
        return Mission(
            mission_id=m.mission_id, approved_area=[Point(longitude=x, latitude=y) for x, y in coords],
            approved_location_label=self.scenario["title"], operator_id="demo-operator",
        )

    async def get_snapshot(self, mission_id: str) -> TrustedSnapshot:
        if mission_id != self.scenario["mission"].mission_id:
            raise ValueError("mission mismatch")
        d, w, p = self.sim.drone, self.sim.world, self.scenario["policy"]
        return TrustedSnapshot(
            drone_state=DroneState(position=Point(longitude=d.location[0], latitude=d.location[1]), battery_percent=d.battery_pct),
            world_state=WorldState(revision=str(w.world_revision), restricted_zone_refs=[z.zone_id for z in w.restricted_zones if z.active]),
            safety_policy=SafetyPolicy(revision=p.version, reference=p.policy_id),
        )

    async def verify(self, plan: Plan, mission: Mission, snapshot: TrustedSnapshot) -> VerificationResult:
        points = [SafetyWaypoint(
            waypoint_id=f"WP-{i+1}", longitude=p.longitude, latitude=p.latitude,
            altitude_agl_m=p.altitude_agl_m, speed_mps=p.speed_mps,
            dwell_s=p.dwell_s or 0.0,
        ) for i, p in enumerate(plan.waypoints)]
        current = self.sim.drone.location
        if (points[0].longitude, points[0].latitude) != tuple(current):
            points.insert(0, SafetyWaypoint(waypoint_id="CURRENT-POSITION", longitude=current[0],
                latitude=current[1], altitude_agl_m=points[0].altitude_agl_m, speed_mps=points[0].speed_mps))
        distance = sum(haversine_distance_m((a.longitude, a.latitude), (b.longitude, b.latitude)) for a, b in zip(points, points[1:], strict=False))
        # Derive conservative demo estimates on the server; never trust model-supplied energy.
        duration = sum(haversine_distance_m((a.longitude, a.latitude), (b.longitude, b.latitude)) / b.speed_mps + (b.dwell_s or 0) for a, b in zip(points, points[1:], strict=False))
        candidate = SafetyPlan(
            plan_id=plan.plan_id, mission_id=mission.mission_id, revision=plan.revision,
            waypoints=points, estimated_duration_s=duration, estimated_energy_wh=distance * 0.04 + 5.0,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        result, cert = SafetyVerifier(self.scenario["policy"]).verify(candidate, self.scenario["mission"], self.sim.world, self.sim.drone)
        self.verdict = result
        if cert:
            self.pending[plan.plan_id] = (candidate, cert, snapshot.world_state.revision)
        return VerificationResult(
            passed=result.passed,
            violations=[Violation(rule_id=v.rule_id.value, message=v.message, observed_value=v.observed, applicable_limit=v.limit) for v in result.violations],
            certificate=Certificate(certificate_ref=cert.certificate_id, plan_id=plan.plan_id, snapshot_revision=snapshot.world_state.revision, issuer="deterministic-simulator-verifier") if cert else None,
        )

    async def request_plan_handoff(self, plan: Plan, certificate: Certificate) -> str:
        candidate, cert, revision = self.pending.pop(plan.plan_id)
        if cert.certificate_id != certificate.certificate_ref or revision != str(self.sim.world.world_revision):
            raise ValueError("certificate or world revision mismatch")
        self.plan, self.certificate, self.status = candidate, cert, "CERTIFIED"
        return f"demo-staged:{plan.plan_id}"


def demo_router(authorize) -> APIRouter:
    router = APIRouter(prefix="/api/v1/demo", dependencies=[authorize])

    @router.get("/state")
    async def state(request: Request):
        return request.app.state.demo.state()

    @router.post("/scenario/{name}")
    async def scenario(name: str, request: Request):
        demo = request.app.state.demo
        async with demo.lock:
            if demo.status == "ACTIVE":
                raise HTTPException(409, "An active mission must finish before changing scenario")
            demo.load(name)
            return demo.state()

    @router.post("/survey")
    async def create_survey(body: SurveyInput, request: Request):
        demo = request.app.state.demo
        async with demo.lock:
            if demo.status == "ACTIVE":
                raise HTTPException(409, "An active mission must finish before creating another")
            demo.create_survey(body)
            return demo.state()

    @router.post("/verify")
    async def verify(request: Request):
        demo = request.app.state.demo
        async with demo.lock:
            if demo.status == "ACTIVE":
                raise HTTPException(409, "Cannot replace a certificate during an active simulation")
            demo.verify_current()
            return demo.state()

    @router.post("/launch")
    async def launch(request: Request):
        demo = request.app.state.demo
        async with demo.lock:
            demo.launch()
            return demo.state()

    @router.post("/tick")
    async def tick(request: Request):
        demo = request.app.state.demo
        async with demo.lock:
            demo.tick()
            return demo.state()

    @router.post("/event")
    async def event(body: EventInput, request: Request):
        demo = request.app.state.demo
        async with demo.lock:
            demo.inject(body.family)
            return demo.state()

    @router.post("/replan")
    async def replan(request: Request):
        demo = request.app.state.demo
        async with demo.lock:
            demo.replan()
            return demo.state()

    @router.post("/ai-plan")
    async def ai_plan(request: Request):
        demo = request.app.state.demo
        settings = request.app.state.nebius.settings
        if not settings.nebius_api_key or not settings.nebius_model_planner:
            raise HTTPException(503, "Configure Nebius planner credentials first")
        async with demo.lock:
            if demo.status == "ACTIVE":
                raise HTTPException(409, "Pause the simulation with an event before planning")
            service = MissionService(demo, demo, demo, NebiusProposalEngine(request.app.state.nebius, ModelRouter(settings)), max_repairs=0)
            operation = await service.plan(demo.mission_dto(), str(uuid4()))
            return {"operation_status": operation.status, "error": operation.error.message if operation.error else None, "state": demo.state()}

    return router
