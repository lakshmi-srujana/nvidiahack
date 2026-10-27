"""
SkyWarden Pydantic v2 Canonical Models
Matches CONTRACTS.md and projectplan.md approved decisions.
"""

from enum import Enum
from typing import List, Optional, Tuple, Any, Dict
from pydantic import BaseModel, Field, field_validator
import math


class MissionObjectiveType(str, Enum):
    SURVEY_AREA = "SURVEY_AREA"


class MissionLifecycleStatus(str, Enum):
    DRAFT = "DRAFT"
    PLANNED = "PLANNED"
    VERIFIED = "VERIFIED"
    CERTIFIED = "CERTIFIED"
    ACTIVE = "ACTIVE"
    REPLANNING = "REPLANNING"
    INTERVENTION_REQUIRED = "INTERVENTION_REQUIRED"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"


class WaypointAction(str, Enum):
    TRANSIT = "TRANSIT"
    SURVEY = "SURVEY"
    HOVER = "HOVER"
    RETURN_HOME = "RETURN_HOME"


class ViolationSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


class RuleIdentifier(str, Enum):
    RULE_01_GEOFENCE_CONTAINMENT = "RULE_01_GEOFENCE_CONTAINMENT"
    RULE_02_RESTRICTED_ZONE_CLEARANCE = "RULE_02_RESTRICTED_ZONE_CLEARANCE"
    RULE_03_ALTITUDE_AGL_BOUNDS = "RULE_03_ALTITUDE_AGL_BOUNDS"
    RULE_04_MAX_SPEED_LIMIT = "RULE_04_MAX_SPEED_LIMIT"
    RULE_05_ENERGY_BUDGET_RESERVE = "RULE_05_ENERGY_BUDGET_RESERVE"
    RULE_06_RETURN_TO_HOME_FEASIBILITY = "RULE_06_RETURN_TO_HOME_FEASIBILITY"
    RULE_07_WIND_SPEED_LIMIT = "RULE_07_WIND_SPEED_LIMIT"
    RULE_08_PHYSICS_SCHEMA_SANITY = "RULE_08_PHYSICS_SCHEMA_SANITY"
    RULE_09_MISSION_TIME_WAYPOINTS_CAP = "RULE_09_MISSION_TIME_WAYPOINTS_CAP"
    RULE_10_CONSTRAINT_INTEGRITY = "RULE_10_CONSTRAINT_INTEGRITY"


class SimulationEventType(str, Enum):
    SURVIVOR_DETECTED = "SURVIVOR_DETECTED"
    LOW_BATTERY = "LOW_BATTERY"
    WIND_SPIKE = "WIND_SPIKE"
    OPERATOR_MISSION_CHANGE = "OPERATOR_MISSION_CHANGE"
    NEW_RESTRICTED_ZONE = "NEW_RESTRICTED_ZONE"
    TELEMETRY_TICK = "TELEMETRY_TICK"
    WAYPOINT_REACHED = "WAYPOINT_REACHED"
    MISSION_COMPLETED = "MISSION_COMPLETED"


class GeoPolygon(BaseModel):
    type: str = "Polygon"
    coordinates: List[List[Tuple[float, float]]]  # [[ [lon, lat], ... ]]


class Waypoint(BaseModel):
    waypoint_id: str
    longitude: float = Field(ge=-180.0, le=180.0)
    latitude: float = Field(ge=-90.0, le=90.0)
    altitude_agl_m: float = Field(ge=0.0)
    speed_mps: float = Field(gt=0.0)
    action: Optional[WaypointAction] = WaypointAction.SURVEY
    dwell_s: Optional[float] = Field(default=0.0, ge=0.0)

    @field_validator("longitude", "latitude", "altitude_agl_m", "speed_mps")
    @classmethod
    def check_finite(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError("Numeric values must be finite numbers")
        return v


class OperatorRestrictions(BaseModel):
    min_altitude_agl_m: Optional[float] = None
    max_altitude_agl_m: Optional[float] = None
    max_speed_mps: Optional[float] = None
    forbidden_zones: Optional[List[GeoPolygon]] = None
    notes: Optional[str] = None


class Mission(BaseModel):
    schema_version: str = "1.0.0"
    mission_id: str
    objective_type: MissionObjectiveType = MissionObjectiveType.SURVEY_AREA
    survey_area: GeoPolygon
    operator_instruction: str
    operator_restrictions: OperatorRestrictions = Field(default_factory=OperatorRestrictions)
    status: MissionLifecycleStatus = MissionLifecycleStatus.DRAFT
    created_at: str
    current_plan_id: Optional[str] = None
    approved_by: Optional[str] = None


class PlanProvenance(BaseModel):
    model_id: Optional[str] = None
    planner_type: str = "DETERMINISTIC_GRID"
    trigger_reason: Optional[str] = None
    repair_attempt: int = Field(default=0, ge=0, le=3)


class Plan(BaseModel):
    schema_version: str = "1.0.0"
    plan_id: str
    mission_id: str
    revision: int = 1
    waypoints: List[Waypoint]
    provenance: PlanProvenance = Field(default_factory=PlanProvenance)
    estimated_duration_s: float = Field(ge=0.0)
    estimated_energy_wh: float = Field(ge=0.0)
    created_at: str


class Violation(BaseModel):
    rule_id: RuleIdentifier
    severity: ViolationSeverity
    message: str
    observed: Any
    limit: Any
    unit: Optional[str] = None
    waypoint_refs: Optional[List[str]] = None
    remediation: Optional[str] = None


class RuleCheckResult(BaseModel):
    rule_id: RuleIdentifier
    name: str
    passed: bool
    message: str
    observed: Optional[Any] = None
    limit: Optional[Any] = None
    unit: Optional[str] = None


class VerificationResult(BaseModel):
    schema_version: str = "1.0.0"
    plan_id: str
    mission_id: str
    passed: bool
    policy_ref: str
    world_ref: str
    drone_ref: str
    checks: List[RuleCheckResult]
    violations: List[Violation]
    verified_at: str


class Certificate(BaseModel):
    schema_version: str = "1.0.0"
    certificate_id: str
    mission_id: str
    plan_id: str
    verification_ref: str
    plan_digest: str  # SHA-256 hash
    policy_ref: str
    world_ref: str
    issued_at: str
    rule_results: List[RuleCheckResult]
    is_valid: bool = True
    invalidation_reason: Optional[str] = None


class SimulationEvent(BaseModel):
    event_id: str
    mission_id: str
    event_type: SimulationEventType
    payload: Dict[str, Any]
    sim_time_s: float
    sequence: int
    source: str = "SIMULATOR"
    created_at: str


class RestrictedZone(BaseModel):
    zone_id: str
    name: str
    boundary: GeoPolygon
    buffer_m: float = 25.0
    active: bool = True


class WorldState(BaseModel):
    world_revision: int = 1
    survey_area: GeoPolygon
    geofence_boundary: GeoPolygon
    restricted_zones: List[RestrictedZone] = Field(default_factory=list)
    wind_speed_mps: float = 0.0
    wind_direction_deg: float = 0.0
    ambient_temperature_c: float = 20.0
    weather_condition: str = "CLEAR"


class SafetyPolicy(BaseModel):
    policy_id: str = "POL-DEFAULT-V1"
    version: str = "1.0.0"
    min_altitude_agl_m: float = 15.0
    max_altitude_agl_m: float = 120.0
    max_speed_mps: float = 15.0
    max_wind_speed_mps: float = 12.0
    battery_reserve_pct: float = 20.0
    total_battery_wh: float = 100.0
    min_return_home_energy_wh: float = 20.0
    max_mission_time_s: float = 1800.0  # 30 min
    max_waypoints: int = 100
    restricted_zone_buffer_m: float = 25.0
    max_repair_attempts: int = 3


class DroneState(BaseModel):
    drone_id: str = "UAV-ALPHA-01"
    location: Tuple[float, float]  # (lon, lat)
    altitude_agl_m: float = 0.0
    velocity_mps: float = 0.0
    heading_deg: float = 0.0
    battery_pct: float = 100.0
    battery_wh: float = 100.0
    home_position: Tuple[float, float]
    sim_time_s: float = 0.0
    current_waypoint_index: int = 0
    state_revision: int = 1
    is_airborne: bool = False
