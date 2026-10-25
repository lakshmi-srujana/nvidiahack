"""
SkyWarden Verification & Simulator Unit Test Suite
"""

import pytest
from verifier.models import (
    Mission,
    Plan,
    Waypoint,
    GeoPolygon,
    WorldState,
    SafetyPolicy,
    DroneState,
    RestrictedZone,
    RuleIdentifier,
)
from verifier.engine import SafetyVerifier
from simulator.engine import MissionSimulator


@pytest.fixture
def base_world():
    return WorldState(
        world_revision=1,
        survey_area=GeoPolygon(
            coordinates=[[
                [-122.0850, 37.4215],
                [-122.0800, 37.4215],
                [-122.0800, 37.4255],
                [-122.0850, 37.4255],
                [-122.0850, 37.4215],
            ]]
        ),
        geofence_boundary=GeoPolygon(
            coordinates=[[
                [-122.0900, 37.4200],
                [-122.0750, 37.4200],
                [-122.0750, 37.4300],
                [-122.0900, 37.4300],
                [-122.0900, 37.4200],
            ]]
        ),
        wind_speed_mps=4.5,
    )


@pytest.fixture
def base_mission(base_world):
    return Mission(
        mission_id="MSN-TEST-001",
        survey_area=base_world.survey_area,
        operator_instruction="Survey Sector Alpha for disaster assessment.",
        created_at="2026-10-25T12:00:00Z",
    )


@pytest.fixture
def base_drone():
    return DroneState(
        location=(-122.0845, 37.4220),
        home_position=(-122.0845, 37.4220),
        altitude_agl_m=0.0,
        battery_pct=100.0,
        battery_wh=100.0,
    )


@pytest.fixture
def valid_plan():
    return Plan(
        plan_id="PLN-VALID-01",
        mission_id="MSN-TEST-001",
        waypoints=[
            Waypoint(waypoint_id="wp1", longitude=-122.0845, latitude=37.4220, altitude_agl_m=45.0, speed_mps=10.0),
            Waypoint(waypoint_id="wp2", longitude=-122.0810, latitude=37.4220, altitude_agl_m=45.0, speed_mps=10.0),
            Waypoint(waypoint_id="wp3", longitude=-122.0810, latitude=37.4240, altitude_agl_m=45.0, speed_mps=10.0),
            Waypoint(waypoint_id="wp4", longitude=-122.0845, latitude=37.4240, altitude_agl_m=45.0, speed_mps=10.0),
        ],
        estimated_duration_s=360.0,
        estimated_energy_wh=32.0,
        created_at="2026-10-25T12:05:00Z",
    )


def test_valid_plan_certification(valid_plan, base_mission, base_world, base_drone):
    verifier = SafetyVerifier()
    res, cert = verifier.verify(valid_plan, base_mission, base_world, base_drone)

    assert res.passed is True
    assert len(res.violations) == 0
    assert cert is not None
    assert cert.is_valid is True
    assert cert.plan_id == valid_plan.plan_id
    assert len(cert.plan_digest) == 64  # SHA-256


def test_geofence_breach_rejection(valid_plan, base_mission, base_world, base_drone):
    # Add a waypoint way outside the geofence
    bad_plan = valid_plan.model_copy(deep=True)
    bad_plan.waypoints.append(
        Waypoint(waypoint_id="wp-outside", longitude=-122.0500, latitude=37.4500, altitude_agl_m=45.0, speed_mps=10.0)
    )

    verifier = SafetyVerifier()
    res, cert = verifier.verify(bad_plan, base_mission, base_world, base_drone)

    assert res.passed is False
    assert cert is None  # Never issue partial certificates!
    rule1_viols = [v for v in res.violations if v.rule_id == RuleIdentifier.RULE_01_GEOFENCE_CONTAINMENT]
    assert len(rule1_viols) > 0
    assert "wp-outside" in rule1_viols[0].waypoint_refs


def test_altitude_limits_enforced(valid_plan, base_mission, base_world, base_drone):
    bad_plan = valid_plan.model_copy(deep=True)
    bad_plan.waypoints[0].altitude_agl_m = 5.0  # Below 15.0m min

    verifier = SafetyVerifier()
    res, cert = verifier.verify(bad_plan, base_mission, base_world, base_drone)

    assert res.passed is False
    assert cert is None
    alt_viols = [v for v in res.violations if v.rule_id == RuleIdentifier.RULE_03_ALTITUDE_AGL_BOUNDS]
    assert len(alt_viols) == 1
    assert alt_viols[0].observed == 5.0


def test_wind_limit_rejection(valid_plan, base_mission, base_world, base_drone):
    base_world.wind_speed_mps = 16.2  # Policy limit is 12.0

    verifier = SafetyVerifier()
    res, cert = verifier.verify(valid_plan, base_mission, base_world, base_drone)

    assert res.passed is False
    assert cert is None
    wind_viols = [v for v in res.violations if v.rule_id == RuleIdentifier.RULE_07_WIND_SPEED_LIMIT]
    assert len(wind_viols) == 1
    assert wind_viols[0].observed == 16.2


def test_simulator_repair_cap_enforcement(valid_plan, base_mission, base_world, base_drone):
    sim = MissionSimulator(base_drone, base_world, base_mission, valid_plan)

    # First 3 attempts are allowed
    assert sim.record_repair_attempt() is True
    assert sim.repair_attempts == 1
    assert sim.record_repair_attempt() is True
    assert sim.repair_attempts == 2
    assert sim.record_repair_attempt() is True
    assert sim.repair_attempts == 3

    # 4th attempt must be rejected and trigger operator intervention
    assert sim.record_repair_attempt() is False
    assert sim.intervention_required is True
    assert sim.repair_attempts == 4
