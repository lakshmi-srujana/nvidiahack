from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from enum import StrEnum

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.config import Settings
from app.context.sanitizer import EvidenceItem, sanitize_evidence
from app.contracts import Mission


class ContextStatus(StrEnum):
    OK = "OK"
    NO_RESULTS = "NO_RESULTS"
    UNAVAILABLE = "UNAVAILABLE"


class ContextBundle(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: ContextStatus
    query: str | None = None
    items: tuple[EvidenceItem, ...] = ()
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    latency_ms: int | None = None
    from_cache: bool = False
    warnings: tuple[str, ...] = ()


class TavilyContextClient:
    """Bounded Tavily search whose output never acquires trusted-state authority."""

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self._client = http_client
        self._owns_client = http_client is None
        self._cache: dict[str, tuple[float, ContextBundle]] = {}
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.settings.tavily_timeout_s)

    async def close(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def context_for(self, mission: Mission) -> ContextBundle:
        if not self.settings.tavily_enabled:
            return ContextBundle(
                status=ContextStatus.UNAVAILABLE,
                warnings=("Tavily context is disabled",),
            )
        if not self.settings.tavily_api_key:
            return ContextBundle(
                status=ContextStatus.UNAVAILABLE,
                warnings=("Tavily is enabled but no API key is configured",),
            )

        query = self._query(mission)
        now = time.monotonic()
        cached = self._cache.get(query)
        if cached and now - cached[0] <= self.settings.tavily_cache_ttl_s:
            return cached[1].model_copy(update={"from_cache": True})

        async with self._lock:
            cached = self._cache.get(query)
            now = time.monotonic()
            if cached and now - cached[0] <= self.settings.tavily_cache_ttl_s:
                return cached[1].model_copy(update={"from_cache": True})
            bundle = await self._search(query)
            if bundle.status in {ContextStatus.OK, ContextStatus.NO_RESULTS}:
                self._cache[query] = (time.monotonic(), bundle)
            return bundle

    def _query(self, mission: Mission) -> str:
        today = datetime.now(timezone.utc).date().isoformat()
        return f"flood advisory {mission.approved_location_label} {today}"[:300]

    async def _search(self, query: str) -> ContextBundle:
        if self._client is None:
            await self.start()
        assert self._client is not None
        started = time.perf_counter()
        try:
            response = await self._client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": self.settings.tavily_api_key.get_secret_value(),
                    "query": query,
                    "topic": "news",
                    "search_depth": "basic",
                    "max_results": self.settings.tavily_max_results,
                    "include_raw_content": False,
                },
            )
            response.raise_for_status()
            payload = response.json()
            raw_results = payload.get("results", []) if isinstance(payload, dict) else []
            results = [item for item in raw_results if isinstance(item, dict)]
            items = tuple(
                sanitize_evidence(results, char_limit=self.settings.tavily_context_char_limit)
            )
            return ContextBundle(
                status=ContextStatus.OK if items else ContextStatus.NO_RESULTS,
                query=query,
                items=items,
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
        except (httpx.HTTPError, ValueError, TypeError):
            return ContextBundle(
                status=ContextStatus.UNAVAILABLE,
                query=query,
                latency_ms=int((time.perf_counter() - started) * 1000),
                warnings=("Tavily request failed; no live web context was used",),
            )
