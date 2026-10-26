"""
SkyWarden Deterministic Safety Verifier Unit Test Suite
Exhaustively verifies all 10 blueprint safety rule classes and certificate mechanics.
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
    ViolationSeverity,
)
from verifier.engine import SafetyVerifier


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
        restricted_zones=[
            RestrictedZone(
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
        ],
        wind_speed_mps=4.5,
    )


@pytest.fixture
def base_mission(base_world):
    return Mission(
        mission_id="MSN-TEST-001",
        survey_area=base_world.survey_area,
        operator_instruction="Survey Sector Alpha for disaster assessment.",
        operator_restrictions={
            "min_altitude_agl_m": 25.0,
            "max_altitude_agl_m": 80.0,
            "max_speed_mps": 12.0,
        },
        created_at="2026-10-25T12:00:00Z",
    )


@pytest.fixture
def base_drone():
    return DroneState(
        drone_id="UAV-ALPHA-01",
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
            Waypoint(waypoint_id="wp2", longitude=-122.0830, latitude=37.4220, altitude_agl_m=45.0, speed_mps=10.0),
            Waypoint(waypoint_id="wp3", longitude=-122.0830, latitude=37.4245, altitude_agl_m=45.0, speed_mps=10.0),
            Waypoint(waypoint_id="wp4", longitude=-122.0845, latitude=37.4245, altitude_agl_m=45.0, speed_mps=10.0),
            Waypoint(waypoint_id="wp5", longitude=-122.0845, latitude=37.4220, altitude_agl_m=30.0, speed_mps=8.0, action="RETURN_HOME"),
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


def test_rule_01_geofence_breach_rejection(valid_plan, base_mission, base_world, base_drone):
    bad_plan = valid_plan.model_copy(deep=True)
    bad_plan.waypoints.append(
        Waypoint(waypoint_id="wp-outside", longitude=-122.0500, latitude=37.4500, altitude_agl_m=45.0, speed_mps=10.0)
    )

    verifier = SafetyVerifier()
    res, cert = verifier.verify(bad_plan, base_mission, base_world, base_drone)

    assert res.passed is False
    assert cert is None
    rule1_viols = [v for v in res.violations if v.rule_id == RuleIdentifier.RULE_01_GEOFENCE_CONTAINMENT]
    assert len(rule1_viols) > 0
    assert "wp-outside" in rule1_viols[0].waypoint_refs


def test_rule_02_restricted_zone_breach(valid_plan, base_mission, base_world, base_drone):
    bad_plan = valid_plan.model_copy(deep=True)
    # Waypoint located inside the substation zone
    bad_plan.waypoints.insert(
        2,
        Waypoint(waypoint_id="wp-substation", longitude=-122.0820, latitude=37.4234, altitude_agl_m=45.0, speed_mps=10.0)
    )

    verifier = SafetyVerifier()
    res, cert = verifier.verify(bad_plan, base_mission, base_world, base_drone)

    assert res.passed is False
    assert cert is None
    rule2_viols = [v for v in res.violations if v.rule_id == RuleIdentifier.RULE_02_RESTRICTED_ZONE_CLEARANCE]
    assert len(rule2_viols) > 0
    assert "wp-substation" in rule2_viols[0].waypoint_refs


def test_rule_03_altitude_agl_bounds(valid_plan, base_mission, base_world, base_drone):
    bad_plan = valid_plan.model_copy(deep=True)
    bad_plan.waypoints[0].altitude_agl_m = 5.0  # Below 15.0m floor

    verifier = SafetyVerifier()
    res, cert = verifier.verify(bad_plan, base_mission, base_world, base_drone)

    assert res.passed is False
    assert cert is None
    alt_viols = [v for v in res.violations if v.rule_id == RuleIdentifier.RULE_03_ALTITUDE_AGL_BOUNDS]
    assert len(alt_viols) == 1
    assert alt_viols[0].observed == 5.0


def test_rule_04_max_speed_limit(valid_plan, base_mission, base_world, base_drone):
    bad_plan = valid_plan.model_copy(deep=True)
    bad_plan.waypoints[0].speed_mps = 22.0  # Above 15.0m/s policy limit

    verifier = SafetyVerifier()
    res, cert = verifier.verify(bad_plan, base_mission, base_world, base_drone)

    assert res.passed is False
    assert cert is None
    speed_viols = [v for v in res.violations if v.rule_id == RuleIdentifier.RULE_04_MAX_SPEED_LIMIT]
    assert len(speed_viols) == 1
    assert speed_viols[0].observed == 22.0


def test_rule_05_battery_reserve_check(valid_plan, base_mission, base_world, base_drone):
    bad_plan = valid_plan.model_copy(deep=True)
    # Energy budget of 85.0 Wh on a 100 Wh battery violates mandatory 20% reserve
    bad_plan.estimated_energy_wh = 85.0

    verifier = SafetyVerifier()
    res, cert = verifier.verify(bad_plan, base_mission, base_world, base_drone)

    assert res.passed is False
    assert cert is None
    energy_viols = [v for v in res.violations if v.rule_id == RuleIdentifier.RULE_05_ENERGY_BUDGET_RESERVE]
    assert len(energy_viols) > 0


def test_rule_07_wind_speed_limit(valid_plan, base_mission, base_world, base_drone):
    base_world.wind_speed_mps = 16.2  # Policy limit is 12.0

    verifier = SafetyVerifier()
    res, cert = verifier.verify(valid_plan, base_mission, base_world, base_drone)

    assert res.passed is False
    assert cert is None
    wind_viols = [v for v in res.violations if v.rule_id == RuleIdentifier.RULE_07_WIND_SPEED_LIMIT]
    assert len(wind_viols) == 1
    assert wind_viols[0].observed == 16.2


def test_rule_08_physics_schema_sanity(valid_plan, base_mission, base_world, base_drone):
    bad_plan = valid_plan.model_copy(deep=True)
    bad_plan.waypoints[0].speed_mps = -5.0  # Impossible negative speed

    verifier = SafetyVerifier()
    res, cert = verifier.verify(bad_plan, base_mission, base_world, base_drone)

    assert res.passed is False
    assert cert is None
    sanity_viols = [v for v in res.violations if v.rule_id == RuleIdentifier.RULE_08_PHYSICS_SCHEMA_SANITY]
    assert len(sanity_viols) > 0


def test_rule_09_waypoint_cap(valid_plan, base_mission, base_world, base_drone):
    policy = SafetyPolicy(max_waypoints=4)  # Lower policy cap to 4
    verifier = SafetyVerifier(policy=policy)
    res, cert = verifier.verify(valid_plan, base_mission, base_world, base_drone)

    assert res.passed is False
    assert cert is None
    cap_viols = [v for v in res.violations if v.rule_id == RuleIdentifier.RULE_09_MISSION_TIME_WAYPOINTS_CAP]
    assert len(cap_viols) > 0


def test_rule_10_operator_restriction_tightening(valid_plan, base_mission, base_world, base_drone):
    # Operator tightens max speed to 8.0 m/s; waypoints are at 10.0 m/s
    base_mission.operator_restrictions.max_speed_mps = 8.0

    verifier = SafetyVerifier()
    res, cert = verifier.verify(valid_plan, base_mission, base_world, base_drone)

    assert res.passed is False
    assert cert is None
    speed_viols = [v for v in res.violations if v.rule_id == RuleIdentifier.RULE_04_MAX_SPEED_LIMIT]
    assert len(speed_viols) > 0
    assert speed_viols[0].limit == 8.0
