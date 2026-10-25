from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.contracts import Mission, Point
from app.errors import ErrorCode, ServiceError
from app.llm.client import NebiusClient
from app.llm.prompts import load_prompt
from app.llm.router import ModelRouter


class ParsedSurveyIntent(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    objective: Literal["SURVEY"]
    approved_location_label: str = Field(min_length=1, max_length=200)
    requires_clarification: bool
    unsupported_actions: list[str] = Field(default_factory=list)


def validate_survey_request(
    operator_instruction: str,
    approved_area: list[Point],
    approved_location_label: str,
    operator_id: str,
) -> Mission:
    text = operator_instruction.lower()
    unsupported = (
        "rescue",
        "deliver",
        "weapon",
        "ignore safety",
        "disable safety",
        "bypass verifier",
        "pass certificate",
        "issue certificate",
    )
    if any(token in text for token in unsupported):
        raise ServiceError(
            ErrorCode.CLARIFICATION_REQUIRED,
            "only an approved survey instruction is supported",
        )
    if not re.search(r"\bsurvey(?:ing)?\b", text):
        raise ServiceError(
            ErrorCode.CLARIFICATION_REQUIRED,
            "instruction must explicitly request a survey mission",
        )
    if len(approved_area) < 3 or not approved_location_label.strip():
        raise ServiceError(
            ErrorCode.CLARIFICATION_REQUIRED,
            "approved area geometry and location label are required",
        )
    return Mission(
        approved_area=approved_area,
        approved_location_label=approved_location_label,
        operator_id=operator_id,
    )


class NebiusMissionParser:
    """Classifies intent while constructing authority fields only from trusted inputs."""

    def __init__(self, client: NebiusClient, router: ModelRouter) -> None:
        self.client = client
        self.router = router

    async def parse(
        self,
        operator_instruction: str,
        approved_area: list[Point],
        approved_location_label: str,
        operator_id: str,
    ) -> Mission:
        mission = validate_survey_request(
            operator_instruction,
            approved_area,
            approved_location_label,
            operator_id,
        )
        selection = self.router.select("parser")
        system_prompt, prompt_revision = load_prompt("parser")
        payload, trace = await self.client.json_completion(
            selection,
            "parser",
            [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "operator_instruction": operator_instruction,
                            "approved_location_label": approved_location_label,
                        }
                    ),
                },
            ],
            mission_id=mission.mission_id,
            prompt_revision=prompt_revision,
        )
        try:
            intent = ParsedSurveyIntent.model_validate(payload)
        except ValidationError as exc:
            self.client.mark_trace_failed(trace.trace_id, ErrorCode.MODEL_BAD_OUTPUT.value)
            raise ServiceError(
                ErrorCode.MODEL_BAD_OUTPUT, "model output does not match parser schema"
            ) from exc
        if intent.approved_location_label != approved_location_label:
            self.client.mark_trace_failed(trace.trace_id, ErrorCode.MODEL_BAD_OUTPUT.value)
            raise ServiceError(
                ErrorCode.MODEL_BAD_OUTPUT,
                "model attempted to change the approved location label",
            )
        if intent.requires_clarification or intent.unsupported_actions:
            raise ServiceError(
                ErrorCode.CLARIFICATION_REQUIRED,
                "instruction requires clarification or contains unsupported actions",
            )
        return mission
