from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI

from app.config import Settings
from app.errors import ErrorCode, ServiceError
from app.llm.router import ModelSelection
from app.llm.usage import PriceCatalog

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InferenceTrace:
    trace_id: str
    mission_id: str | None
    stage: str
    requested_tier: str
    actual_tier: str
    actual_model_id: str
    routing_reason: str
    prompt_revision: str
    started_at_utc: str
    latency_ms: int
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    success: bool
    error_code: str | None = None
    provider_request_id: str | None = None
    estimated_cost_usd: float | None = None
    cost_status: str = "unknown"
    response_truncated: bool = False


class NebiusClient:
    """One long-lived OpenAI-compatible Nebius transport with bounded retries."""
    is_mock = False

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: AsyncOpenAI | None = None
        self._semaphore = asyncio.Semaphore(settings.nebius_max_concurrent_calls)
        self._prices = PriceCatalog(settings.model_price_file)
        self.traces: list[InferenceTrace] = []

    async def start(self) -> None:
        if not self.settings.nebius_api_key:
            return
        self._client = AsyncOpenAI(
            api_key=self.settings.nebius_api_key.get_secret_value(),
            base_url=self.settings.nebius_base_url,
            timeout=self.settings.nebius_timeout_s,
            max_retries=0,
        )

    async def close(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None

    async def catalog(self) -> list[str]:
        if not self._client:
            return []
        try:
            models = await self._client.models.list()
            return [item.id for item in models.data]
        except (APIConnectionError, APIStatusError, APITimeoutError) as exc:
            raise ServiceError(
                ErrorCode.AI_UNAVAILABLE,
                "Nebius model catalog is unavailable",
                retryable=isinstance(exc, (APIConnectionError, APITimeoutError))
                or getattr(exc, "status_code", 0) >= 500,
            ) from exc

    async def json_completion(
        self,
        selection: ModelSelection,
        stage: str,
        messages: list[dict[str, str]],
        *,
        json_mode: bool | None = None,
        mission_id: str | None = None,
        prompt_revision: str = "unknown",
    ) -> tuple[dict[str, Any], InferenceTrace]:
        started = time.perf_counter()
        started_at = datetime.now(timezone.utc).isoformat()
        trace_id = str(uuid4())
        if not self._client:
            error = ServiceError(ErrorCode.AI_UNAVAILABLE, "Nebius client is not configured")
            self._record_trace(
                InferenceTrace(
                    trace_id=trace_id,
                    mission_id=mission_id,
                    stage=stage,
                    requested_tier=selection.tier,
                    actual_tier=selection.tier,
                    actual_model_id=selection.model_id,
                    routing_reason=selection.reason,
                    prompt_revision=prompt_revision,
                    started_at_utc=started_at,
                    latency_ms=0,
                    input_tokens=None,
                    output_tokens=None,
                    total_tokens=None,
                    success=False,
                    error_code=error.code.value,
                )
            )
            raise error
        error: ServiceError | None = None
        async with self._semaphore:
            for attempt in range(self.settings.nebius_max_provider_retries + 1):
                try:
                    use_json_mode = (
                        selection.model_id in self.settings.nebius_json_mode_models
                        if json_mode is None
                        else json_mode
                    )
                    request: dict[str, Any] = {
                        "model": selection.model_id,
                        "messages": messages,
                        "temperature": 0,
                    }
                    if use_json_mode:
                        request["response_format"] = {"type": "json_object"}
                    response = await self._client.chat.completions.create(**request)
                    content = response.choices[0].message.content
                    if not content:
                        raise ServiceError(ErrorCode.MODEL_BAD_OUTPUT, "provider returned an empty response")
                    payload = json.loads(content)
                    usage = getattr(response, "usage", None)
                    finish_reason = getattr(response.choices[0], "finish_reason", None)
                    input_tokens = getattr(usage, "prompt_tokens", None)
                    output_tokens = getattr(usage, "completion_tokens", None)
                    estimated_cost, cost_status = self._prices.estimate(
                        selection.model_id, input_tokens, output_tokens
                    )
                    trace = InferenceTrace(
                        trace_id=trace_id,
                        mission_id=mission_id,
                        stage=stage,
                        requested_tier=selection.tier,
                        actual_tier=selection.tier,
                        actual_model_id=selection.model_id,
                        routing_reason=selection.reason,
                        prompt_revision=prompt_revision,
                        started_at_utc=started_at,
                        latency_ms=int((time.perf_counter() - started) * 1000),
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        total_tokens=getattr(usage, "total_tokens", None),
                        success=True,
                        provider_request_id=getattr(response, "_request_id", None),
                        estimated_cost_usd=estimated_cost,
                        cost_status=cost_status,
                        response_truncated=finish_reason == "length",
                    )
                    self._record_trace(trace)
                    return payload, trace
                except (APITimeoutError, asyncio.TimeoutError):
                    error = ServiceError(ErrorCode.AI_TIMEOUT, "Nebius request timed out", True)
                except APIStatusError as exc:
                    if exc.status_code == 429:
                        error = ServiceError(
                            ErrorCode.PROVIDER_RATE_LIMIT,
                            "Nebius provider rate limit reached",
                            True,
                        )
                    else:
                        error = ServiceError(
                            ErrorCode.AI_UNAVAILABLE,
                            "Nebius provider is unavailable",
                            exc.status_code >= 500,
                        )
                except APIConnectionError:
                    error = ServiceError(ErrorCode.AI_UNAVAILABLE, "Nebius provider is unavailable", True)
                except (json.JSONDecodeError, TypeError, ServiceError) as exc:
                    error = exc if isinstance(exc, ServiceError) else ServiceError(ErrorCode.MODEL_BAD_OUTPUT, "model did not return valid JSON")
                if not error.retryable or attempt >= self.settings.nebius_max_provider_retries:
                    break
                await asyncio.sleep(0.25 * (2**attempt))
        assert error is not None
        self._record_trace(
            InferenceTrace(
                trace_id=trace_id,
                mission_id=mission_id,
                stage=stage,
                requested_tier=selection.tier,
                actual_tier=selection.tier,
                actual_model_id=selection.model_id,
                routing_reason=selection.reason,
                prompt_revision=prompt_revision,
                started_at_utc=started_at,
                latency_ms=int((time.perf_counter() - started) * 1000),
                input_tokens=None,
                output_tokens=None,
                total_tokens=None,
                success=False,
                error_code=error.code.value,
            )
        )
        raise error

    def _record_trace(self, trace: InferenceTrace) -> None:
        self.traces.append(trace)
        logger.info("nebius_inference %s", json.dumps(asdict(trace), sort_keys=True))

    def mark_trace_failed(self, trace_id: str, error_code: str) -> None:
        for index in range(len(self.traces) - 1, -1, -1):
            if self.traces[index].trace_id == trace_id:
                corrected = replace(self.traces[index], success=False, error_code=error_code)
                self.traces[index] = corrected
                logger.info(
                    "nebius_inference_schema_rejection %s",
                    json.dumps(asdict(corrected), sort_keys=True),
                )
                return

    def sanitized_traces(self) -> list[dict[str, Any]]:
        return [asdict(trace) for trace in self.traces]
