import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def client():
    return TestClient(create_app(Settings(_env_file=None, app_mode="test")))


def test_certified_scenario_launches_and_safety_event_stops_motion():
    with client() as api:
        assert api.post("/api/v1/demo/launch").status_code == 409
        verified = api.post("/api/v1/demo/verify").json()
        assert verified["status"] == "CERTIFIED"
        assert verified["certificate"]["plan_digest"]
        assert api.post("/api/v1/demo/launch").json()["status"] == "ACTIVE"
        assert api.post("/api/v1/demo/tick").json()["drone"]["sim_time_s"] == 1
        event = api.post("/api/v1/demo/event", json={"family": "WIND_SPIKE"}).json()
        assert event["status"] == "INTERVENTION_REQUIRED"
        assert event["certificate"] is None
        assert api.post("/api/v1/demo/tick").status_code == 409
        assert api.post("/api/v1/demo/verify").json()["status"] == "REJECTED"
        assert api.post("/api/v1/demo/launch").status_code == 409


def test_unsafe_scenarios_reject_and_ai_is_opt_in():
    with client() as api:
        for name in ("dam", "wind", "battery"):
            assert api.post(f"/api/v1/demo/scenario/{name}").status_code == 200
            result = api.post("/api/v1/demo/verify").json()
            assert result["status"] == "REJECTED"
            assert result["certificate"] is None
            assert result["verdict"]["violations"]
            assert api.post("/api/v1/demo/launch").status_code == 409
        assert api.post("/api/v1/demo/ai-plan").status_code == 503


def test_operator_survey_requires_survey_instruction_and_can_launch():
    with client() as api:
        payload = {"instruction": "Survey the approved area", "west": -122.085,
                   "east": -122.083, "south": 37.4215, "north": 37.4235}
        created = api.post("/api/v1/demo/survey", json=payload)
        assert created.status_code == 200
        assert created.json()["scenario"] == "custom"
        assert api.post("/api/v1/demo/verify").json()["status"] == "CERTIFIED"
        assert api.post("/api/v1/demo/launch").json()["status"] == "ACTIVE"
        assert api.post("/api/v1/demo/survey", json=payload).status_code == 409

    with client() as api:
        payload["instruction"] = "Deliver a package"
        assert api.post("/api/v1/demo/survey", json=payload).status_code == 422


def test_low_battery_rejected_even_when_plan_energy_is_small():
    with client() as api:
        demo = api.app.state.demo
        demo.sim.drone.battery_wh = 21
        demo.sim.drone.battery_pct = 21
        demo.plan.estimated_energy_wh = 2
        result = api.post("/api/v1/demo/verify").json()
        assert result["status"] == "REJECTED"
        assert any(v["rule_id"] == "RULE_05_ENERGY_BUDGET_RESERVE" for v in result["verdict"]["violations"])


def test_event_replan_is_reverified_and_repairs_are_bounded():
    with client() as api:
        api.post("/api/v1/demo/verify")
        api.post("/api/v1/demo/launch")
        api.post("/api/v1/demo/tick")
        api.post("/api/v1/demo/event", json={"family": "SURVIVOR_DETECTED"})
        result = api.post("/api/v1/demo/replan").json()
        assert result["status"] == "CERTIFIED"
        assert result["plan"]["revision"] == 2
        assert result["certificate"]["plan_id"] == result["plan"]["plan_id"]
        assert api.post("/api/v1/demo/launch").json()["status"] == "ACTIVE"
        api.post("/api/v1/demo/event", json={"family": "WIND_SPIKE"})
        for attempt in range(1, 4):
            result = api.post("/api/v1/demo/replan").json()
            assert result["status"] == "REJECTED"
            assert result["certificate"] is None
            assert result["replan_attempts"] == attempt
        assert api.post("/api/v1/demo/replan").status_code == 409


@pytest.mark.parametrize("family", [
    "SURVIVOR_DETECTED", "LOW_BATTERY", "WIND_SPIKE",
    "NEW_RESTRICTED_ZONE", "OPERATOR_MISSION_CHANGE",
])
def test_each_approved_event_pauses_and_invalidates_certificate(family):
    with client() as api:
        assert api.post("/api/v1/demo/verify").json()["certificate"]
        assert api.post("/api/v1/demo/launch").status_code == 200
        result = api.post("/api/v1/demo/event", json={"family": family})
        assert result.status_code == 200
        body = result.json()
        assert body["status"] == "INTERVENTION_REQUIRED"
        assert body["certificate"] is None
        assert body["events"][-1]["event_type"] == family
        assert api.post("/api/v1/demo/tick").status_code == 409
