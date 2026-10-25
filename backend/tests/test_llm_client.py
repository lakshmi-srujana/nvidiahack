from types import SimpleNamespace

import httpx
import pytest
from openai import APIStatusError

from app.config import Settings
from app.errors import ErrorCode, ServiceError
from app.llm.client import NebiusClient
from app.llm.router import ModelSelection


class FailingCompletions:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        self.calls = 0

    async def create(self, **_kwargs):
        self.calls += 1
        response = httpx.Response(
            self.status_code,
            request=httpx.Request("POST", "https://provider.test/v1/chat/completions"),
        )
        raise APIStatusError("provider failure", response=response, body=None)


class SuccessfulCompletions:
    def __init__(self) -> None:
        self.requests: list[dict] = []

    async def create(self, **kwargs):
        self.requests.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content='{"ok": true}'), finish_reason="stop"
                )
            ],
            usage=None,
            _request_id="request-1",
        )


def client_with_status(status_code: int, retries: int) -> tuple[NebiusClient, FailingCompletions]:
    client = NebiusClient(
        Settings(_env_file=None, nebius_max_provider_retries=retries)
    )
    completions = FailingCompletions(status_code)
    client._client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    return client, completions


@pytest.mark.asyncio
async def test_rate_limit_is_retried_and_classified() -> None:
    client, completions = client_with_status(429, retries=1)
    with pytest.raises(ServiceError) as caught:
        await client.json_completion(
            ModelSelection("planner", "model", "test"), "planner", []
        )
    assert caught.value.code is ErrorCode.PROVIDER_RATE_LIMIT
    assert caught.value.retryable is True
    assert completions.calls == 2
    assert client.traces[-1].error_code == "PROVIDER_RATE_LIMIT"


@pytest.mark.asyncio
async def test_provider_client_error_is_not_retried() -> None:
    client, completions = client_with_status(401, retries=2)
    with pytest.raises(ServiceError) as caught:
        await client.json_completion(
            ModelSelection("planner", "model", "test"), "planner", []
        )
    assert caught.value.code is ErrorCode.AI_UNAVAILABLE
    assert caught.value.retryable is False
    assert completions.calls == 1


@pytest.mark.asyncio
async def test_json_mode_is_only_sent_for_capability_verified_model() -> None:
    completions = SuccessfulCompletions()
    client = NebiusClient(Settings(_env_file=None))
    client._client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    selection = ModelSelection("planner", "model", "test")
    await client.json_completion(selection, "planner", [])
    assert "response_format" not in completions.requests[0]

    verified_completions = SuccessfulCompletions()
    verified = NebiusClient(
        Settings(_env_file=None, nebius_json_mode_models="model, other-model")
    )
    verified._client = SimpleNamespace(
        chat=SimpleNamespace(completions=verified_completions)
    )
    _, trace = await verified.json_completion(selection, "planner", [])
    assert verified_completions.requests[0]["response_format"] == {"type": "json_object"}
    assert trace.provider_request_id == "request-1"
    assert trace.input_tokens is None
    assert trace.estimated_cost_usd is None
    assert trace.cost_status == "unknown_usage"
    assert trace.routing_reason == "test"
    assert trace.prompt_revision == "unknown"


@pytest.mark.asyncio
async def test_unconfigured_client_records_failed_trace() -> None:
    client = NebiusClient(Settings(_env_file=None))
    with pytest.raises(ServiceError):
        await client.json_completion(
            ModelSelection("planner", "model", "test"), "planner", []
        )
    assert client.traces[-1].success is False
    assert client.traces[-1].error_code == "AI_UNAVAILABLE"
