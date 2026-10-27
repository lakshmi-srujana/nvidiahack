import type {
  Mission,
  Plan,
  WorldState,
  SafetyPolicy,
  DroneState,
  TavilyResearchResult,
} from "../contracts/contracts";

export const DEFAULT_SAFETY_POLICY: SafetyPolicy = {
  policy_id: "POL-ALPHA-2026",
  version: "1.0.0",
  min_altitude_agl_m: 15.0,
  max_altitude_agl_m: 120.0,
  max_speed_mps: 15.0,
  max_wind_speed_mps: 12.0,
  battery_reserve_pct: 20.0,
  min_return_home_energy_wh: 20.0,
  max_mission_time_s: 1800.0,
  max_waypoints: 100,
  restricted_zone_buffer_m: 25.0,
  max_repair_attempts: 3,
};

export const INITIAL_DRONE_STATE: DroneState = {
  drone_id: "UAV-ALPHA-01",
  location: [-122.0845, 37.4220],
  altitude_agl_m: 0.0,
  velocity_mps: 0.0,
  heading_deg: 45.0,
  battery_pct: 100.0,
  battery_wh: 100.0,
  home_position: [-122.0845, 37.4220],
  sim_time_s: 0.0,
  current_waypoint_index: 0,
  state_revision: 1,
  is_airborne: false,
};

export const INITIAL_WORLD_STATE: WorldState = {
  world_revision: 1,
  survey_area: {
    type: "Polygon",
    coordinates: [
      [
        [-122.0850, 37.4215],
        [-122.0800, 37.4215],
        [-122.0800, 37.4255],
        [-122.0850, 37.4255],
        [-122.0850, 37.4215],
      ],
    ],
  },
  geofence_boundary: {
    type: "Polygon",
    coordinates: [
      [
        [-122.0900, 37.4200],
        [-122.0750, 37.4200],
        [-122.0750, 37.4300],
        [-122.0900, 37.4300],
        [-122.0900, 37.4200],
      ],
    ],
  },
  restricted_zones: [
    {
      zone_id: "ZONE-HAZARD-01",
      name: "High Voltage Substation",
      boundary: {
        type: "Polygon",
        coordinates: [
          [
            [-122.0825, 37.4230],
            [-122.0815, 37.4230],
            [-122.0815, 37.4238],
            [-122.0825, 37.4238],
            [-122.0825, 37.4230],
          ],
        ],
      },
      buffer_m: 25.0,
      active: true,
    },
  ],
  wind_speed_mps: 4.8,
  wind_direction_deg: 240.0,
  ambient_temperature_c: 18.5,
  weather_condition: "PARTLY_CLOUDY",
};

export const INITIAL_MISSION: Mission = {
  schema_version: "1.0.0",
  mission_id: "MSN-ALPHA-2026",
  objective_type: "SURVEY_AREA",
  survey_area: INITIAL_WORLD_STATE.survey_area,
  operator_instruction:
    "Conduct autonomous grid survey across Sector Alpha riverbank to locate stranded hikers following seasonal flash flooding.",
  operator_restrictions: {
    min_altitude_agl_m: 25.0,
    max_altitude_agl_m: 80.0,
    max_speed_mps: 12.0,
  },
  status: "DRAFT",
  created_at: new Date().toISOString(),
};

export const INITIAL_VALID_PLAN: Plan = {
  schema_version: "1.0.0",
  plan_id: "PLN-ALPHA-001",
  mission_id: "MSN-ALPHA-2026",
  revision: 1,
  waypoints: [
    {
      waypoint_id: "WP-01",
      longitude: -122.0845,
      latitude: 37.4220,
      altitude_agl_m: 45.0,
      speed_mps: 10.0,
      action: "TRANSIT",
      dwell_s: 0,
    },
    {
      waypoint_id: "WP-02",
      longitude: -122.0830,
      latitude: 37.4220,
      altitude_agl_m: 45.0,
      speed_mps: 10.0,
      action: "SURVEY",
      dwell_s: 0,
    },
    {
      waypoint_id: "WP-03",
      longitude: -122.0830,
      latitude: 37.4245,
      altitude_agl_m: 45.0,
      speed_mps: 10.0,
      action: "SURVEY",
      dwell_s: 0,
    },
    {
      waypoint_id: "WP-04",
      longitude: -122.0842,
      latitude: 37.4245,
      altitude_agl_m: 45.0,
      speed_mps: 10.0,
      action: "SURVEY",
      dwell_s: 0,
    },
    {
      waypoint_id: "WP-05",
      longitude: -122.0845,
      latitude: 37.4220,
      altitude_agl_m: 30.0,
      speed_mps: 8.0,
      action: "RETURN_HOME",
      dwell_s: 0,
    },
  ],
  provenance: {
    planner_type: "DETERMINISTIC_GRID",
    repair_attempt: 0,
  },
  estimated_duration_s: 380.0,
  estimated_energy_wh: 36.5,
  created_at: new Date().toISOString(),
};

export const MOCK_TAVILY_RESEARCH: TavilyResearchResult = {
  query: "Sector Alpha flooding water level and local low-altitude flight advisories",
  retrieved_at: new Date().toISOString(),
  sources: [
    {
      title: "Regional Emergency Response Dispatch - Hydrology Alert",
      url: "https://emergency.gov/alerts/sector-alpha-flood-2026",
      content_snippet:
        "Water elevation crest reached 4.2m along north trail. Search operations prioritized for daylight hours. Keep UAS above 25m AGL near powerlines.",
      score: 0.94,
    },
    {
      title: "Aviation Weather Notice: Sector Alpha Valley Winds",
      url: "https://weather.aviation.org/notam/sector-alpha",
      content_snippet:
        "Moderate gusting expected after 14:00 local time. Max gusts up to 11.5 m/s. Clear visibility 10+ km.",
      score: 0.88,
    },
  ],
  summary:
    "Ground reports confirm impassable road access on north bank with suspected hikers isolated near grid coordinates (-122.0834, 37.4241). Airspace clear of civilian aircraft; powerline hazard active near substation.",
  disclaimer:
    "NON-AUTHORITATIVE NOTICE: Tavily intelligence and AI analysis are advisory only. They cannot override platform safety policy, relax flight restrictions, or issue mission certificates.",
  is_cached: true,
};

export const DAM_SURGE_ZONE = {
  zone_id: "ZONE-DAM-SURGE-01",
  name: "Dam Spillway Emergency Surge Inundation Channel",
  boundary: {
    type: "Polygon" as const,
    coordinates: [
      [
        [-122.0838, 37.4222],
        [-122.0828, 37.4222],
        [-122.0828, 37.4248],
        [-122.0838, 37.4248],
        [-122.0838, 37.4222],
      ] as [number, number][],
    ],
  },
  buffer_m: 30.0,
  active: true,
};

export const DAM_BREACH_PLAN: Plan = {
  schema_version: "1.0.0",
  plan_id: "PLN-DAM-UNADAPTED",
  mission_id: "MSN-ALPHA-2026",
  revision: 1,
  waypoints: [
    {
      waypoint_id: "WP-DAM-01",
      longitude: -122.0845,
      latitude: 37.4220,
      altitude_agl_m: 45.0,
      speed_mps: 10.0,
      action: "TRANSIT",
      dwell_s: 0,
    },
    {
      waypoint_id: "WP-DAM-02",
      longitude: -122.0833,
      latitude: 37.4235,
      altitude_agl_m: 45.0,
      speed_mps: 10.0,
      action: "SURVEY",
      dwell_s: 0,
    },
    {
      waypoint_id: "WP-DAM-03",
      longitude: -122.0845,
      latitude: 37.4220,
      altitude_agl_m: 30.0,
      speed_mps: 8.0,
      action: "RETURN_HOME",
      dwell_s: 0,
    },
  ],
  provenance: {
    planner_type: "AI_ORCHESTRATOR",
    repair_attempt: 0,
  },
  estimated_duration_s: 220.0,
  estimated_energy_wh: 22.0,
  created_at: new Date().toISOString(),
};

export const BATTERY_CRITICAL_PLAN: Plan = {
  schema_version: "1.0.0",
  plan_id: "PLN-BATTERY-EXCESSIVE",
  mission_id: "MSN-ALPHA-2026",
  revision: 1,
  waypoints: INITIAL_VALID_PLAN.waypoints,
  provenance: {
    planner_type: "AI_ORCHESTRATOR",
    repair_attempt: 0,
  },
  estimated_duration_s: 900.0,
  estimated_energy_wh: 85.0,
  created_at: new Date().toISOString(),
};
