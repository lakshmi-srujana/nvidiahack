from types import SimpleNamespace

import pytest

from app.config import Settings
from app.contracts import DroneState, Mission, Point, SafetyPolicy, TrustedSnapshot, WorldState
from app.errors import ErrorCode, ServiceError
from app.llm.client import NebiusClient
from app.llm.router import ModelRouter
from app.mission.nebius_engine import NebiusProposalEngine


class MalformedCompletions:
    async def create(self, **_kwargs):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content='{"mission_id":"wrong"}'),
                    finish_reason="stop",
                )
            ],
            usage=None,
            _request_id="malformed-request",
        )


@pytest.mark.asyncio
async def test_schema_invalid_model_json_is_typed_and_trace_is_failed() -> None:
    settings = Settings(_env_file=None, nebius_model_planner="planner-model")
    client = NebiusClient(settings)
    client._client = SimpleNamespace(
        chat=SimpleNamespace(completions=MalformedCompletions())
    )
    engine = NebiusProposalEngine(client, ModelRouter(settings))
    mission = Mission(
        approved_area=[
            Point(longitude=77.58, latitude=12.96),
            Point(longitude=77.60, latitude=12.96),
            Point(longitude=77.60, latitude=12.98),
        ],
        approved_location_label="sector",
        operator_id="operator",
    )
    snapshot = TrustedSnapshot(
        drone_state=DroneState(
            position=Point(longitude=77.59, latitude=12.97), battery_percent=80
        ),
        world_state=WorldState(revision="world-1"),
        safety_policy=SafetyPolicy(revision="policy-1", reference="policy"),
    )

    with pytest.raises(ServiceError) as caught:
        await engine.propose(mission, snapshot, stage="planner")

    assert caught.value.code is ErrorCode.MODEL_BAD_OUTPUT
    assert client.traces[-1].success is False
    assert client.traces[-1].error_code == "MODEL_BAD_OUTPUT"
