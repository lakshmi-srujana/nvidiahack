"""
SkyWarden Discrete-Time Mission Simulator
Simulates a single drone under discrete ticks (1Hz default),
evaluating telemetry, tracking battery drain, and processing injected triggers.
"""

from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime, timezone
import math
from verifier.models import (
    DroneState,
    WorldState,
    Plan,
    Mission,
    SimulationEvent,
    SimulationEventType,
    RestrictedZone,
    GeoPolygon,
)
from verifier.rules import haversine_distance_m


class MissionSimulator:
    def __init__(
        self,
        drone: DroneState,
        world: WorldState,
        mission: Mission,
        plan: Optional[Plan] = None,
    ):
        self.drone = drone
        self.world = world
        self.mission = mission
        self.plan = plan
        self.sim_time_s: float = 0.0
        self.sequence: int = 0
        self.events: List[SimulationEvent] = []
        self.repair_attempts: int = 0
        self.intervention_required: bool = False
        self.is_paused: bool = True
        self.speed_multiplier: float = 1.0

    def emit_event(
        self,
        event_type: SimulationEventType,
        payload: Dict[str, Any],
        source: str = "SIMULATOR",
    ) -> SimulationEvent:
        self.sequence += 1
        now_iso = datetime.now(timezone.utc).isoformat()
        event = SimulationEvent(
            event_id=f"EVT-{self.sequence:05d}",
            mission_id=self.mission.mission_id,
            event_type=event_type,
            payload=payload,
            sim_time_s=self.sim_time_s,
            sequence=self.sequence,
            source=source,
            created_at=now_iso,
        )
        self.events.append(event)
        return event

    def tick(self, delta_s: float = 1.0) -> DroneState:
        """Advance simulation by delta_s seconds."""
        if not self.plan or not self.drone.is_airborne or self.intervention_required:
            return self.drone

        effective_delta = delta_s * self.speed_multiplier
        self.sim_time_s += effective_delta
        self.drone.sim_time_s = self.sim_time_s

        waypoints = self.plan.waypoints
        curr_idx = self.drone.current_waypoint_index

        if curr_idx >= len(waypoints):
            self.drone.is_airborne = False
            self.drone.velocity_mps = 0.0
            self.emit_event(
                SimulationEventType.MISSION_COMPLETED,
                {"message": "All plan waypoints successfully traversed and surveyed."},
            )
            return self.drone

        target_wp = waypoints[curr_idx]
        target_pos = (target_wp.longitude, target_wp.latitude)
        curr_pos = self.drone.location

        dist_m = haversine_distance_m(curr_pos, target_pos)
        speed = target_wp.speed_mps
        step_dist = speed * effective_delta

        if dist_m <= step_dist or dist_m < 2.0:
            # Reached waypoint
            self.drone.location = target_pos
            self.drone.altitude_agl_m = target_wp.altitude_agl_m
            self.drone.current_waypoint_index += 1
            self.emit_event(
                SimulationEventType.WAYPOINT_REACHED,
                {
                    "waypoint_id": target_wp.waypoint_id,
                    "index": curr_idx,
                    "altitude_agl_m": target_wp.altitude_agl_m,
                    "action": target_wp.action,
                },
            )
        else:
            # Interpolate towards target
            ratio = step_dist / dist_m
            new_lon = curr_pos[0] + (target_pos[0] - curr_pos[0]) * ratio
            new_lat = curr_pos[1] + (target_pos[1] - curr_pos[1]) * ratio
            self.drone.location = (new_lon, new_lat)

            # Update heading
            d_lon = target_pos[0] - curr_pos[0]
            d_lat = target_pos[1] - curr_pos[1]
            angle_rad = math.atan2(d_lon, d_lat)
            self.drone.heading_deg = (math.degrees(angle_rad) + 360.0) % 360.0

            # Altitude interpolation
            alt_diff = target_wp.altitude_agl_m - self.drone.altitude_agl_m
            self.drone.altitude_agl_m += alt_diff * min(1.0, ratio * 2.0)
            self.drone.velocity_mps = speed

        # Battery consumption model: baseline cruise power (120W) + wind resistance
        power_w = 120.0 + (self.world.wind_speed_mps ** 1.5) * 4.0
        energy_used_wh = (power_w * effective_delta) / 3600.0
        self.drone.battery_wh = max(0.0, self.drone.battery_wh - energy_used_wh)
        self.drone.battery_pct = max(0.0, (self.drone.battery_wh / 100.0) * 100.0)

        # Emit telemetry tick every 5 simulated seconds
        if int(self.sim_time_s) % 5 == 0:
            self.emit_event(
                SimulationEventType.TELEMETRY_TICK,
                {
                    "position": self.drone.location,
                    "altitude_agl_m": round(self.drone.altitude_agl_m, 1),
                    "speed_mps": round(self.drone.velocity_mps, 1),
                    "heading_deg": round(self.drone.heading_deg, 1),
                    "battery_pct": round(self.drone.battery_pct, 1),
                    "battery_wh": round(self.drone.battery_wh, 1),
                    "current_waypoint_index": self.drone.current_waypoint_index,
                },
            )

        # Check for autonomous low battery warning
        if self.drone.battery_pct < 20.0 and self.drone.is_airborne:
            self.inject_low_battery()

        return self.drone

    # --- Trigger Injections (The 5 Approved Replan Families) ---

    def inject_survivor_detected(
        self,
        location: Optional[Tuple[float, float]] = None,
        confidence: float = 0.94,
    ) -> SimulationEvent:
        pos = location or (
            self.drone.location[0] + 0.001,
            self.drone.location[1] + 0.001,
        )
        return self.emit_event(
            SimulationEventType.SURVIVOR_DETECTED,
            {
                "detection_id": f"DET-{self.sequence:03d}",
                "location": pos,
                "confidence": confidence,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            source="AI_DETECTOR",
        )

    def inject_low_battery(self) -> SimulationEvent:
        return self.emit_event(
            SimulationEventType.LOW_BATTERY,
            {
                "current_battery_pct": round(self.drone.battery_pct, 1),
                "remaining_wh": round(self.drone.battery_wh, 1),
                "return_energy_required_wh": 18.5,
                "threshold_pct": 20.0,
            },
            source="SIMULATOR",
        )

    def inject_wind_spike(self, speed_mps: float = 14.8) -> SimulationEvent:
        self.world.wind_speed_mps = speed_mps
        return self.emit_event(
            SimulationEventType.WIND_SPIKE,
            {
                "observed_speed_mps": speed_mps,
                "gust_speed_mps": speed_mps + 3.2,
                "direction_deg": 270.0,
                "limit_mps": 12.0,
            },
            source="WEATHER_SENSOR",
        )

    def inject_new_restricted_zone(
        self,
        zone_id: str,
        name: str,
        boundary: GeoPolygon,
    ) -> SimulationEvent:
        new_zone = RestrictedZone(zone_id=zone_id, name=name, boundary=boundary, active=True)
        self.world.restricted_zones.append(new_zone)
        self.world.world_revision += 1
        return self.emit_event(
            SimulationEventType.NEW_RESTRICTED_ZONE,
            {
                "zone_id": zone_id,
                "name": name,
                "boundary": boundary.model_dump(),
                "effective_from": datetime.now(timezone.utc).isoformat(),
            },
            source="OPERATOR",
        )

    def record_repair_attempt(self) -> bool:
        """
        Records a replan/repair attempt.
        Enforces Decision 8: at most 3 repair attempts!
        Returns True if repair permitted, False if cap reached.
        """
        self.repair_attempts += 1
        if self.repair_attempts > 3:
            self.intervention_required = True
            self.emit_event(
                SimulationEventType.OPERATOR_MISSION_CHANGE,
                {
                    "status": "INTERVENTION_REQUIRED",
                    "reason": "Maximum 3 automatic repair attempts exceeded. Autonomous replan halted.",
                    "attempts": self.repair_attempts,
                },
                source="SIMULATOR",
            )
            return False
        return True
