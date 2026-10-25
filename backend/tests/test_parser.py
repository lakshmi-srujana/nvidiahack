import json
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.contracts import Point
from app.errors import ErrorCode, ServiceError
from app.llm.client import NebiusClient
from app.llm.router import ModelRouter
from app.mission.parser import NebiusMissionParser


class ParserCompletions:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    async def create(self, **_kwargs):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=json.dumps(self.payload)),
                    finish_reason="stop",
                )
            ],
            usage=None,
            _request_id="parser-request",
        )


def parser(payload: dict) -> tuple[NebiusMissionParser, NebiusClient]:
    settings = Settings(_env_file=None, nebius_model_fast="fast-model")
    client = NebiusClient(settings)
    client._client = SimpleNamespace(
        chat=SimpleNamespace(completions=ParserCompletions(payload))
    )
    return NebiusMissionParser(client, ModelRouter(settings)), client


def area() -> list[Point]:
    return [
        Point(longitude=77.58, latitude=12.96),
        Point(longitude=77.60, latitude=12.96),
        Point(longitude=77.60, latitude=12.98),
    ]


@pytest.mark.asyncio
async def test_model_parser_can_classify_but_not_create_authority_fields() -> None:
    model_parser, _ = parser(
        {
            "objective": "SURVEY",
            "approved_location_label": "approved sector",
            "requires_clarification": False,
            "unsupported_actions": [],
        }
    )
    mission = await model_parser.parse(
        "Survey the approved sector", area(), "approved sector", "operator"
    )
    assert mission.approved_area == area()
    assert mission.approved_location_label == "approved sector"


@pytest.mark.asyncio
async def test_model_parser_rejects_changed_approved_location() -> None:
    model_parser, client = parser(
        {
            "objective": "SURVEY",
            "approved_location_label": "different sector",
            "requires_clarification": False,
            "unsupported_actions": [],
        }
    )
    with pytest.raises(ServiceError) as caught:
        await model_parser.parse(
            "Survey the approved sector", area(), "approved sector", "operator"
        )
    assert caught.value.code is ErrorCode.MODEL_BAD_OUTPUT
    assert client.traces[-1].success is False
