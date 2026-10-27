"""
SkyWarden Contract Fixture Verification Tests
Validates that all valid and invalid fixtures match canonical Pydantic v2 schemas.
"""

import json
from pathlib import Path
import pytest
from verifier.models import (
    Mission,
    Plan,
    Certificate,
    SimulationEvent,
)
from verifier.engine import SafetyVerifier
from verifier.models import WorldState, DroneState, GeoPolygon

FIXTURES_DIR = Path(__file__).parent.parent / "contracts" / "fixtures"


def test_valid_mission_fixture():
    path = FIXTURES_DIR / "valid" / "mission_valid.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    mission = Mission.model_validate(data)
    assert mission.mission_id == "msn-val-001"
    assert mission.objective_type.value == "SURVEY_AREA"


def test_valid_plan_fixture():
    path = FIXTURES_DIR / "valid" / "plan_valid.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    plan = Plan.model_validate(data)
    assert plan.plan_id == "pln-val-001"
    assert len(plan.waypoints) == 7


def test_valid_certificate_fixture():
    path = FIXTURES_DIR / "valid" / "certificate_valid.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    cert = Certificate.model_validate(data)
    assert cert.certificate_id == "cert-val-001"
    assert cert.is_valid is True


def test_valid_event_fixtures():
    event_files = [
        "event_low_battery.json",
        "event_wind_spike.json",
        "event_survivor_detected.json",
        "event_new_restricted_zone.json",
        "event_operator_change.json",
    ]
    for filename in event_files:
        path = FIXTURES_DIR / "valid" / filename
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        event = SimulationEvent.model_validate(data)
        assert event.event_id.startswith("EVT-")
        assert event.sequence > 0


def test_invalid_plan_geofence_fixture():
    path = FIXTURES_DIR / "invalid" / "plan_geofence_violation.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    expected_viols = data.pop("expected_violations", [])
    plan = Plan.model_validate(data)

    # Verify against standard world/mission
    mission_path = FIXTURES_DIR / "valid" / "mission_valid.json"
    with open(mission_path, "r", encoding="utf-8") as f:
        mission_data = json.load(f)
    mission = Mission.model_validate(mission_data)

    world = WorldState(
        survey_area=mission.survey_area,
        geofence_boundary=mission.survey_area,
    )
    drone = DroneState(
        location=mission.survey_area.coordinates[0][0],
        home_position=mission.survey_area.coordinates[0][0],
    )

    verifier = SafetyVerifier()
    res, cert = verifier.verify(plan, mission, world, drone)
    assert res.passed is False
    assert cert is None
    assert any(v.rule_id.value == expected_viols[0]["rule_id"] for v in res.violations)
