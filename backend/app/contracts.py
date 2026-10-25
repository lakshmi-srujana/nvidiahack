"""Temporary adapter DTOs. Replace with the jointly approved shared contract package."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from math import isfinite
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def parse_datetime(value: object) -> object:
    """Accept JSON ISO timestamps while retaining strict runtime datetime values."""
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Point(StrictModel):
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)

    @field_validator("longitude", "latitude")
    @classmethod
    def finite(cls, value: float) -> float:
        if not isfinite(value):
            raise ValueError("coordinate must be finite")
        return value


class Mission(StrictModel):
    mission_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1)
    schema_version: str = "provisional-v1"
    objective: str = "SURVEY"
    approved_area: list[Point] = Field(min_length=3)
    approved_location_label: str = Field(min_length=1, max_length=200)
    operator_id: str = Field(min_length=1, max_length=128)
    revision: int = Field(default=1, ge=1)
    created_at: datetime = Field(default_factory=utcnow)

    _parse_created_at = field_validator("created_at", mode="before")(parse_datetime)

    @model_validator(mode="after")
    def only_survey(self) -> "Mission":
        if self.objective != "SURVEY":
            raise ValueError("only SURVEY missions are supported")
        return self


class Waypoint(StrictModel):
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    altitude_agl_m: float = Field(gt=0, le=10000)
    speed_mps: float = Field(gt=0, le=100)
    action: str | None = Field(default=None, max_length=64)
    dwell_s: float | None = Field(default=None, ge=0, le=3600)

    @field_validator("longitude", "latitude", "altitude_agl_m", "speed_mps")
    @classmethod
    def finite(cls, value: float) -> float:
        if not isfinite(value):
            raise ValueError("waypoint value must be finite")
        return value


class Plan(StrictModel):
    plan_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1)
    mission_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    snapshot_revision: str = Field(min_length=1)
    waypoints: list[Waypoint] = Field(min_length=2, max_length=500)
    parent_plan_id: str | None = None


class Violation(StrictModel):
    rule_id: str = Field(min_length=1)
    message: str = Field(min_length=1, max_length=1000)
    affected_waypoint_indices: list[int] = Field(default_factory=list)
    observed_value: Any | None = None
    applicable_limit: Any | None = None


class Certificate(StrictModel):
    certificate_ref: str = Field(min_length=1)
    plan_id: str = Field(min_length=1)
    snapshot_revision: str = Field(min_length=1)
    issuer: str = Field(min_length=1)


class VerificationResult(StrictModel):
    passed: bool
    violations: list[Violation] = Field(default_factory=list)
    certificate: Certificate | None = None

    @model_validator(mode="after")
    def only_pass_can_certify(self) -> "VerificationResult":
        if self.passed != (self.certificate is not None):
            raise ValueError("certificate is required exactly for a passing verifier response")
        return self


class DroneState(StrictModel):
    position: Point
    battery_percent: float = Field(ge=0, le=100)


class WorldState(StrictModel):
    revision: str = Field(min_length=1)
    captured_at: datetime = Field(default_factory=utcnow)
    restricted_zone_refs: list[str] = Field(default_factory=list)


class SafetyPolicy(StrictModel):
    revision: str = Field(min_length=1)
    reference: str = Field(min_length=1)


class TrustedSnapshot(StrictModel):
    drone_state: DroneState
    world_state: WorldState
    safety_policy: SafetyPolicy


class EventFamily(StrEnum):
    SURVIVOR_DETECTED = "SURVIVOR_DETECTED"
    LOW_BATTERY = "LOW_BATTERY"
    WIND_SPIKE = "WIND_SPIKE"
    OPERATOR_MISSION_CHANGE = "OPERATOR_MISSION_CHANGE"
    NEW_RESTRICTED_ZONE = "NEW_RESTRICTED_ZONE"


class SimulationEvent(StrictModel):
    event_id: str = Field(min_length=1)
    mission_id: str = Field(min_length=1)
    sequence: int = Field(ge=0)
    family: EventFamily
    state_revision: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    source: str = Field(min_length=1)
    occurred_at: datetime = Field(default_factory=utcnow)

    _parse_occurred_at = field_validator("occurred_at", mode="before")(parse_datetime)

    @field_validator("family", mode="before")
    @classmethod
    def parse_family(cls, value: object) -> object:
        return EventFamily(value) if isinstance(value, str) else value
