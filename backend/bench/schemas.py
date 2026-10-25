from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class AttackClass(StrEnum):
    BENIGN_CONTROL = "BENIGN_CONTROL"
    ZONE_CROSSING = "ZONE_CROSSING"
    ENERGY_IMPOSSIBILITY = "ENERGY_IMPOSSIBILITY"
    COORDINATE_TRAP = "COORDINATE_TRAP"
    PHYSICS_LIMIT = "PHYSICS_LIMIT"
    CONTRADICTORY_OBJECTIVE = "CONTRADICTORY_OBJECTIVE"
    AMBIGUITY = "AMBIGUITY"
    DIRECT_INJECTION = "DIRECT_INJECTION"
    POISONED_CONTEXT = "POISONED_CONTEXT"
    CONFUSED_AUTHORITY = "CONFUSED_AUTHORITY"
    STALE_RACE = "STALE_RACE"
    MALFORMED_MODEL_OUTPUT = "MALFORMED_MODEL_OUTPUT"
    RESOURCE_PRESSURE = "RESOURCE_PRESSURE"


class AttackCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,80}$")
    suite_version: str = Field(min_length=1, max_length=64)
    seed: int = 42
    attack_class: AttackClass
    input_channel: str = Field(default="operator", min_length=1, max_length=64)
    operator_text: str = Field(default="Survey the approved polygon", min_length=1, max_length=4000)
    expected_behavior: str = Field(min_length=1, max_length=128)
    validity_tags: tuple[str, ...] = ()
    source: str = "hand-authored"


class AttemptRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    case_id: str
    mode: str
    initial_plan_hash: str | None = None
    candidate_plan_hashes: list[str] = Field(default_factory=list)
    initial_verdict: str | None = None
    verifier_statuses: list[str] = Field(default_factory=list)
    violated_rule_ids: list[list[str]] = Field(default_factory=list)
    repair_attempts: int = Field(default=0, ge=0)
    safe_plan_accepted: bool = False
    simulator_completed: bool | None = None
    latency_ms: int | None = Field(default=None, ge=0)
    llm_input_tokens: int | None = Field(default=None, ge=0)
    llm_output_tokens: int | None = Field(default=None, ge=0)
    estimated_model_cost_usd: float | None = Field(default=None, ge=0)
    tavily_calls: int | None = Field(default=None, ge=0)
    error_code: str | None = None
    finished_at_utc: str | None = None
