"""
SkyWarden Discrete-Time Mission Simulator Tests
Validates tick engine, battery mechanics, trigger injections, and Decision A08 retry cap.
"""

import pytest
from verifier.models import (
    Mission,
    Plan,
    Waypoint,
    GeoPolygon,
    WorldState,
    DroneState,
    SimulationEventType,
)
from simulator.engine import MissionSimulator


@pytest.fixture
def sim_setup():
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
    world = WorldState(
        world_revision=1,
        survey_area=survey_area,
        geofence_boundary=geofence,
        wind_speed_mps=4.0,
    )
    drone = DroneState(
        drone_id="UAV-01",
        location=(-122.0845, 37.4220),
        home_position=(-122.0845, 37.4220),
        altitude_agl_m=0.0,
        battery_pct=100.0,
        battery_wh=100.0,
        is_airborne=True,
    )
    mission = Mission(
        mission_id="MSN-SIM-01",
        survey_area=survey_area,
        operator_instruction="Simulate sector survey.",
        created_at="2026-10-25T12:00:00Z",
    )
    plan = Plan(
        plan_id="PLN-SIM-01",
        mission_id="MSN-SIM-01",
        waypoints=[
            Waypoint(waypoint_id="wp1", longitude=-122.0845, latitude=37.4220, altitude_agl_m=40.0, speed_mps=10.0),
            Waypoint(waypoint_id="wp2", longitude=-122.0840, latitude=37.4220, altitude_agl_m=40.0, speed_mps=10.0),
        ],
        estimated_duration_s=60.0,
        estimated_energy_wh=5.0,
        created_at="2026-10-25T12:00:00Z",
    )
    return MissionSimulator(drone, world, mission, plan)


def test_simulator_tick_progression(sim_setup):
    sim = sim_setup
    assert sim.sim_time_s == 0.0

    # Advance 1 second
    d = sim.tick(1.0)
    assert sim.sim_time_s == 1.0
    assert d.battery_wh < 100.0  # Consumed cruise energy


def test_simulator_waypoint_reached(sim_setup):
    sim = sim_setup
    # Drone starts right at wp1; first tick should reach wp1
    sim.tick(1.0)
    assert sim.drone.current_waypoint_index >= 1
    events = [e for e in sim.events if e.event_type == SimulationEventType.WAYPOINT_REACHED]
    assert len(events) >= 1
    assert events[0].payload["waypoint_id"] == "wp1"


def test_simulator_trigger_survivor_detected(sim_setup):
    sim = sim_setup
    evt = sim.inject_survivor_detected(confidence=0.96)
    assert evt.event_type == SimulationEventType.SURVIVOR_DETECTED
    assert evt.payload["confidence"] == 0.96
    assert evt.source == "AI_DETECTOR"


def test_simulator_trigger_low_battery(sim_setup):
    sim = sim_setup
    sim.drone.battery_pct = 18.0
    sim.drone.battery_wh = 18.0
    evt = sim.inject_low_battery()
    assert evt.event_type == SimulationEventType.LOW_BATTERY
    assert evt.payload["current_battery_pct"] == 18.0


def test_simulator_trigger_wind_spike(sim_setup):
    sim = sim_setup
    evt = sim.inject_wind_spike(speed_mps=15.0)
    assert evt.event_type == SimulationEventType.WIND_SPIKE
    assert sim.world.wind_speed_mps == 15.0
    assert evt.payload["observed_speed_mps"] == 15.0


def test_simulator_trigger_new_restricted_zone(sim_setup):
    sim = sim_setup
    poly = GeoPolygon(
        coordinates=[[
            [-122.0835, 37.4225],
            [-122.0825, 37.4225],
            [-122.0825, 37.4235],
            [-122.0835, 37.4235],
            [-122.0835, 37.4225],
        ]]
    )
    evt = sim.inject_new_restricted_zone("ZONE-SURGE-NEW", "Surge Channel", poly)
    assert evt.event_type == SimulationEventType.NEW_RESTRICTED_ZONE
    assert len(sim.world.restricted_zones) == 1
    assert sim.world.world_revision == 2


def test_simulator_decision_a08_repair_cap(sim_setup):
    sim = sim_setup
    # Exactly 3 automatic repairs allowed
    assert sim.record_repair_attempt() is True
    assert sim.record_repair_attempt() is True
    assert sim.record_repair_attempt() is True
    assert sim.intervention_required is False

    # 4th attempt must halt autonomous repairs and demand operator intervention
    assert sim.record_repair_attempt() is False
    assert sim.intervention_required is True
    assert sim.repair_attempts == 4
