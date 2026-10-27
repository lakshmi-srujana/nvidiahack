"""
SkyWarden Pre-Seeded Simulation Scenarios
Implements the 4 core disaster scenarios required by Developer B in CONTRACTS.md:
1. Flash Flood Search (Nominal)
2. Dam Spillway Breach & Surge Channel Inundation
3. High Wind Severe Weather Breach
4. Critical Low-Battery Emergency RTH
"""

from typing import Dict, Any
from verifier.models import (
    Mission,
    Plan,
    Waypoint,
    GeoPolygon,
    WorldState,
    SafetyPolicy,
    DroneState,
    RestrictedZone,
    PlanProvenance,
)


def get_default_policy() -> SafetyPolicy:
    return SafetyPolicy(
        policy_id="POL-ALPHA-2026",
        version="1.0.0",
        min_altitude_agl_m=15.0,
        max_altitude_agl_m=120.0,
        max_speed_mps=15.0,
        max_wind_speed_mps=12.0,
        battery_reserve_pct=20.0,
        total_battery_wh=100.0,
        min_return_home_energy_wh=20.0,
        max_mission_time_s=1800.0,
        max_waypoints=100,
        restricted_zone_buffer_m=25.0,
        max_repair_attempts=3,
    )


def create_flood_scenario() -> Dict[str, Any]:
    """
    Scenario 1: Flash Flood Search (Nominal)
    Systematic search and survey across Sector Alpha riverbank for isolated hikers.
    Weather is calm; all waypoints are strictly geofenced. Passes all checks and certifies.
    """
    survey_area = GeoPolygon(
        coordinates=[[
            [-122.0850, 37.4215],
            [-122.0800, 37.4215],
            [-122.0800, 37.4255],
            [-122.0850, 37.4255],
            [-122.0850, 37.4215],
        ]]
    )
    geofence = GeoPolygon(
        coordinates=[[
            [-122.0900, 37.4200],
            [-122.0750, 37.4200],
            [-122.0750, 37.4300],
            [-122.0900, 37.4300],
            [-122.0900, 37.4200],
        ]]
    )
    hazard_zone = RestrictedZone(
        zone_id="ZONE-HAZARD-01",
        name="High Voltage Substation",
        boundary=GeoPolygon(
            coordinates=[[
                [-122.0825, 37.4230],
                [-122.0815, 37.4230],
                [-122.0815, 37.4238],
                [-122.0825, 37.4238],
                [-122.0825, 37.4230],
            ]]
        ),
        buffer_m=25.0,
        active=True,
    )

    world = WorldState(
        world_revision=1,
        survey_area=survey_area,
        geofence_boundary=geofence,
        restricted_zones=[hazard_zone],
        wind_speed_mps=4.5,
        wind_direction_deg=240.0,
        ambient_temperature_c=18.5,
        weather_condition="PARTLY_CLOUDY",
    )

    drone = DroneState(
        drone_id="UAV-ALPHA-01",
        location=(-122.0845, 37.4220),
        home_position=(-122.0845, 37.4220),
        altitude_agl_m=0.0,
        velocity_mps=0.0,
        heading_deg=45.0,
        battery_pct=100.0,
        battery_wh=100.0,
    )

    mission = Mission(
        mission_id="MSN-FLOOD-01",
        survey_area=survey_area,
        operator_instruction="Conduct autonomous grid survey across Sector Alpha riverbank to locate stranded hikers following seasonal flash flooding.",
        operator_restrictions={
            "min_altitude_agl_m": 25.0,
            "max_altitude_agl_m": 80.0,
            "max_speed_mps": 12.0,
        },
        status="DRAFT",
        created_at="2026-10-25T12:00:00Z",
    )

    plan = Plan(
        plan_id="PLN-FLOOD-01",
        mission_id="MSN-FLOOD-01",
        revision=1,
        waypoints=[
            Waypoint(waypoint_id="WP-01", longitude=-122.0845, latitude=37.4220, altitude_agl_m=45.0, speed_mps=10.0, action="TRANSIT"),
            Waypoint(waypoint_id="WP-02", longitude=-122.0830, latitude=37.4220, altitude_agl_m=45.0, speed_mps=10.0, action="SURVEY"),
            Waypoint(waypoint_id="WP-03", longitude=-122.0830, latitude=37.4245, altitude_agl_m=45.0, speed_mps=10.0, action="SURVEY"),
            Waypoint(waypoint_id="WP-04", longitude=-122.0842, latitude=37.4245, altitude_agl_m=45.0, speed_mps=10.0, action="SURVEY"),
            Waypoint(waypoint_id="WP-05", longitude=-122.0845, latitude=37.4220, altitude_agl_m=30.0, speed_mps=8.0, action="RETURN_HOME"),
        ],
        provenance=PlanProvenance(planner_type="DETERMINISTIC_GRID", repair_attempt=0),
        estimated_duration_s=380.0,
        estimated_energy_wh=36.5,
        created_at="2026-10-25T12:05:00Z",
    )

    return {
        "id": "scenario_flood",
        "title": "Flash Flood Search (Nominal)",
        "world": world,
        "drone": drone,
        "mission": mission,
        "plan": plan,
        "policy": get_default_policy(),
    }


def create_dam_breach_scenario() -> Dict[str, Any]:
    """
    Scenario 2: Dam Spillway Breach & Surge Channel Inundation
    Dam structure releases torrent into downstream surge channel.
    An emergency exclusion zone is active; an unadapted plan breaches the surge zone,
    proving that safety validation rejects the unverified route until repaired.
    """
    base = create_flood_scenario()
    world = base["world"]

    dam_surge_zone = RestrictedZone(
        zone_id="ZONE-DAM-SURGE-01",
        name="Dam Spillway Emergency Surge Inundation Channel",
        boundary=GeoPolygon(
            coordinates=[[
                [-122.0838, 37.4222],
                [-122.0828, 37.4222],
                [-122.0828, 37.4248],
                [-122.0838, 37.4248],
                [-122.0838, 37.4222],
            ]]
        ),
        buffer_m=30.0,
        active=True,
    )
    world.restricted_zones.append(dam_surge_zone)
    world.world_revision += 1

    # Plan whose waypoints cross the active dam surge zone
    plan = Plan(
        plan_id="PLN-DAM-UNADAPTED",
        mission_id="MSN-FLOOD-01",
        revision=1,
        waypoints=[
            Waypoint(waypoint_id="WP-DAM-01", longitude=-122.0845, latitude=37.4220, altitude_agl_m=45.0, speed_mps=10.0, action="TRANSIT"),
            Waypoint(waypoint_id="WP-DAM-02", longitude=-122.0833, latitude=37.4235, altitude_agl_m=45.0, speed_mps=10.0, action="SURVEY"),
            Waypoint(waypoint_id="WP-DAM-03", longitude=-122.0845, latitude=37.4220, altitude_agl_m=30.0, speed_mps=8.0, action="RETURN_HOME"),
        ],
        provenance=PlanProvenance(planner_type="AI_ORCHESTRATOR", repair_attempt=0),
        estimated_duration_s=220.0,
        estimated_energy_wh=22.0,
        created_at="2026-10-25T12:05:00Z",
    )

    return {
        "id": "scenario_dam",
        "title": "Dam Breach & Surge Channel Inundation",
        "world": world,
        "drone": base["drone"],
        "mission": base["mission"],
        "plan": plan,
        "policy": get_default_policy(),
    }


def create_high_wind_scenario() -> Dict[str, Any]:
    """
    Scenario 3: Severe High Wind Violation
    Valley storm generates sustained wind speed of 15.5 m/s (Limit: 12.0 m/s).
    Verifier strictly blocks launch and revokes certification.
    """
    base = create_flood_scenario()
    world = base["world"]
    world.wind_speed_mps = 15.5
    world.weather_condition = "THUNDERSTORM"

    return {
        "id": "scenario_wind",
        "title": "Severe High Wind Violation",
        "world": world,
        "drone": base["drone"],
        "mission": base["mission"],
        "plan": base["plan"],
        "policy": get_default_policy(),
    }


def create_battery_critical_scenario() -> Dict[str, Any]:
    """
    Scenario 4: Critical Low-Battery Emergency RTH
    Drone battery is at 18.0% / 18.0 Wh, which breaches the mandatory 20% reserve threshold.
    Safety verifier rejects long survey plans (85.0 Wh required) and enforces immediate Return-To-Home contingency.
    """
    base = create_flood_scenario()
    drone = base["drone"]
    drone.battery_pct = 18.0
    drone.battery_wh = 18.0

    plan = base["plan"].model_copy(deep=True)
    plan.estimated_energy_wh = 85.0

    return {
        "id": "scenario_battery",
        "title": "Critical Low-Battery Emergency RTH",
        "world": base["world"],
        "drone": drone,
        "mission": base["mission"],
        "plan": plan,
        "policy": get_default_policy(),
    }
