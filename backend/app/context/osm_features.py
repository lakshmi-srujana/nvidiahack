"""Fetch bounded OpenStreetMap features for operator review, without inference charges."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
from fastapi import HTTPException
from shapely.geometry import Polygon

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OSM_MAP_URL = "https://api.openstreetmap.org/api/0.6/map"


def _kind(tags: dict) -> tuple[str, str] | None:
    if tags.get("natural") == "water" or "water" in tags or tags.get("waterway") == "riverbank" or tags.get("landuse") in {"reservoir", "basin"}:
        return "water", tags.get("name") or "Mapped water body"
    if tags.get("power") in {"substation", "plant"} or tags.get("landuse") in {"industrial", "brownfield", "landfill"} or tags.get("man_made") in {"dam", "wastewater_plant"}:
        return "possible_threat", tags.get("name") or "Mapped industrial or utility site"
    if tags.get("building") and tags.get("building") != "no":
        return "building", tags.get("name") or "Mapped building"
    return None


def parse_osm_features(payload: dict, survey_ring: list[tuple[float, float]]) -> list[dict]:
    area = Polygon(survey_ring)
    findings: list[dict] = []
    for item in payload.get("elements", []):
        if item.get("type") != "way" or not isinstance(item.get("geometry"), list):
            continue
        classified = _kind(item.get("tags") or {})
        if classified is None:
            continue
        coordinates = [(part["lon"], part["lat"]) for part in item["geometry"] if "lon" in part and "lat" in part]
        if len(coordinates) < 4 or coordinates[0] != coordinates[-1]:
            continue
        polygon = Polygon(coordinates)
        if not polygon.is_valid or polygon.area <= 0:
            continue
        clipped = polygon.intersection(area)
        if clipped.is_empty:
            continue
        if clipped.geom_type == "MultiPolygon":
            clipped = max(clipped.geoms, key=lambda part: part.area)
        if clipped.geom_type != "Polygon" or clipped.area <= 0:
            continue
        simplified = clipped.simplify(0.000005, preserve_topology=True)
        ring = [(round(lon, 7), round(lat, 7)) for lon, lat in simplified.exterior.coords]
        if len(ring) > 100:
            continue
        kind, label = classified
        findings.append({
            "kind": kind, "label": label, "coordinates": ring,
            "osm_id": item.get("id"), "source_url": f"https://www.openstreetmap.org/way/{item.get('id')}",
            "mapped_tags": item.get("tags") or {},
            "mapped_area": clipped.area,
        })
    priority = {"possible_threat": 0, "water": 1, "building": 2}
    findings.sort(key=lambda finding: (priority[finding["kind"]], -finding["mapped_area"]))
    return [{key: value for key, value in finding.items() if key != "mapped_area"} for finding in findings[:120]]


def _main_api_to_overpass_shape(payload: dict) -> dict:
    nodes = {item["id"]: item for item in payload.get("elements", []) if item.get("type") == "node"}
    elements = []
    for item in payload.get("elements", []):
        if item.get("type") != "way":
            continue
        geometry = [{"lon": nodes[node_id]["lon"], "lat": nodes[node_id]["lat"]}
                    for node_id in item.get("nodes", []) if node_id in nodes]
        elements.append({**item, "geometry": geometry})
    return {"elements": elements}


async def fetch_osm_features(survey_ring: list[tuple[float, float]]) -> tuple[list[dict], str]:
    west, south, east, north = Polygon(survey_ring).bounds
    if east - west > 0.03 or north - south > 0.03:
        raise HTTPException(422, "Zoom in or draw an area within 0.03 degrees per side for map feature analysis")
    bbox = f"{south:.7f},{west:.7f},{north:.7f},{east:.7f}"
    query = (
        "[out:json][timeout:15][maxsize:33554432];("
        f'way["building"]({bbox});'
        f'way["natural"="water"]({bbox});'
        f'way["water"]({bbox});'
        f'way["waterway"="riverbank"]({bbox});'
        f'way["landuse"~"^(reservoir|basin|industrial|brownfield|landfill)$"]({bbox});'
        f'way["power"~"^(substation|plant)$"]({bbox});'
        f'way["man_made"~"^(dam|wastewater_plant)$"]({bbox});'
        ");out geom;"
    )
    source = "OpenStreetMap via Overpass"
    async with httpx.AsyncClient(timeout=8, headers={"User-Agent": "SkyWardenPrototype/0.1 (local map feature review)"}) as client:
        try:
            response = await client.post(OVERPASS_URL, data={"data": query})
            response.raise_for_status()
            if len(response.content) > 4_000_000:
                raise HTTPException(422, "Too many mapped features; select a smaller area")
            payload = response.json()
        except (httpx.HTTPError, ValueError) as primary_error:
            if east - west > 0.01 or north - south > 0.01:
                raise HTTPException(503, "Overpass is unavailable; select an area within 0.01 degrees for the demo fallback") from primary_error
            try:
                response = await client.get(OSM_MAP_URL, params={"bbox": f"{west:.7f},{south:.7f},{east:.7f},{north:.7f}"}, headers={"Accept": "application/json"})
                response.raise_for_status()
                if len(response.content) > 4_000_000:
                    raise HTTPException(422, "Too many mapped features; select a smaller area")
                payload = _main_api_to_overpass_shape(response.json())
                source = "OpenStreetMap small-area API fallback"
            except (httpx.HTTPError, ValueError) as fallback_error:
                raise HTTPException(503, "OpenStreetMap feature lookup is temporarily unavailable") from fallback_error
    if not isinstance(payload, dict) or "elements" not in payload:
        raise HTTPException(503, "OpenStreetMap feature lookup returned an invalid response")
    return parse_osm_features(payload, survey_ring), source


def analysis_record(findings: list[dict], source: str) -> dict:
    return {"source": source, "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "count": len(findings), "note": "Mapped features may be incomplete or outdated; potential threats require operator review."}
