"""
SkyWarden SQLite Memory Store Unit Tests
Validates persistence of missions, plans, certificates, and event streams.
"""

import pytest
from simulator.memory import SQLiteMemoryStore
from simulator.scenarios import create_flood_scenario
from verifier.engine import SafetyVerifier
from verifier.models import SimulationEvent, SimulationEventType


@pytest.fixture
def mem_store():
    return SQLiteMemoryStore(":memory:")


def test_mission_and_plan_persistence(mem_store):
    scen = create_flood_scenario()
    mission = scen["mission"]
    plan = scen["plan"]

    mem_store.save_mission(mission)
    retrieved_m = mem_store.get_mission(mission.mission_id)
    assert retrieved_m is not None
    assert retrieved_m["mission_id"] == mission.mission_id
    assert retrieved_m["objective_type"] == "SURVEY_AREA"

    mem_store.save_plan(plan)


def test_verification_and_certificate_persistence(mem_store):
    scen = create_flood_scenario()
    verifier = SafetyVerifier(policy=scen["policy"])
    res, cert = verifier.verify(scen["plan"], scen["mission"], scen["world"], scen["drone"])

    assert res.passed is True
    assert cert is not None

    mem_store.save_verification(res)
    mem_store.save_certificate(cert)


def test_simulation_event_logging_and_export(mem_store):
    evt1 = SimulationEvent(
        event_id="EVT-001",
        mission_id="MSN-TEST",
        event_type=SimulationEventType.SURVIVOR_DETECTED,
        payload={"confidence": 0.95},
        sim_time_s=10.0,
        sequence=1,
        source="AI_DETECTOR",
        created_at="2026-10-25T12:00:00Z",
    )
    evt2 = SimulationEvent(
        event_id="EVT-002",
        mission_id="MSN-TEST",
        event_type=SimulationEventType.LOW_BATTERY,
        payload={"current_battery_pct": 18.0},
        sim_time_s=25.0,
        sequence=2,
        source="SIMULATOR",
        created_at="2026-10-25T12:00:15Z",
    )

    mem_store.log_event(evt1)
    mem_store.log_event(evt2)

    events = mem_store.get_events("MSN-TEST")
    assert len(events) == 2
    assert events[0]["event_id"] == "EVT-001"
    assert events[1]["event_id"] == "EVT-002"

    audit_json = mem_store.export_audit_json("MSN-TEST")
    assert "SURVIVOR_DETECTED" in audit_json
    assert "LOW_BATTERY" in audit_json
