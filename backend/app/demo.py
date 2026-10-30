"""Local, single-drone integration of the AI proposal and simulator components.

The sample policies and scenarios are prototype assumptions, not approved flight rules.
"""
# ruff: noqa: E402
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field, ValidationError, model_validator
from shapely.geometry import Point as ShapePoint
from shapely.geometry import Polygon

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
from verifier.models import GeoPolygon, RestrictedZone, SimulationEventType
from verifier.models import Plan as SafetyPlan
from verifier.models import Waypoint as SafetyWaypoint
from verifier.rules import haversine_distance_m

from app.context.geocoding import search_location
from app.context.local_vision import analyze_local_image
from app.context.osm_features import analysis_record, fetch_osm_features
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
from app.demo_geometry import validate_point, validate_ring, validate_route
from app.demo_planner import generate_geographic_route
from app.llm.router import ModelRouter, ModelSelection
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
    location: tuple[float, float] | None = None
    zone_coordinates: list[tuple[float, float]] | None = None


class SurveyInput(BaseModel):
    instruction: str = Field(min_length=1, max_length=1000)
    west: float | None = Field(default=None, ge=-180, le=180)
    east: float | None = Field(default=None, ge=-180, le=180)
    south: float | None = Field(default=None, ge=-90, le=90)
    north: float | None = Field(default=None, ge=-90, le=90)
    coordinates: list[tuple[float, float]] | None = None

    @model_validator(mode="after")
    def rectangle_is_ordered(self):
        if self.coordinates is not None:
            validate_ring(self.coordinates)
            return self
        if None in (self.west, self.east, self.south, self.north):
            raise ValueError("Supply drawn coordinates or all four rectangle bounds")
        if self.west >= self.east or self.south >= self.north:
            raise ValueError("West must be less than east and south must be less than north")
        if self.east - self.west > 0.1 or self.north - self.south > 0.1:
            raise ValueError("Demo survey area must be within 0.1 degrees per side")
        return self

    def ring(self) -> list[tuple[float, float]]:
        if self.coordinates is not None:
            return validate_ring(self.coordinates)
        return validate_ring([(self.west, self.south), (self.east, self.south),
                              (self.east, self.north), (self.west, self.north)])


ZoneKind = Literal["restricted", "planned", "no_man", "no_fly", "destination_drop", "pickup", "safe", "unknown"]
BLOCKING_ZONES = {"restricted", "no_man", "no_fly", "unknown"}


class ZoneInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    zone_type: ZoneKind
    coordinates: list[tuple[float, float]]
    buffer_m: float = Field(default=0, ge=0, le=100)
    source: Literal["operator", "osm_confirmed"] = "operator"


class RouteInput(BaseModel):
    coordinates: list[tuple[float, float]]
    altitude_agl_m: float = Field(default=45, ge=15, le=120)
    speed_mps: float = Field(default=8, gt=0, le=15)


class VisionInput(BaseModel):
    image_base64: str = Field(min_length=100, max_length=3_000_000)
    bounds: tuple[float, float, float, float]


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
        self.zones: list[dict] = []
        self.map_findings: list[dict] = []
        self.map_analysis: dict | None = None
        self.vision_findings: list[dict] = []
        self.vision_analysis: dict | None = None
        self.replan_attempts = 0
        self.last_trigger: str | None = None
        self.status = "DRAFT"

    def state(self) -> dict:
        world = self.sim.world.model_dump(mode="json")
        custom_ids = {zone["zone_id"] for zone in self.zones}
        world["zones"] = [
            *[zone.copy() for zone in self.zones],
            *[{
                "zone_id": zone.zone_id, "name": zone.name, "zone_type": "restricted",
                "boundary": zone.boundary.model_dump(mode="json"), "buffer_m": zone.buffer_m,
                "active": zone.active, "source": "seeded",
            } for zone in self.sim.world.restricted_zones if zone.zone_id not in custom_ids],
        ]
        return {
            "scenario": self.name, "title": self.scenario["title"], "status": self.status,
            "mission": self.scenario["mission"].model_dump(mode="json"),
            "world": world,
            "drone": self.sim.drone.model_dump(mode="json"),
            "plan": self.plan.model_dump(mode="json"),
            "map_findings": self.map_findings,
            "map_analysis": self.map_analysis,
            "vision_findings": self.vision_findings,
            "vision_analysis": self.vision_analysis,
            "verdict": self.verdict.model_dump(mode="json") if self.verdict else None,
            "certificate": self.certificate.model_dump(mode="json") if self.certificate else None,
            "replan_attempts": self.replan_attempts,
            "events": [event.model_dump(mode="json") for event in self.sim.events],
        }

    def create_survey(self, data: SurveyInput) -> None:
        from app.mission.parser import validate_survey_request

        coords = data.ring()
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

    def invalidate_plan(self) -> None:
        self.verdict = None
        self.certificate = None
        self.pending.clear()
        self.status = "DRAFT"
        self.sim.world.world_revision += 1

    def add_zone(self, body: ZoneInput, *, source: str = "operator") -> dict:
        area = Polygon(self.scenario["mission"].survey_area.coordinates[0])
        ring = validate_ring(body.coordinates, area=area)
        zone_id = f"ZONE-{uuid4()}"
        zone = {
            "zone_id": zone_id, "name": body.name, "zone_type": body.zone_type,
            "boundary": GeoPolygon(coordinates=[ring]).model_dump(mode="json"),
            "buffer_m": body.buffer_m, "active": True, "source": source,
        }
        self.zones.append(zone)
        if body.zone_type in BLOCKING_ZONES:
            self.sim.world.restricted_zones.append(RestrictedZone(
                zone_id=zone_id, name=f"{body.zone_type.replace('_', ' ')}: {body.name}",
                boundary=GeoPolygon(coordinates=[ring]), buffer_m=body.buffer_m, active=True,
            ))
        self.invalidate_plan()
        return zone

    def add_suggested_zones(self) -> int:
        """Make reviewable zones from mapped and local vision findings."""
        kinds = {"possible_threat": "restricted", "water": "unknown", "building": "planned"}
        existing = {zone.get("source_ref") for zone in self.zones}
        added = 0
        building_count = 0
        for index, finding in enumerate([*self.map_findings, *self.vision_findings]):
            if added >= 12:
                break
            if finding["kind"] == "building" and building_count >= 4:
                continue
            reference = (
                f"osm:way:{finding['osm_id']}" if finding.get("osm_id") is not None
                else f"vision:{index}:{finding['label']}"
            )
            if reference in existing:
                continue
            try:
                zone = self.add_zone(ZoneInput(
                    name=finding["label"], zone_type=kinds[finding["kind"]],
                    coordinates=finding["coordinates"], source="operator",
                ), source="auto_suggestion")
            except HTTPException:
                continue
            zone["source_ref"] = reference
            existing.add(reference)
            added += 1
            if finding["kind"] == "building":
                building_count += 1
        return added

    def remove_zone(self, zone_id: str) -> None:
        original_count = len(self.zones)
        self.zones = [zone for zone in self.zones if zone["zone_id"] != zone_id]
        if len(self.zones) == original_count:
            raise HTTPException(404, "Only operator-created zones can be removed")
        self.sim.world.restricted_zones = [
            zone for zone in self.sim.world.restricted_zones if zone.zone_id != zone_id
        ]
        self.invalidate_plan()

    def set_route(self, body: RouteInput, *, source: str = "operator") -> None:
        points = validate_route(body.coordinates)
        home = tuple(self.sim.drone.home_position)
        current = tuple(self.sim.drone.location)
        if points[0] != current:
            points.insert(0, current)
        if points[-1] != home:
            points.append(home)
        if len(points) > self.scenario["policy"].max_waypoints:
            raise HTTPException(422, "Route exceeds the waypoint limit")
        waypoints = [SafetyWaypoint(
            waypoint_id=f"WP-{index+1}", longitude=lon, latitude=lat,
            altitude_agl_m=body.altitude_agl_m, speed_mps=body.speed_mps,
            action="RETURN_HOME" if index == len(points) - 1 else "SURVEY",
        ) for index, (lon, lat) in enumerate(points)]
        legs = list(zip(points, points[1:], strict=False))
        distance = sum(haversine_distance_m(a, b) for a, b in legs)
        self.plan = SafetyPlan(
            plan_id=f"PLAN-{uuid4()}", mission_id=self.scenario["mission"].mission_id,
            revision=self.plan.revision + 1, waypoints=waypoints,
            estimated_duration_s=sum(haversine_distance_m(a, b) / body.speed_mps for a, b in legs),
            estimated_energy_wh=distance * 0.04 + 5.0,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self.plan.provenance.planner_type = {
            "ai": "AI_ORCHESTRATOR", "auto": "DETERMINISTIC_GRID", "operator": "MANUAL_MAP",
        }[source]
        self.invalidate_plan()

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

    def inject(self, body: EventInput) -> None:
        if self.status != "ACTIVE":
            raise HTTPException(409, "An active simulation is required")
        family = body.family
        if family == "SURVIVOR_DETECTED":
            location = validate_point(body.location) if body.location is not None else tuple(self.sim.drone.location)
            if not Polygon(self.scenario["mission"].survey_area.coordinates[0]).covers(ShapePoint(location)):
                raise HTTPException(422, "Detection point must be inside the survey area")
            self.sim.inject_survivor_detected(location=location, source="OPERATOR")
        elif family == "LOW_BATTERY":
            self.sim.drone.battery_pct = 18.0
            self.sim.drone.battery_wh = 18.0
            self.sim.inject_low_battery()
        elif family == "WIND_SPIKE":
            self.sim.inject_wind_spike()
        elif family == "NEW_RESTRICTED_ZONE":
            if body.zone_coordinates is None:
                raise HTTPException(422, "Draw the new restricted zone on the map first")
            ring = validate_ring(body.zone_coordinates, area=Polygon(self.scenario["mission"].survey_area.coordinates[0]))
            zone_id = f"ZONE-EVENT-{uuid4()}"
            boundary = GeoPolygon(coordinates=[ring])
            self.sim.inject_new_restricted_zone(zone_id, "Injected restricted zone", boundary)
            self.zones.append({"zone_id": zone_id, "name": "Injected restricted zone",
                               "zone_type": "restricted", "boundary": boundary.model_dump(mode="json"),
                               "buffer_m": 25.0, "active": True, "source": "event"})
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
        self.verdict = None
        self.pending.clear()
        self.status = "INTERVENTION_REQUIRED"
        if family != "NEW_RESTRICTED_ZONE":
            self.sim.world.world_revision += 1
        self.replan_attempts = 0
        self.last_trigger = family

    def replan(self) -> None:
        if self.status not in {"INTERVENTION_REQUIRED", "REJECTED"}:
            raise HTTPException(409, "A paused mission requiring review is needed")
        if self.replan_attempts >= 3:
            raise HTTPException(409, "Three replan attempts exhausted; operator intervention required")
        self.replan_attempts += 1
        remaining = self.plan.waypoints[self.sim.drone.current_waypoint_index:]
        if not remaining:
            raise HTTPException(409, "There are no remaining waypoints to replan")
        targets = [(waypoint.longitude, waypoint.latitude) for waypoint in remaining[:-1]]
        coordinates = generate_geographic_route(
            self.scenario["mission"].survey_area.coordinates[0],
            self.state()["world"]["zones"],
            tuple(self.sim.drone.location), tuple(self.sim.drone.home_position),
            coverage_points=targets,
        )
        self.set_route(RouteInput(coordinates=coordinates,
            altitude_agl_m=remaining[0].altitude_agl_m,
            speed_mps=remaining[0].speed_mps), source="auto")
        self.plan.provenance.trigger_reason = self.last_trigger or "OPERATOR"
        self.plan.provenance.repair_attempt = self.replan_attempts
        self.verify_current()
        self.sim.drone.current_waypoint_index = 0
        self.sim.emit_event(SimulationEventType.OPERATOR_MISSION_CHANGE,
            {"status": "REPLAN_CERTIFIED" if self.certificate else "REPLAN_REJECTED",
             "attempt": self.replan_attempts, "plan_id": self.plan.plan_id,
             "skipped_blocked_waypoints": len(targets) - sum(
                 1 for point in targets if point in coordinates
             )}, source="SIMULATOR")

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

    @router.get("/location/search")
    async def location_search(q: str = Query(min_length=3, max_length=200)):
        return {"results": await search_location(q), "source": "OpenStreetMap Nominatim"}

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
            demo.inject(body)
            return demo.state()

    @router.post("/replan")
    async def replan(request: Request):
        demo = request.app.state.demo
        async with demo.lock:
            demo.replan()
            return demo.state()

    @router.post("/zones")
    async def add_zone(body: ZoneInput, request: Request):
        demo = request.app.state.demo
        async with demo.lock:
            if demo.status == "ACTIVE":
                raise HTTPException(409, "Pause the mission before editing zones")
            demo.add_zone(body, source=body.source)
            return demo.state()

    @router.delete("/zones/{zone_id}")
    async def delete_zone(zone_id: str, request: Request):
        demo = request.app.state.demo
        async with demo.lock:
            if demo.status == "ACTIVE":
                raise HTTPException(409, "Pause the mission before editing zones")
            demo.remove_zone(zone_id)
            return demo.state()

    @router.post("/route/manual")
    async def manual_route(body: RouteInput, request: Request):
        demo = request.app.state.demo
        async with demo.lock:
            if demo.status == "ACTIVE":
                raise HTTPException(409, "Pause the mission before editing its route")
            demo.set_route(body)
            return demo.state()

    @router.post("/analyze-map")
    async def analyze_map(request: Request):
        demo = request.app.state.demo
        async with demo.lock:
            if demo.status == "ACTIVE":
                raise HTTPException(409, "Pause the mission before map analysis")
            if demo.map_analysis is None:
                ring = demo.scenario["mission"].survey_area.coordinates[0]
                demo.map_findings, source = await fetch_osm_features(ring)
                demo.map_analysis = analysis_record(demo.map_findings, source)
            return demo.state()

    @router.post("/vision/local")
    async def local_vision(body: VisionInput, request: Request):
        demo = request.app.state.demo
        async with demo.lock:
            if demo.status == "ACTIVE":
                raise HTTPException(409, "Pause the mission before image analysis")
            ring = demo.scenario["mission"].survey_area.coordinates[0]
            west, south, east, north = body.bounds
            if not Polygon([(west, south), (east, south), (east, north), (west, north)]).covers(Polygon(ring)):
                raise HTTPException(422, "The captured map must contain the locked survey area")
            demo.vision_findings, demo.vision_analysis = await analyze_local_image(
                body.image_base64, body.bounds, ring,
            )
            return demo.state()

    @router.post("/zones/auto")
    async def auto_zones(request: Request):
        demo = request.app.state.demo
        async with demo.lock:
            if demo.status == "ACTIVE":
                raise HTTPException(409, "Pause the mission before adding zones")
            if not demo.map_findings and not demo.vision_findings:
                raise HTTPException(409, "Analyze the map before creating suggested zones")
            demo.add_suggested_zones()
            return demo.state()

    @router.post("/route/auto")
    async def auto_route(request: Request):
        demo = request.app.state.demo
        async with demo.lock:
            if demo.status == "ACTIVE":
                raise HTTPException(409, "Pause the mission before planning")
            coordinates = generate_geographic_route(
                demo.scenario["mission"].survey_area.coordinates[0],
                demo.state()["world"]["zones"],
                tuple(demo.sim.drone.location), tuple(demo.sim.drone.home_position),
            )
            demo.set_route(RouteInput(coordinates=coordinates), source="auto")
            demo.verify_current()
            return demo.state()

    @router.post("/route/ai")
    async def ai_route(request: Request):
        demo = request.app.state.demo
        settings = request.app.state.nebius.settings
        if not settings.nebius_api_key or not settings.nebius_model_planner:
            raise HTTPException(503, "Configure Nebius planner credentials first")
        async with demo.lock:
            if demo.status == "ACTIVE":
                raise HTTPException(409, "Pause the mission before planning")
            context = {
                "survey_area": demo.scenario["mission"].survey_area.coordinates[0],
                "current_position": demo.sim.drone.location,
                "home_position": demo.sim.drone.home_position,
                "zones": demo.state()["world"]["zones"],
                "mapped_features": demo.map_findings,
                "altitude_agl_m": 45, "speed_mps": 8,
            }
            prompt = (
                "Return only JSON {\"coordinates\":[[longitude,latitude],...]} for a survey route "
                "inside the supplied WGS84 survey polygon. Use actual supplied coordinates as bounds; "
                "do not invent a different place. Visit planned, pickup, destination_drop and safe "
                "zones when feasible. Avoid restricted, no_man, no_fly and unknown zones including "
                "their buffers. Mapped features are context, not flight restrictions unless "
                "the operator confirmed them as zones. "
                "Return 2 to 30 ordered coordinates. The server will add current position and home "
                "and reject any unsafe proposal. Never claim a certificate."
            )
            payload, trace = await request.app.state.nebius.json_completion(
                ModelSelection(tier="planner", model_id=settings.nebius_model_planner,
                               reason="operator:map-route"),
                "map-route", [{"role": "system", "content": prompt},
                              {"role": "user", "content": json.dumps(context)}],
                json_mode=False, mission_id=demo.scenario["mission"].mission_id,
                prompt_revision="map-route-v1",
            )
            try:
                route = RouteInput.model_validate({"coordinates": payload["coordinates"]})
            except (KeyError, TypeError, ValidationError) as exc:
                raise HTTPException(502, "Planner returned invalid route coordinates") from exc
            demo.set_route(route, source="ai")
            demo.verify_current()
            return {"state": demo.state(), "trace_id": trace.trace_id,
                    "model_id": trace.actual_model_id}

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
