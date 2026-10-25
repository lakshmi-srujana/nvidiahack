"""
SkyWarden Deterministic Verification & Certification Engine
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Tuple, Optional, List
from verifier.models import (
    Plan,
    Mission,
    WorldState,
    SafetyPolicy,
    DroneState,
    VerificationResult,
    Certificate,
    RuleCheckResult,
    Violation,
)
from verifier.rules import (
    check_rule_01_geofence,
    check_rule_02_restricted_zones,
    check_rule_03_altitude,
    check_rule_04_max_speed,
    check_rule_05_energy_reserve,
    check_rule_06_return_home,
    check_rule_07_wind_limits,
    check_rule_08_physics_schema,
    check_rule_09_caps,
    check_rule_10_constraint_integrity,
)


def compute_plan_digest(plan: Plan, mission: Mission, policy: SafetyPolicy) -> str:
    """Computes deterministic SHA-256 digest over plan geometry, speeds, and bounds."""
    canonical_dict = {
        "plan_id": plan.plan_id,
        "mission_id": plan.mission_id,
        "revision": plan.revision,
        "waypoints": [
            [wp.waypoint_id, round(wp.longitude, 6), round(wp.latitude, 6), round(wp.altitude_agl_m, 2), round(wp.speed_mps, 2)]
            for wp in plan.waypoints
        ],
        "policy_id": policy.policy_id,
        "survey_area": mission.survey_area.coordinates,
    }
    raw = json.dumps(canonical_dict, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class SafetyVerifier:
    def __init__(self, policy: Optional[SafetyPolicy] = None):
        self.policy = policy or SafetyPolicy()

    def verify(
        self,
        plan: Plan,
        mission: Mission,
        world: WorldState,
        drone: DroneState,
    ) -> Tuple[VerificationResult, Optional[Certificate]]:
        now_iso = datetime.now(timezone.utc).isoformat()

        all_checks: List[RuleCheckResult] = []
        all_violations: List[Violation] = []

        # Run all 10 deterministic checks in sequence
        r1_res, r1_viols = check_rule_01_geofence(plan, world)
        all_checks.append(r1_res)
        all_violations.extend(r1_viols)

        r2_res, r2_viols = check_rule_02_restricted_zones(plan, world, self.policy, mission)
        all_checks.append(r2_res)
        all_violations.extend(r2_viols)

        r3_res, r3_viols = check_rule_03_altitude(plan, self.policy, mission)
        all_checks.append(r3_res)
        all_violations.extend(r3_viols)

        r4_res, r4_viols = check_rule_04_max_speed(plan, self.policy, mission)
        all_checks.append(r4_res)
        all_violations.extend(r4_viols)

        r5_res, r5_viols = check_rule_05_energy_reserve(plan, self.policy, world)
        all_checks.append(r5_res)
        all_violations.extend(r5_viols)

        r6_res, r6_viols = check_rule_06_return_home(plan, self.policy, drone)
        all_checks.append(r6_res)
        all_violations.extend(r6_viols)

        r7_res, r7_viols = check_rule_07_wind_limits(world, self.policy)
        all_checks.append(r7_res)
        all_violations.extend(r7_viols)

        r8_res, r8_viols = check_rule_08_physics_schema(plan)
        all_checks.append(r8_res)
        all_violations.extend(r8_viols)

        r9_res, r9_viols = check_rule_09_caps(plan, self.policy)
        all_checks.append(r9_res)
        all_violations.extend(r9_viols)

        r10_res, r10_viols = check_rule_10_constraint_integrity(mission, self.policy)
        all_checks.append(r10_res)
        all_violations.extend(r10_viols)

        all_passed = len(all_violations) == 0

        verification_result = VerificationResult(
            plan_id=plan.plan_id,
            mission_id=mission.mission_id,
            passed=all_passed,
            policy_ref=f"{self.policy.policy_id}:{self.policy.version}",
            world_ref=f"world_rev_{world.world_revision}",
            drone_ref=drone.drone_id,
            checks=all_checks,
            violations=all_violations,
            verified_at=now_iso,
        )

        certificate: Optional[Certificate] = None
        if all_passed:
            digest = compute_plan_digest(plan, mission, self.policy)
            certificate = Certificate(
                certificate_id=f"CERT-{plan.plan_id}-{plan.revision}",
                mission_id=mission.mission_id,
                plan_id=plan.plan_id,
                verification_ref=f"VRF-{plan.plan_id}-{plan.revision}",
                plan_digest=digest,
                policy_ref=f"{self.policy.policy_id}:{self.policy.version}",
                world_ref=f"world_rev_{world.world_revision}",
                issued_at=now_iso,
                rule_results=all_checks,
                is_valid=True,
            )

        return verification_result, certificate
