"""Local-only map image suggestions. Model boxes are advisory, not flight authority."""

from __future__ import annotations

import base64
import binascii
import json
import math
import os
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException
from shapely.geometry import Polygon

MODEL = os.getenv("SKYWARDEN_LOCAL_VISION_MODEL", "qwen3.5:2b")
OLLAMA = "http://127.0.0.1:11434"
KINDS = {"building", "water", "possible_threat"}


def _coordinate(box: list[float], west: float, south: float, east: float, north: float) -> list[tuple[float, float]]:
    """Project a normalized screenshot box through the unpitched Mercator map."""
    left, top, right, bottom = [value / 1000 for value in box]
    north_y = math.asinh(math.tan(math.radians(north)))
    south_y = math.asinh(math.tan(math.radians(south)))

    def point(x: float, y: float) -> tuple[float, float]:
        longitude = west + (east - west) * x
        latitude = math.degrees(math.atan(math.sinh(north_y + (south_y - north_y) * y)))
        return round(longitude, 7), round(latitude, 7)

    return [point(left, top), point(right, top), point(right, bottom), point(left, bottom), point(left, top)]


def parse_vision_boxes(
    content: str, bounds: tuple[float, float, float, float], survey_ring: list[tuple[float, float]],
) -> list[dict]:
    try:
        data = json.loads(content)
    except (TypeError, ValueError) as exc:
        raise HTTPException(502, "Local vision returned invalid JSON") from exc
    detections = data.get("detections") if isinstance(data, dict) else data if isinstance(data, list) else None
    if detections is None and isinstance(data, dict) and {"kind", "box"} <= data.keys():
        detections = [data]
    if not isinstance(detections, list):
        raise HTTPException(502, "Local vision did not return a detection list")
    west, south, east, north = bounds
    survey = Polygon(survey_ring)
    findings: list[dict] = []
    for item in detections[:16]:
        if not isinstance(item, dict) or item.get("kind") not in KINDS:
            continue
        box = item.get("box")
        if not isinstance(box, list) or len(box) != 4 or any(
            not isinstance(value, (int, float)) or not math.isfinite(value) for value in box
        ):
            continue
        left, top, right, bottom = box
        if not (0 <= left < right <= 1000 and 0 <= top < bottom <= 1000):
            continue
        if (right - left) * (bottom - top) < 100:
            continue
        clipped = Polygon(_coordinate(box, west, south, east, north)).intersection(survey)
        if clipped.is_empty:
            continue
        if clipped.geom_type == "MultiPolygon":
            clipped = max(clipped.geoms, key=lambda polygon: polygon.area)
        if clipped.geom_type != "Polygon" or clipped.area <= 0:
            continue
        label = str(item.get("label") or item["kind"].replace("_", " "))[:100]
        findings.append({
            "kind": item["kind"], "label": label,
            "coordinates": [(round(x, 7), round(y, 7)) for x, y in clipped.exterior.coords],
            "source": "local_vision", "model": MODEL, "review_required": True,
        })
    return findings


async def analyze_local_image(
    image_base64: str, bounds: tuple[float, float, float, float],
    survey_ring: list[tuple[float, float]],
) -> tuple[list[dict], dict]:
    try:
        image = base64.b64decode(image_base64, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise HTTPException(422, "Map image must be valid base64") from exc
    if len(image) < 100 or len(image) > 2_000_000 or not image.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(422, "Map image must be a PNG under 2 MB")
    west, south, east, north = bounds
    if not all(map(math.isfinite, bounds)) or not (-180 <= west < east <= 180 and -85 <= south < north <= 85):
        raise HTTPException(422, "Invalid WGS84 map viewport")
    if east - west > 0.1 or north - south > 0.1:
        raise HTTPException(422, "Zoom in before local image analysis")
    prompt = (
        "Inspect this OpenStreetMap image. Return JSON only, with key detections. "
        "Each detection has kind (building, water, or possible_threat), a brief label, "
        "and box [left, top, right, bottom] in integer 0-1000 image coordinates. "
        "Identify only clearly visible map features. Do not infer security threats "
        "from ordinary roads or buildings. For possible_threat use only clearly marked "
        "industrial, utility, dam, or hazard sites. Return at most 12 detections. "
        "If unsure, return an empty list. No markdown."
    )
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            tags = await client.get(f"{OLLAMA}/api/tags")
            tags.raise_for_status()
            installed = {item.get("name") for item in tags.json().get("models", [])}
            if MODEL not in installed:
                raise HTTPException(503, f"Local vision model {MODEL} is not installed in Ollama")
            response = await client.post(f"{OLLAMA}/api/chat", json={
                "model": MODEL, "stream": False, "format": "json", "think": False,
                "options": {"temperature": 0, "num_predict": 800},
                "messages": [{"role": "user", "content": prompt, "images": [image_base64]}],
            })
            response.raise_for_status()
            content = response.json().get("message", {}).get("content")
    except httpx.HTTPError as exc:
        raise HTTPException(503, "Local Ollama vision is unavailable or timed out") from exc
    findings = parse_vision_boxes(content, bounds, survey_ring)
    record = {
        "source": "Local Ollama vision", "model": MODEL,
        "retrieved_at": datetime.now(timezone.utc).isoformat(), "count": len(findings),
        "note": "Image boxes are approximate map suggestions. Operator review is required.",
    }
    return findings, record
