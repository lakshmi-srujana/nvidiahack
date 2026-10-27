/**
 * SkyWarden Shared Interface Contracts
 * Canonical TypeScript definitions matching Pydantic v2 contract specifications.
 * Schema Version: 1.0.0
 */

export const SCHEMA_VERSION = "1.0.0";

// --- Coordinates & Spatial Types ---

export type Longitude = number; // WGS84 [-180, 180]
export type Latitude = number;  // WGS84 [-90, 90]

export type Coordinate = [Longitude, Latitude]; // GeoJSON convention: [lon, lat]

export interface GeoPolygon {
  type: "Polygon";
  coordinates: Coordinate[][]; // outer ring, optional holes
}

// --- Enums ---

export type MissionObjectiveType = "SURVEY_AREA";

export type MissionLifecycleStatus =
  | "DRAFT"
  | "PLANNED"
  | "VERIFIED"
  | "CERTIFIED"
  | "ACTIVE"
  | "REPLANNING"
  | "INTERVENTION_REQUIRED"
  | "COMPLETED"
  | "ABORTED";

export type WaypointAction =
  | "TRANSIT"
  | "SURVEY"
  | "HOVER"
  | "RETURN_HOME";

export type ViolationSeverity = "CRITICAL" | "WARNING" | "INFO";

export type SimulationEventType =
  | "SURVIVOR_DETECTED"
  | "LOW_BATTERY"
  | "WIND_SPIKE"
  | "OPERATOR_MISSION_CHANGE"
  | "NEW_RESTRICTED_ZONE"
  | "TELEMETRY_TICK"
  | "WAYPOINT_REACHED"
  | "MISSION_COMPLETED";

export type RuleIdentifier =
  | "RULE_01_GEOFENCE_CONTAINMENT"
  | "RULE_02_RESTRICTED_ZONE_CLEARANCE"
  | "RULE_03_ALTITUDE_AGL_BOUNDS"
  | "RULE_04_MAX_SPEED_LIMIT"
  | "RULE_05_ENERGY_BUDGET_RESERVE"
  | "RULE_06_RETURN_TO_HOME_FEASIBILITY"
  | "RULE_07_WIND_SPEED_LIMIT"
  | "RULE_08_PHYSICS_SCHEMA_SANITY"
  | "RULE_09_MISSION_TIME_WAYPOINTS_CAP"
  | "RULE_10_CONSTRAINT_INTEGRITY";

// --- Waypoint Contract ---

export interface Waypoint {
  waypoint_id: string;
  longitude: Longitude;
  latitude: Latitude;
  altitude_agl_m: number;      // Height above ground level in metres
  speed_mps: number;           // Velocity in metres per second
  action?: WaypointAction;     // Default: SURVEY
  dwell_s?: number;            // Stationary time in seconds
}

// --- Mission Contract ---

export interface OperatorRestrictions {
  max_altitude_agl_m?: number;
  min_altitude_agl_m?: number;
  max_speed_mps?: number;
  forbidden_zones?: GeoPolygon[];
  notes?: string;
}

export interface Mission {
  schema_version: string;
  mission_id: string;
  objective_type: MissionObjectiveType;
  survey_area: GeoPolygon;
  operator_instruction: string;
  operator_restrictions: OperatorRestrictions;
  status: MissionLifecycleStatus;
  created_at: string; // ISO-8601 UTC
  current_plan_id?: string;
  approved_by?: string;
}

// --- Plan Contract ---

export interface PlanProvenance {
  model_id?: string;
  planner_type: "DETERMINISTIC_GRID" | "AI_ORCHESTRATOR" | "REPAIR_LOOP";
  trigger_reason?: string;
  repair_attempt: number; // 0 for initial, 1..3 for repairs
}

export interface Plan {
  schema_version: string;
  plan_id: string;
  mission_id: string;
  revision: number;
  waypoints: Waypoint[];
  provenance: PlanProvenance;
  estimated_duration_s: number;
  estimated_energy_wh: number;
  created_at: string;
}

// --- Violation & Verification Contract ---

export interface Violation {
  rule_id: RuleIdentifier;
  severity: ViolationSeverity;
  message: string;
  observed: unknown;
  limit: unknown;
  unit?: string;
  waypoint_refs?: string[];
  remediation?: string;
}

export interface RuleCheckResult {
  rule_id: RuleIdentifier;
  name: string;
  passed: boolean;
  message: string;
  observed?: unknown;
  limit?: unknown;
  unit?: string;
}

export interface VerificationResult {
  schema_version: string;
  plan_id: string;
  mission_id: string;
  passed: boolean;
  policy_ref: string;
  world_ref: string;
  drone_ref: string;
  checks: RuleCheckResult[];
  violations: Violation[];
  verified_at: string;
}

// --- Certificate Contract ---

export interface Certificate {
  schema_version: string;
  certificate_id: string;
  mission_id: string;
  plan_id: string;
  verification_ref: string;
  plan_digest: string; // SHA-256 hash of plan waypoints and constraints
  policy_ref: string;
  world_ref: string;
  issued_at: string;
  rule_results: RuleCheckResult[];
  is_valid: boolean;
  invalidation_reason?: string;
}

// --- Simulation Event Contract ---

export interface SurvivorDetectionPayload {
  detection_id: string;
  location: Coordinate;
  confidence: number;
  timestamp: string;
}

export interface LowBatteryPayload {
  current_battery_pct: number;
  remaining_wh: number;
  return_energy_required_wh: number;
  threshold_pct: number;
}

export interface WindSpikePayload {
  observed_speed_mps: number;
  gust_speed_mps: number;
  direction_deg: number;
  limit_mps: number;
}

export interface OperatorMissionChangePayload {
  new_survey_area?: GeoPolygon;
  new_restrictions?: OperatorRestrictions;
  operator_reason: string;
}

export interface NewRestrictedZonePayload {
  zone_id: string;
  name: string;
  boundary: GeoPolygon;
  effective_from: string;
}

export interface TelemetryTickPayload {
  position: Coordinate;
  altitude_agl_m: number;
  speed_mps: number;
  heading_deg: number;
  battery_pct: number;
  battery_wh: number;
  current_waypoint_index: number;
}

export type SimulationEventPayload =
  | SurvivorDetectionPayload
  | LowBatteryPayload
  | WindSpikePayload
  | OperatorMissionChangePayload
  | NewRestrictedZonePayload
  | TelemetryTickPayload
  | Record<string, unknown>;

export interface SimulationEvent {
  event_id: string;
  mission_id: string;
  event_type: SimulationEventType;
  payload: SimulationEventPayload;
  sim_time_s: number;
  sequence: number;
  source: "SIMULATOR" | "OPERATOR" | "WEATHER_SENSOR" | "AI_DETECTOR";
  created_at: string;
}

// --- Supporting Models ---

export interface DroneState {
  drone_id: string;
  location: Coordinate;
  altitude_agl_m: number;
  velocity_mps: number;
  heading_deg: number;
  battery_pct: number;
  battery_wh: number;
  home_position: Coordinate;
  sim_time_s: number;
  current_waypoint_index: number;
  state_revision: number;
  is_airborne: boolean;
}

export interface RestrictedZone {
  zone_id: string;
  name: string;
  boundary: GeoPolygon;
  buffer_m: number;
  active: boolean;
}

export interface WorldState {
  world_revision: number;
  survey_area: GeoPolygon;
  geofence_boundary: GeoPolygon;
  restricted_zones: RestrictedZone[];
  wind_speed_mps: number;
  wind_direction_deg: number;
  ambient_temperature_c: number;
  weather_condition: string;
}

export interface SafetyPolicy {
  policy_id: string;
  version: string;
  min_altitude_agl_m: number;       // default: 15.0
  max_altitude_agl_m: number;       // default: 120.0
  max_speed_mps: number;            // default: 15.0
  max_wind_speed_mps: number;       // default: 12.0
  battery_reserve_pct: number;      // default: 20.0%
  min_return_home_energy_wh: number;// default: 30.0 Wh
  max_mission_time_s: number;       // default: 1800 s (30 min)
  max_waypoints: number;            // default: 100
  restricted_zone_buffer_m: number; // default: 25.0 m
  max_repair_attempts: number;      // frozen: 3
}

// --- AI / Research Contracts ---

export interface TavilySource {
  title: string;
  url: string;
  content_snippet: string;
  score: number;
}

export interface TavilyResearchResult {
  query: string;
  retrieved_at: string;
  sources: TavilySource[];
  summary: string;
  disclaimer: string;
  is_cached: boolean;
}
