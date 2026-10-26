"""
SkyWarden Scenarios Unit Test Suite
Validates the 4 core disaster scenarios required by Developer B in CONTRACTS.md:
1. Flash Flood Search (Nominal)
2. Dam Spillway Breach & Surge Inundation
3. High Wind Violation
4. Critical Low Battery Emergency RTH
"""

import pytest
from verifier.engine import SafetyVerifier
from verifier.models import RuleIdentifier
from simulator.scenarios import (
    create_flood_scenario,
    create_dam_breach_scenario,
    create_high_wind_scenario,
    create_battery_critical_scenario,
)


def test_flood_scenario_certifies_nominally():
    scen = create_flood_scenario()
    verifier = SafetyVerifier(policy=scen["policy"])
    res, cert = verifier.verify(scen["plan"], scen["mission"], scen["world"], scen["drone"])

    assert res.passed is True
    assert cert is not None
    assert cert.is_valid is True
    assert len(res.violations) == 0


def test_dam_breach_scenario_detects_surge_hazard():
    scen = create_dam_breach_scenario()
    verifier = SafetyVerifier(policy=scen["policy"])
    res, cert = verifier.verify(scen["plan"], scen["mission"], scen["world"], scen["drone"])

    assert res.passed is False
    assert cert is None
    rule2_viols = [v for v in res.violations if v.rule_id == RuleIdentifier.RULE_02_RESTRICTED_ZONE_CLEARANCE]
    assert len(rule2_viols) > 0
    assert any("Dam Spillway" in str(v.message) or "Surge" in str(v.message) for v in rule2_viols)


def test_high_wind_scenario_blocks_flight():
    scen = create_high_wind_scenario()
    verifier = SafetyVerifier(policy=scen["policy"])
    res, cert = verifier.verify(scen["plan"], scen["mission"], scen["world"], scen["drone"])

    assert res.passed is False
    assert cert is None
    wind_viols = [v for v in res.violations if v.rule_id == RuleIdentifier.RULE_07_WIND_SPEED_LIMIT]
    assert len(wind_viols) == 1
    assert wind_viols[0].observed == 15.5


def test_battery_critical_scenario_rejects_long_survey():
    scen = create_battery_critical_scenario()
    verifier = SafetyVerifier(policy=scen["policy"])
    res, cert = verifier.verify(scen["plan"], scen["mission"], scen["world"], scen["drone"])

    assert res.passed is False
    assert cert is None
    battery_viols = [v for v in res.violations if v.rule_id == RuleIdentifier.RULE_05_ENERGY_BUDGET_RESERVE]
    assert len(battery_viols) > 0
