"""Geometry checks for operator-selected demo areas and map-drawn plans."""

from __future__ import annotations

import math

from fastapi import HTTPException
from shapely.geometry import Polygon
from verifier.rules import haversine_distance_m

Point = tuple[float, float]


def validate_point(point: Point) -> Point:
    lon, lat = point
    if not (math.isfinite(lon) and math.isfinite(lat) and -180 <= lon <= 180 and -90 <= lat <= 90):
        raise HTTPException(422, "Coordinates must be finite WGS84 longitude and latitude")
    return float(lon), float(lat)


def validate_ring(points: list[Point], *, area: Polygon | None = None) -> list[Point]:
    if not 3 <= len(points) <= 100:
        raise HTTPException(422, "A polygon needs 3 to 100 vertices")
    ring = [validate_point(point) for point in points]
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    polygon = Polygon(ring)
    if not polygon.is_valid or polygon.area <= 0:
        raise HTTPException(422, "The drawn polygon must not cross itself or have zero area")
    west, south, east, north = polygon.bounds
    if east - west > 0.1 or north - south > 0.1:
        raise HTTPException(422, "The demo area must be within 0.1 degrees per side; zoom in")
    if area is not None and not area.covers(polygon):
        raise HTTPException(422, "The drawn zone must be inside the locked survey area")
    return ring


def validate_route(points: list[Point]) -> list[Point]:
    if not 2 <= len(points) <= 98:
        raise HTTPException(422, "A route needs 2 to 98 map-picked waypoints")
    route = [validate_point(point) for point in points]
    if all(haversine_distance_m(a, b) < 0.1 for a, b in zip(route, route[1:], strict=False)):
        raise HTTPException(422, "The route needs at least two distinct locations")
    return route
