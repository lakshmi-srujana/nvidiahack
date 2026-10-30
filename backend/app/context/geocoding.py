"""User-triggered, cached address/PIN lookup for the local mission map."""

from __future__ import annotations

import asyncio
import math
import os
import re
import time

import httpx
from fastapi import HTTPException

GEOCODER_URL = os.getenv("SKYWARDEN_GEOCODER_URL", "https://nominatim.openstreetmap.org/search")
USER_AGENT = "SkyWardenSurveyPrototype/0.1 (https://github.com/lakshmi-srujana/nvidiahack)"
_lock = asyncio.Lock()
_last_request = 0.0
_cache: dict[str, tuple[float, list[dict]]] = {}


def parse_results(payload: object) -> list[dict]:
    if not isinstance(payload, list):
        raise HTTPException(503, "Location provider returned an invalid response")
    results = []
    for item in payload[:5]:
        if not isinstance(item, dict):
            continue
        try:
            latitude, longitude = float(item["lat"]), float(item["lon"])
            south, north, west, east = [float(value) for value in item["boundingbox"]]
        except (KeyError, TypeError, ValueError):
            continue
        if not all(math.isfinite(value) for value in (latitude, longitude, south, north, west, east)):
            continue
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180 and south <= latitude <= north and west <= longitude <= east):
            continue
        results.append({
            "label": str(item.get("display_name") or "Mapped location")[:300],
            "latitude": latitude, "longitude": longitude,
            "bounds": [west, south, east, north],
            "osm_type": item.get("osm_type"), "osm_id": item.get("osm_id"),
        })
    return results


async def search_location(query: str) -> list[dict]:
    global _last_request
    normalized = " ".join(query.strip().split())
    if not 3 <= len(normalized) <= 200:
        raise HTTPException(422, "Enter an address or six-digit Indian PIN code")
    key = normalized.casefold()
    async with _lock:
        now = time.monotonic()
        cached = _cache.get(key)
        if cached and now - cached[0] < 86400:
            return cached[1]
        # OSMF public Nominatim permits at most one request per second per app.
        await asyncio.sleep(max(0.0, 1.05 - (now - _last_request)))
        _last_request = time.monotonic()
        params: dict[str, str | int] = {"format": "jsonv2", "limit": 5, "addressdetails": 1}
        if re.fullmatch(r"[1-9][0-9]{5}", normalized):
            params.update({"postalcode": normalized, "countrycodes": "in"})
        else:
            params["q"] = normalized
        try:
            async with httpx.AsyncClient(timeout=12, headers={"User-Agent": USER_AGENT}) as client:
                response = await client.get(GEOCODER_URL, params=params)
                response.raise_for_status()
                results = parse_results(response.json())
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(503, "Address lookup is temporarily unavailable") from exc
        _cache[key] = (time.monotonic(), results)
        return results
