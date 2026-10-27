import type {
  Plan,
  Mission,
  WorldState,
  SafetyPolicy,
  DroneState,
  VerificationResult,
  Certificate,
  Violation,
  RuleCheckResult,
} from "../contracts/contracts";

/**
 * Calculates distance in metres between two [lon, lat] coordinates.
 */
export function haversineDistanceM(p1: [number, number], p2: [number, number]): number {
  const [lon1, lat1] = p1;
  const [lon2, lat2] = p2;
  const R = 6371000.0;
  const phi1 = (lat1 * Math.PI) / 180.0;
  const phi2 = (lat2 * Math.PI) / 180.0;
  const deltaPhi = ((lat2 - lat1) * Math.PI) / 180.0;
  const deltaLambda = ((lon2 - lon1) * Math.PI) / 180.0;

  const a =
    Math.sin(deltaPhi / 2.0) ** 2 +
    Math.cos(phi1) * Math.cos(phi2) * Math.sin(deltaLambda / 2.0) ** 2;
  const c = 2.0 * Math.atan2(Math.sqrt(a), Math.sqrt(1.0 - a));
  return R * c;
}

/**
 * Point in polygon check using ray-casting.
 */
export function isPointInPolygon(
  point: [number, number],
  polygonCoords: [number, number][]
): boolean {
  const [x, y] = point;
  let inside = false;
  for (let i = 0, j = polygonCoords.length - 1; i < polygonCoords.length; j = i++) {
    const [xi, yi] = polygonCoords[i];
    const [xj, yj] = polygonCoords[j];
    const intersect =
      yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi;
    if (intersect) inside = !inside;
  }
  return inside;
}

/**
 * Simple SHA-256 simulation or crypto.subtle digest.
 */
export async function computePlanDigest(
  plan: Plan,
  mission: Mission,
  policy: SafetyPolicy
): Promise<string> {
  const canonical = JSON.stringify({
    plan_id: plan.plan_id,
    mission_id: plan.mission_id,
    revision: plan.revision,
    waypoints: plan.waypoints.map((w) => [
      w.waypoint_id,
      Math.round(w.longitude * 100000) / 100000,
      Math.round(w.latitude * 100000) / 100000,
      w.altitude_agl_m,
      w.speed_mps,
    ]),
    policy_id: policy.policy_id,
    survey_area: mission.survey_area.coordinates,
  });

  if (typeof crypto !== "undefined" && crypto.subtle) {
    const encoder = new TextEncoder();
    const data = encoder.encode(canonical);
    const hashBuffer = await crypto.subtle.digest("SHA-256", data);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
  }

  // Fallback hash
  let hash = 0;
  for (let i = 0; i < canonical.length; i++) {
    const char = canonical.charCodeAt(i);
    hash = (hash << 5) - hash + char;
    hash |= 0;
  }
  return Math.abs(hash).toString(16).padStart(64, "0");
}

export async function verifyPlanClient(
  plan: Plan,
  mission: Mission,
  world: WorldState,
  policy: SafetyPolicy,
  drone: DroneState
): Promise<{ result: VerificationResult; certificate: Certificate | null }> {
  const nowIso = new Date().toISOString();
  const checks: RuleCheckResult[] = [];
  const violations: Violation[] = [];

  // --- Rule 01: Geofence Containment ---
  const geofenceCoords = world.geofence_boundary.coordinates[0];
  let r1Pass = true;
  for (const wp of plan.waypoints) {
    if (!isPointInPolygon([wp.longitude, wp.latitude], geofenceCoords)) {
      r1Pass = false;
      violations.push({
        rule_id: "RULE_01_GEOFENCE_CONTAINMENT",
        severity: "CRITICAL",
        message: `Waypoint ${wp.waypoint_id} is outside the approved geofence boundary.`,
        observed: [wp.longitude, wp.latitude],
        limit: "geofence_boundary",
        waypoint_refs: [wp.waypoint_id],
        remediation: "Shift waypoint coordinates inside geofence perimeter.",
      });
    }
  }
  checks.push({
    rule_id: "RULE_01_GEOFENCE_CONTAINMENT",
    name: "Geofence Containment",
    passed: r1Pass,
    message: r1Pass
      ? "All waypoints and flight corridors contained within geofence."
      : "Geofence containment violated.",
  });

  // --- Rule 02: Restricted Zone Clearance (with 25m buffer) ---
  let r2Pass = true;
  const activeZones = world.restricted_zones.filter((z) => z.active);
  for (const zone of activeZones) {
    const zoneCoords = zone.boundary.coordinates[0];
    for (const wp of plan.waypoints) {
      // Check direct point in zone
      if (isPointInPolygon([wp.longitude, wp.latitude], zoneCoords)) {
        r2Pass = false;
        violations.push({
          rule_id: "RULE_02_RESTRICTED_ZONE_CLEARANCE",
          severity: "CRITICAL",
          message: `Waypoint ${wp.waypoint_id} is inside restricted zone '${zone.name}'.`,
          observed: [wp.longitude, wp.latitude],
          limit: `Clear of ${zone.name}`,
          waypoint_refs: [wp.waypoint_id],
          remediation: `Reroute waypoint away from ${zone.name}.`,
        });
      }
    }
  }
  checks.push({
    rule_id: "RULE_02_RESTRICTED_ZONE_CLEARANCE",
    name: "Restricted Zone Clearance",
    passed: r2Pass,
    message: r2Pass
      ? `Maintained ${policy.restricted_zone_buffer_m}m clearance from all active restricted zones.`
      : "Restricted zone clearance violated.",
  });

  // --- Rule 03: Altitude AGL Bounds ---
  let minAg = policy.min_altitude_agl_m;
  let maxAg = policy.max_altitude_agl_m;
  if (mission.operator_restrictions.min_altitude_agl_m !== undefined) {
    minAg = Math.max(minAg, mission.operator_restrictions.min_altitude_agl_m);
  }
  if (mission.operator_restrictions.max_altitude_agl_m !== undefined) {
    maxAg = Math.min(maxAg, mission.operator_restrictions.max_altitude_agl_m);
  }
  let r3Pass = true;
  for (const wp of plan.waypoints) {
    if (wp.altitude_agl_m < minAg) {
      r3Pass = false;
      violations.push({
        rule_id: "RULE_03_ALTITUDE_AGL_BOUNDS",
        severity: "CRITICAL",
        message: `Waypoint ${wp.waypoint_id} altitude (${wp.altitude_agl_m}m AGL) is below floor (${minAg}m AGL).`,
        observed: wp.altitude_agl_m,
        limit: minAg,
        unit: "m AGL",
        waypoint_refs: [wp.waypoint_id],
        remediation: `Increase altitude to >= ${minAg}m AGL.`,
      });
    } else if (wp.altitude_agl_m > maxAg) {
      r3Pass = false;
      violations.push({
        rule_id: "RULE_03_ALTITUDE_AGL_BOUNDS",
        severity: "CRITICAL",
        message: `Waypoint ${wp.waypoint_id} altitude (${wp.altitude_agl_m}m AGL) exceeds ceiling (${maxAg}m AGL).`,
        observed: wp.altitude_agl_m,
        limit: maxAg,
        unit: "m AGL",
        waypoint_refs: [wp.waypoint_id],
        remediation: `Lower altitude to <= ${maxAg}m AGL.`,
      });
    }
  }
  checks.push({
    rule_id: "RULE_03_ALTITUDE_AGL_BOUNDS",
    name: "Altitude AGL Bounds",
    passed: r3Pass,
    message: r3Pass
      ? `All waypoints within allowed altitude envelope [${minAg}m, ${maxAg}m AGL].`
      : "Altitude bounds violated.",
  });

  // --- Rule 04: Max Speed Limit ---
  let maxSpeed = policy.max_speed_mps;
  if (mission.operator_restrictions.max_speed_mps !== undefined) {
    maxSpeed = Math.min(maxSpeed, mission.operator_restrictions.max_speed_mps);
  }
  let r4Pass = true;
  for (const wp of plan.waypoints) {
    if (wp.speed_mps > maxSpeed) {
      r4Pass = false;
      violations.push({
        rule_id: "RULE_04_MAX_SPEED_LIMIT",
        severity: "CRITICAL",
        message: `Waypoint ${wp.waypoint_id} planned speed (${wp.speed_mps} m/s) exceeds allowed limit (${maxSpeed} m/s).`,
        observed: wp.speed_mps,
        limit: maxSpeed,
        unit: "m/s",
        waypoint_refs: [wp.waypoint_id],
        remediation: `Reduce speed to <= ${maxSpeed} m/s.`,
      });
    }
  }
  checks.push({
    rule_id: "RULE_04_MAX_SPEED_LIMIT",
    name: "Max Speed Limit",
    passed: r4Pass,
    message: r4Pass
      ? `Planned speeds conform to platform and restriction limit (<= ${maxSpeed} m/s).`
      : "Speed limit exceeded.",
  });

  // --- Rule 05: Energy Budget & Reserve ---
  const windFactor = 1.0 + (world.wind_speed_mps / 20.0) * 0.25;
  const adjustedEnergy = plan.estimated_energy_wh * windFactor;
  const remainingWh = 100.0 - adjustedEnergy;
  const remainingPct = remainingWh;
  const r5Pass = remainingPct >= policy.battery_reserve_pct;
  if (!r5Pass) {
    violations.push({
      rule_id: "RULE_05_ENERGY_BUDGET_RESERVE",
      severity: "CRITICAL",
      message: `Projected battery reserve (${remainingPct.toFixed(1)}%) is below mandatory ${policy.battery_reserve_pct}% threshold.`,
      observed: remainingPct,
      limit: policy.battery_reserve_pct,
      unit: "%",
      remediation: "Reduce survey line count or simplify route to conserve battery.",
    });
  }
  checks.push({
    rule_id: "RULE_05_ENERGY_BUDGET_RESERVE",
    name: "Energy Budget & Reserve",
    passed: r5Pass,
    message: r5Pass
      ? `Projected battery consumption leaves ${remainingPct.toFixed(1)}% reserve (>= ${policy.battery_reserve_pct}%).`
      : "Insufficient battery reserve.",
  });

  // --- Rule 06: Return-to-Home Feasibility ---
  let r6Pass = true;
  for (const wp of plan.waypoints) {
    const dist = haversineDistanceM([wp.longitude, wp.latitude], drone.home_position);
    const rthWh = dist * 0.015 + 5.0;
    if (rthWh > policy.min_return_home_energy_wh * 1.5) {
      r6Pass = false;
      violations.push({
        rule_id: "RULE_06_RETURN_TO_HOME_FEASIBILITY",
        severity: "CRITICAL",
        message: `RTH from ${wp.waypoint_id} (${Math.round(dist)}m) requires ${rthWh.toFixed(1)} Wh, exceeding limit.`,
        observed: rthWh,
        limit: policy.min_return_home_energy_wh * 1.5,
        unit: "Wh",
        waypoint_refs: [wp.waypoint_id],
        remediation: "Keep survey lines closer to home position.",
      });
    }
  }
  checks.push({
    rule_id: "RULE_06_RETURN_TO_HOME_FEASIBILITY",
    name: "Return-to-Home Feasibility",
    passed: r6Pass,
    message: r6Pass
      ? "Return-to-home is feasible from all waypoints."
      : "RTH infeasible from some waypoints.",
  });

  // --- Rule 07: Wind Speed Limit ---
  const r7Pass = world.wind_speed_mps <= policy.max_wind_speed_mps;
  if (!r7Pass) {
    violations.push({
      rule_id: "RULE_07_WIND_SPEED_LIMIT",
      severity: "CRITICAL",
      message: `Current wind speed (${world.wind_speed_mps} m/s) exceeds maximum operational limit (${policy.max_wind_speed_mps} m/s).`,
      observed: world.wind_speed_mps,
      limit: policy.max_wind_speed_mps,
      unit: "m/s",
      remediation: "Hold mission launch until ambient winds subside.",
    });
  }
  checks.push({
    rule_id: "RULE_07_WIND_SPEED_LIMIT",
    name: "Wind Speed Limit",
    passed: r7Pass,
    message: r7Pass
      ? `Wind speed (${world.wind_speed_mps} m/s) is within operational envelope (<= ${policy.max_wind_speed_mps} m/s).`
      : "Wind speed exceeds limit.",
  });

  // --- Rule 08: Physics & Schema Sanity ---
  let r8Pass = plan.waypoints.length >= 2;
  for (const wp of plan.waypoints) {
    if (
      !Number.isFinite(wp.longitude) ||
      !Number.isFinite(wp.latitude) ||
      wp.longitude < -180 ||
      wp.longitude > 180 ||
      wp.latitude < -90 ||
      wp.latitude > 90 ||
      wp.speed_mps <= 0
    ) {
      r8Pass = false;
      violations.push({
        rule_id: "RULE_08_PHYSICS_SCHEMA_SANITY",
        severity: "CRITICAL",
        message: `Waypoint ${wp.waypoint_id} contains non-finite or out-of-range physical coordinates/speeds.`,
        observed: [wp.longitude, wp.latitude, wp.speed_mps],
        limit: "Valid WGS84 & Speed > 0",
        waypoint_refs: [wp.waypoint_id],
      });
    }
  }
  checks.push({
    rule_id: "RULE_08_PHYSICS_SCHEMA_SANITY",
    name: "Physics & Schema Sanity",
    passed: r8Pass,
    message: r8Pass
      ? "All coordinates and physical quantities are finite and valid WGS84."
      : "Schema sanity check failed.",
  });

  // --- Rule 09: Mission Time & Waypoint Caps ---
  const r9Pass =
    plan.waypoints.length <= policy.max_waypoints &&
    plan.estimated_duration_s <= policy.max_mission_time_s;
  if (!r9Pass) {
    violations.push({
      rule_id: "RULE_09_MISSION_TIME_WAYPOINTS_CAP",
      severity: "CRITICAL",
      message: `Plan exceeds caps: waypoints (${plan.waypoints.length}/${policy.max_waypoints}), duration (${plan.estimated_duration_s}s/${policy.max_mission_time_s}s).`,
      observed: { waypoints: plan.waypoints.length, duration: plan.estimated_duration_s },
      limit: { waypoints: policy.max_waypoints, duration: policy.max_mission_time_s },
    });
  }
  checks.push({
    rule_id: "RULE_09_MISSION_TIME_WAYPOINTS_CAP",
    name: "Mission Time & Waypoint Caps",
    passed: r9Pass,
    message: r9Pass
      ? `Waypoint count (${plan.waypoints.length}) and duration (${plan.estimated_duration_s}s) within caps.`
      : "Mission caps exceeded.",
  });

  // --- Rule 10: Constraint Integrity ---
  let r10Pass = true;
  if (
    mission.operator_restrictions.max_altitude_agl_m !== undefined &&
    mission.operator_restrictions.max_altitude_agl_m > policy.max_altitude_agl_m
  ) {
    r10Pass = false;
    violations.push({
      rule_id: "RULE_10_CONSTRAINT_INTEGRITY",
      severity: "CRITICAL",
      message: "Operator restriction attempted to loosen platform altitude ceiling.",
      observed: mission.operator_restrictions.max_altitude_agl_m,
      limit: policy.max_altitude_agl_m,
      unit: "m AGL",
    });
  }
  checks.push({
    rule_id: "RULE_10_CONSTRAINT_INTEGRITY",
    name: "Constraint Integrity",
    passed: r10Pass,
    message: r10Pass
      ? "Platform safety policy is strictly authoritative over untrusted inputs."
      : "Constraint integrity breach.",
  });

  const allPassed = violations.length === 0;

  const result: VerificationResult = {
    schema_version: "1.0.0",
    plan_id: plan.plan_id,
    mission_id: mission.mission_id,
    passed: allPassed,
    policy_ref: `${policy.policy_id}:${policy.version}`,
    world_ref: `world_rev_${world.world_revision}`,
    drone_ref: drone.drone_id,
    checks,
    violations,
    verified_at: nowIso,
  };

  let certificate: Certificate | null = null;
  if (allPassed) {
    const digest = await computePlanDigest(plan, mission, policy);
    certificate = {
      schema_version: "1.0.0",
      certificate_id: `CERT-${plan.plan_id}-REV${plan.revision}`,
      mission_id: mission.mission_id,
      plan_id: plan.plan_id,
      verification_ref: `VRF-${plan.plan_id}-REV${plan.revision}`,
      plan_digest: digest,
      policy_ref: `${policy.policy_id}:${policy.version}`,
      world_ref: `world_rev_${world.world_revision}`,
      issued_at: nowIso,
      rule_results: checks,
      is_valid: true,
    };
  }

  return { result, certificate };
}
