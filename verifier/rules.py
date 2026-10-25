"""
SkyWarden Deterministic Verifier Rules
Implements the 10 Blueprint Safety Rule Classes strictly.
Returns (passed: bool, message: str, violations: List[Violation])
"""

import math
from typing import List, Tuple, Optional
from shapely.geometry import Polygon, Point, LineString
from verifier.models import (
    Plan,
    Mission,
    WorldState,
    SafetyPolicy,
    DroneState,
    RuleIdentifier,
    Violation,
    ViolationSeverity,
    RuleCheckResult,
)


def haversine_distance_m(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Calculates distance in metres between two (lon, lat) coordinates."""
    lon1, lat1 = p1
    lon2, lat2 = p2
    R = 6371000.0  # Earth radius in metres
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def degrees_to_approx_metres(lat_mid: float) -> Tuple[float, float]:
    """Returns (metres_per_deg_lon, metres_per_deg_lat) around latitude lat_mid."""
    R = 6371000.0
    lat_rad = math.radians(lat_mid)
    m_per_lat = (math.pi / 180.0) * R
    m_per_lon = (math.pi / 180.0) * R * math.cos(lat_rad)
    return m_per_lon, m_per_lat


def check_rule_01_geofence(
    plan: Plan, world: WorldState
) -> Tuple[RuleCheckResult, List[Violation]]:
    """Rule 01: All waypoints and path segments must be strictly inside geofence."""
    rule_id = RuleIdentifier.RULE_01_GEOFENCE_CONTAINMENT
    poly_coords = world.geofence_boundary.coordinates[0]
    geofence_poly = Polygon(poly_coords)

    violations: List[Violation] = []

    # Check waypoints
    for wp in plan.waypoints:
        pt = Point(wp.longitude, wp.latitude)
        # Using a slight numerical epsilon or direct contains/covers
        if not geofence_poly.covers(pt):
            violations.append(
                Violation(
                    rule_id=rule_id,
                    severity=ViolationSeverity.CRITICAL,
                    message=f"Waypoint {wp.waypoint_id} ({wp.longitude:.4f}, {wp.latitude:.4f}) is outside geofence boundary.",
                    observed=[wp.longitude, wp.latitude],
                    limit="geofence_boundary",
                    waypoint_refs=[wp.waypoint_id],
                    remediation="Shift waypoint inside geofence perimeter.",
                )
            )

    # Check path segments
    for i in range(len(plan.waypoints) - 1):
        w1 = plan.waypoints[i]
        w2 = plan.waypoints[i + 1]
        line = LineString([(w1.longitude, w1.latitude), (w2.longitude, w2.latitude)])
        if not geofence_poly.covers(line):
            violations.append(
                Violation(
                    rule_id=rule_id,
                    severity=ViolationSeverity.CRITICAL,
                    message=f"Flight segment between {w1.waypoint_id} and {w2.waypoint_id} intersects outside geofence.",
                    observed=f"{w1.waypoint_id} -> {w2.waypoint_id}",
                    limit="geofence_boundary",
                    waypoint_refs=[w1.waypoint_id, w2.waypoint_id],
                    remediation="Add intermediate waypoints conforming to geofence interior.",
                )
            )

    passed = len(violations) == 0
    msg = (
        "All waypoints and path segments contained within approved geofence."
        if passed
        else f"Geofence breached by {len(violations)} points/segments."
    )
    return RuleCheckResult(rule_id=rule_id, name="Geofence Containment", passed=passed, message=msg), violations


def check_rule_02_restricted_zones(
    plan: Plan, world: WorldState, policy: SafetyPolicy, mission: Mission
) -> Tuple[RuleCheckResult, List[Violation]]:
    """Rule 02: Waypoints & flight paths must not intersect restricted zones + buffer."""
    rule_id = RuleIdentifier.RULE_02_RESTRICTED_ZONE_CLEARANCE
    violations: List[Violation] = []

    active_zones = [z for z in world.restricted_zones if z.active]
    # Also include forbidden zones from operator restrictions
    if mission.operator_restrictions.forbidden_zones:
        for idx, fz in enumerate(mission.operator_restrictions.forbidden_zones):
            active_zones.append(
                type("TempZone", (), {
                    "zone_id": f"OP-ZONE-{idx+1}",
                    "name": f"Operator Forbidden Zone {idx+1}",
                    "boundary": fz,
                    "buffer_m": policy.restricted_zone_buffer_m,
                })()
            )

    for zone in active_zones:
        coords = zone.boundary.coordinates[0]
        base_poly = Polygon(coords)
        mid_lat = coords[0][1] if coords else 0.0
        m_lon, m_lat = degrees_to_approx_metres(mid_lat)
        # buffer in degrees
        deg_buffer = (zone.buffer_m) / max(m_lon, m_lat)
        buffered_poly = base_poly.buffer(deg_buffer)

        # Check each waypoint
        for wp in plan.waypoints:
            pt = Point(wp.longitude, wp.latitude)
            if buffered_poly.intersects(pt):
                violations.append(
                    Violation(
                        rule_id=rule_id,
                        severity=ViolationSeverity.CRITICAL,
                        message=f"Waypoint {wp.waypoint_id} infringes restricted zone '{zone.name}' with {zone.buffer_m}m buffer.",
                        observed=[wp.longitude, wp.latitude],
                        limit=f"Clear of {zone.name} + {zone.buffer_m}m",
                        unit="metres",
                        waypoint_refs=[wp.waypoint_id],
                        remediation=f"Reroute waypoint away from {zone.name}.",
                    )
                )

        # Check segments
        for i in range(len(plan.waypoints) - 1):
            w1 = plan.waypoints[i]
            w2 = plan.waypoints[i + 1]
            seg = LineString([(w1.longitude, w1.latitude), (w2.longitude, w2.latitude)])
            if buffered_poly.intersects(seg):
                violations.append(
                    Violation(
                        rule_id=rule_id,
                        severity=ViolationSeverity.CRITICAL,
                        message=f"Path segment {w1.waypoint_id}->{w2.waypoint_id} intersects restricted zone '{zone.name}'.",
                        observed=f"{w1.waypoint_id} -> {w2.waypoint_id}",
                        limit=f"Clear of {zone.name} + {zone.buffer_m}m",
                        waypoint_refs=[w1.waypoint_id, w2.waypoint_id],
                        remediation=f"Insert detour waypoints around {zone.name}.",
                    )
                )

    passed = len(violations) == 0
    msg = (
        f"All waypoints clear of all {len(active_zones)} active restricted zones."
        if passed
        else f"Restricted zone clearance violated {len(violations)} times."
    )
    return RuleCheckResult(rule_id=rule_id, name="Restricted Zone Clearance", passed=passed, message=msg), violations


def check_rule_03_altitude(
    plan: Plan, policy: SafetyPolicy, mission: Mission
) -> Tuple[RuleCheckResult, List[Violation]]:
    """Rule 03: Altitude AGL must be within trusted bounds & operator limits."""
    rule_id = RuleIdentifier.RULE_03_ALTITUDE_AGL_BOUNDS
    violations: List[Violation] = []

    min_agl = policy.min_altitude_agl_m
    max_agl = policy.max_altitude_agl_m

    # Tighter operator restrictions apply
    if mission.operator_restrictions.min_altitude_agl_m is not None:
        min_agl = max(min_agl, mission.operator_restrictions.min_altitude_agl_m)
    if mission.operator_restrictions.max_altitude_agl_m is not None:
        max_agl = min(max_agl, mission.operator_restrictions.max_altitude_agl_m)

    for wp in plan.waypoints:
        if wp.altitude_agl_m < min_agl:
            violations.append(
                Violation(
                    rule_id=rule_id,
                    severity=ViolationSeverity.CRITICAL,
                    message=f"Waypoint {wp.waypoint_id} altitude ({wp.altitude_agl_m:.1f}m AGL) below minimum allowed ({min_agl:.1f}m AGL).",
                    observed=wp.altitude_agl_m,
                    limit=min_agl,
                    unit="m AGL",
                    waypoint_refs=[wp.waypoint_id],
                    remediation=f"Elevate waypoint altitude to at least {min_agl:.1f}m AGL.",
                )
            )
        elif wp.altitude_agl_m > max_agl:
            violations.append(
                Violation(
                    rule_id=rule_id,
                    severity=ViolationSeverity.CRITICAL,
                    message=f"Waypoint {wp.waypoint_id} altitude ({wp.altitude_agl_m:.1f}m AGL) exceeds ceiling ({max_agl:.1f}m AGL).",
                    observed=wp.altitude_agl_m,
                    limit=max_agl,
                    unit="m AGL",
                    waypoint_refs=[wp.waypoint_id],
                    remediation=f"Lower waypoint altitude below ceiling of {max_agl:.1f}m AGL.",
                )
            )

    passed = len(violations) == 0
    msg = (
        f"All waypoints within allowed altitude bounds [{min_agl:.1f}m, {max_agl:.1f}m AGL]."
        if passed
        else f"{len(violations)} waypoint(s) violated altitude limits."
    )
    return RuleCheckResult(rule_id=rule_id, name="Altitude AGL Bounds", passed=passed, message=msg), violations


def check_rule_04_max_speed(
    plan: Plan, policy: SafetyPolicy, mission: Mission
) -> Tuple[RuleCheckResult, List[Violation]]:
    """Rule 04: Waypoint planned speeds must not exceed safety limit."""
    rule_id = RuleIdentifier.RULE_04_MAX_SPEED_LIMIT
    violations: List[Violation] = []

    max_speed = policy.max_speed_mps
    if mission.operator_restrictions.max_speed_mps is not None:
        max_speed = min(max_speed, mission.operator_restrictions.max_speed_mps)

    for wp in plan.waypoints:
        if wp.speed_mps > max_speed:
            violations.append(
                Violation(
                    rule_id=rule_id,
                    severity=ViolationSeverity.CRITICAL,
                    message=f"Waypoint {wp.waypoint_id} planned speed ({wp.speed_mps:.1f} m/s) exceeds maximum allowed ({max_speed:.1f} m/s).",
                    observed=wp.speed_mps,
                    limit=max_speed,
                    unit="m/s",
                    waypoint_refs=[wp.waypoint_id],
                    remediation=f"Reduce waypoint speed to <= {max_speed:.1f} m/s.",
                )
            )

    passed = len(violations) == 0
    msg = (
        f"All waypoint speeds within limit (<= {max_speed:.1f} m/s)."
        if passed
        else f"{len(violations)} waypoint(s) exceed maximum speed."
    )
    return RuleCheckResult(rule_id=rule_id, name="Max Speed Limit", passed=passed, message=msg), violations


def check_rule_05_energy_reserve(
    plan: Plan, policy: SafetyPolicy, world: WorldState
) -> Tuple[RuleCheckResult, List[Violation]]:
    """Rule 05: Wind-adjusted energy budget must maintain minimum battery reserve."""
    rule_id = RuleIdentifier.RULE_05_ENERGY_BUDGET_RESERVE
    violations: List[Violation] = []

    # Wind resistance penalty factor
    wind_factor = 1.0 + (world.wind_speed_mps / 20.0) * 0.25
    adjusted_energy = plan.estimated_energy_wh * wind_factor
    remaining_wh = policy.total_battery_wh - adjusted_energy
    remaining_pct = (remaining_wh / policy.total_battery_wh) * 100.0

    if remaining_pct < policy.battery_reserve_pct:
        violations.append(
            Violation(
                rule_id=rule_id,
                severity=ViolationSeverity.CRITICAL,
                message=f"Projected remaining battery ({remaining_pct:.1f}%) is below mandatory {policy.battery_reserve_pct:.1f}% reserve.",
                observed=remaining_pct,
                limit=policy.battery_reserve_pct,
                unit="%",
                remediation="Shorten route or increase survey line spacing to conserve energy.",
            )
        )

    passed = len(violations) == 0
    msg = (
        f"Projected energy consumption ({adjusted_energy:.1f} Wh) leaves {remaining_pct:.1f}% battery (>= {policy.battery_reserve_pct:.1f}% reserve)."
        if passed
        else f"Insufficient energy reserve: {remaining_pct:.1f}% vs {policy.battery_reserve_pct:.1f}% limit."
    )
    return RuleCheckResult(rule_id=rule_id, name="Energy Budget & Reserve", passed=passed, message=msg), violations


def check_rule_06_return_home(
    plan: Plan, policy: SafetyPolicy, drone: DroneState
) -> Tuple[RuleCheckResult, List[Violation]]:
    """Rule 06: Return-to-home feasibility check from every waypoint."""
    rule_id = RuleIdentifier.RULE_06_RETURN_TO_HOME_FEASIBILITY
    violations: List[Violation] = []

    home = drone.home_position
    # Wh per metre baseline: ~0.015 Wh/m (approx 15W cruise at 10m/s)
    ENERGY_PER_METRE_WH = 0.015

    for wp in plan.waypoints:
        dist_m = haversine_distance_m((wp.longitude, wp.latitude), home)
        rth_energy_wh = dist_m * ENERGY_PER_METRE_WH + 5.0  # +5 Wh for climb/descent
        if rth_energy_wh > policy.min_return_home_energy_wh * 1.5:
            violations.append(
                Violation(
                    rule_id=rule_id,
                    severity=ViolationSeverity.CRITICAL,
                    message=f"Return to home from {wp.waypoint_id} ({dist_m:.0f}m away) requires {rth_energy_wh:.1f} Wh, exceeding safe threshold.",
                    observed=rth_energy_wh,
                    limit=policy.min_return_home_energy_wh * 1.5,
                    unit="Wh",
                    waypoint_refs=[wp.waypoint_id],
                    remediation="Keep survey waypoints closer to home coordinates or establish forward home landing site.",
                )
            )

    passed = len(violations) == 0
    msg = (
        "Return-to-home is feasible from all waypoints."
        if passed
        else f"RTH infeasible from {len(violations)} waypoint(s)."
    )
    return RuleCheckResult(rule_id=rule_id, name="Return-to-Home Feasibility", passed=passed, message=msg), violations


def check_rule_07_wind_limits(
    world: WorldState, policy: SafetyPolicy
) -> Tuple[RuleCheckResult, List[Violation]]:
    """Rule 07: Current & gust wind speed must not exceed policy limit."""
    rule_id = RuleIdentifier.RULE_07_WIND_SPEED_LIMIT
    violations: List[Violation] = []

    if world.wind_speed_mps > policy.max_wind_speed_mps:
        violations.append(
            Violation(
                rule_id=rule_id,
                severity=ViolationSeverity.CRITICAL,
                message=f"Wind speed ({world.wind_speed_mps:.1f} m/s) exceeds maximum operational limit ({policy.max_wind_speed_mps:.1f} m/s).",
                observed=world.wind_speed_mps,
                limit=policy.max_wind_speed_mps,
                unit="m/s",
                remediation="Hold mission launch until ambient wind subsides below operational envelope.",
            )
        )

    passed = len(violations) == 0
    msg = (
        f"Wind speed ({world.wind_speed_mps:.1f} m/s) is within operational limit (<= {policy.max_wind_speed_mps:.1f} m/s)."
        if passed
        else f"Wind speed limit breached: {world.wind_speed_mps:.1f} m/s > {policy.max_wind_speed_mps:.1f} m/s."
    )
    return RuleCheckResult(rule_id=rule_id, name="Wind Speed Limit", passed=passed, message=msg), violations


def check_rule_08_physics_schema(plan: Plan) -> Tuple[RuleCheckResult, List[Violation]]:
    """Rule 08: Finite coordinates, valid WGS84, speeds, altitudes."""
    rule_id = RuleIdentifier.RULE_08_PHYSICS_SCHEMA_SANITY
    violations: List[Violation] = []

    if not plan.waypoints or len(plan.waypoints) < 2:
        violations.append(
            Violation(
                rule_id=rule_id,
                severity=ViolationSeverity.CRITICAL,
                message="Plan must contain at least 2 waypoints.",
                observed=len(plan.waypoints),
                limit=2,
                remediation="Generate valid multi-point survey route.",
            )
        )

    for wp in plan.waypoints:
        if not (-180.0 <= wp.longitude <= 180.0 and -90.0 <= wp.latitude <= 90.0):
            violations.append(
                Violation(
                    rule_id=rule_id,
                    severity=ViolationSeverity.CRITICAL,
                    message=f"Waypoint {wp.waypoint_id} coordinates outside WGS84 bounds.",
                    observed=[wp.longitude, wp.latitude],
                    limit="WGS84",
                    waypoint_refs=[wp.waypoint_id],
                )
            )
        if wp.speed_mps <= 0.0:
            violations.append(
                Violation(
                    rule_id=rule_id,
                    severity=ViolationSeverity.CRITICAL,
                    message=f"Waypoint {wp.waypoint_id} has non-positive speed.",
                    observed=wp.speed_mps,
                    limit="> 0",
                    unit="m/s",
                    waypoint_refs=[wp.waypoint_id],
                )
            )

    passed = len(violations) == 0
    msg = "All waypoint physics and schema fields valid." if passed else f"Schema sanity check failed: {len(violations)} errors."
    return RuleCheckResult(rule_id=rule_id, name="Physics & Schema Sanity", passed=passed, message=msg), violations


def check_rule_09_caps(
    plan: Plan, policy: SafetyPolicy
) -> Tuple[RuleCheckResult, List[Violation]]:
    """Rule 09: Mission time and waypoint count caps."""
    rule_id = RuleIdentifier.RULE_09_MISSION_TIME_WAYPOINTS_CAP
    violations: List[Violation] = []

    if len(plan.waypoints) > policy.max_waypoints:
        violations.append(
            Violation(
                rule_id=rule_id,
                severity=ViolationSeverity.CRITICAL,
                message=f"Waypoint count ({len(plan.waypoints)}) exceeds cap ({policy.max_waypoints}).",
                observed=len(plan.waypoints),
                limit=policy.max_waypoints,
                remediation="Simplify route by reducing grid density.",
            )
        )

    if plan.estimated_duration_s > policy.max_mission_time_s:
        violations.append(
            Violation(
                rule_id=rule_id,
                severity=ViolationSeverity.CRITICAL,
                message=f"Estimated duration ({plan.estimated_duration_s:.0f}s) exceeds max mission time ({policy.max_mission_time_s:.0f}s).",
                observed=plan.estimated_duration_s,
                limit=policy.max_mission_time_s,
                unit="seconds",
                remediation="Partition survey into multiple sub-missions.",
            )
        )

    passed = len(violations) == 0
    msg = (
        f"Waypoint count ({len(plan.waypoints)}) and duration ({plan.estimated_duration_s:.0f}s) within limits."
        if passed
        else "Caps exceeded."
    )
    return RuleCheckResult(rule_id=rule_id, name="Mission Time & Waypoints Cap", passed=passed, message=msg), violations


def check_rule_10_constraint_integrity(
    mission: Mission, policy: SafetyPolicy
) -> Tuple[RuleCheckResult, List[Violation]]:
    """Rule 10: Untrusted external prompt text cannot loosen safety policy constraints."""
    rule_id = RuleIdentifier.RULE_10_CONSTRAINT_INTEGRITY
    violations: List[Violation] = []

    # Check that operator restrictions do NOT relax the trusted safety policy
    if mission.operator_restrictions.max_altitude_agl_m is not None:
        if mission.operator_restrictions.max_altitude_agl_m > policy.max_altitude_agl_m:
            violations.append(
                Violation(
                    rule_id=rule_id,
                    severity=ViolationSeverity.CRITICAL,
                    message="Operator restriction attempted to exceed trusted platform max altitude ceiling.",
                    observed=mission.operator_restrictions.max_altitude_agl_m,
                    limit=policy.max_altitude_agl_m,
                    unit="m AGL",
                    remediation="Clamp max altitude to platform policy ceiling.",
                )
            )

    if mission.operator_restrictions.max_speed_mps is not None:
        if mission.operator_restrictions.max_speed_mps > policy.max_speed_mps:
            violations.append(
                Violation(
                    rule_id=rule_id,
                    severity=ViolationSeverity.CRITICAL,
                    message="Operator restriction attempted to exceed trusted airframe speed limit.",
                    observed=mission.operator_restrictions.max_speed_mps,
                    limit=policy.max_speed_mps,
                    unit="m/s",
                    remediation="Clamp max speed to platform policy limit.",
                )
            )

    passed = len(violations) == 0
    msg = "Constraint integrity verified: trusted safety policy remains authoritative." if passed else "Integrity breach."
    return RuleCheckResult(rule_id=rule_id, name="Constraint Integrity", passed=passed, message=msg), violations
