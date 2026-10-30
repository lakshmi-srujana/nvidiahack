"""Small deterministic geographic route proposal for the local demo."""

from __future__ import annotations

import heapq
import math

from fastapi import HTTPException
from shapely import affinity
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
from verifier.rules import degrees_to_approx_metres, haversine_distance_m

BLOCKING = {"restricted", "no_man", "no_fly", "unknown"}
TARGETS = {"planned", "pickup", "destination_drop", "safe"}


def _buffered_zone(zone: dict, latitude: float) -> Polygon:
    polygon = Polygon(zone["boundary"]["coordinates"][0])
    metres_lon, metres_lat = degrees_to_approx_metres(latitude)
    scaled = affinity.scale(polygon, xfact=metres_lon, yfact=metres_lat, origin=(0, 0))
    buffered = scaled.buffer(float(zone.get("buffer_m", 0)) + 3.0, quad_segs=4)
    return affinity.scale(buffered, xfact=1 / metres_lon, yfact=1 / metres_lat, origin=(0, 0))


def _sample_coverage(free: Polygon) -> list[tuple[float, float]]:
    west, south, east, north = free.bounds
    points: list[tuple[float, float]] = []
    for row, fraction in enumerate((0.33, 0.66)):
        latitude = south + (north - south) * fraction
        pieces = free.intersection(LineString([(west, latitude), (east, latitude)]))
        segments = [pieces] if pieces.geom_type == "LineString" else list(getattr(pieces, "geoms", []))
        segments = [segment for segment in segments if segment.geom_type == "LineString" and segment.length > 0.00001]
        segments.sort(key=lambda segment: segment.centroid.x)
        if row % 2:
            segments.reverse()
        for segment in segments[:4]:
            endpoints = [
                (segment.interpolate(fraction, normalized=True).x,
                 segment.interpolate(fraction, normalized=True).y)
                for fraction in (0.02, 0.98)
            ]
            if row % 2:
                endpoints.reverse()
            points.extend(endpoints)
    return points[:24]


def generate_geographic_route(
    area_ring: list[tuple[float, float]], zones: list[dict],
    start: tuple[float, float], home: tuple[float, float],
    coverage_points: list[tuple[float, float]] | None = None,
) -> list[tuple[float, float]]:
    area = Polygon(area_ring)
    latitude = area.centroid.y
    blockers = [_buffered_zone(zone, latitude) for zone in zones if zone["active"] and zone["zone_type"] in BLOCKING]
    free = area.difference(unary_union(blockers)) if blockers else area
    if free.is_empty or not free.covers(Point(start)) or not free.covers(Point(home)):
        raise HTTPException(409, "Start or home is inside an exclusion zone")

    if coverage_points is None:
        goals = _sample_coverage(free)
        for zone in zones:
            if zone["active"] and zone["zone_type"] in TARGETS:
                center = Polygon(zone["boundary"]["coordinates"][0]).representative_point()
                if free.covers(center):
                    goals.append((center.x, center.y))
    else:
        goals = [point for point in coverage_points if free.covers(Point(point))]

    support = list(area.exterior.coords)[:-1]
    for polygon in blockers:
        vertices = list(polygon.exterior.coords)[:-1]
        step = max(1, math.ceil(len(vertices) / 16))
        support.extend(vertices[::step])
    nodes = list(dict.fromkeys((float(x), float(y)) for x, y in [start, *goals, home, *support]))
    if len(nodes) > 160:
        raise HTTPException(422, "Too many zone vertices for the local route planner")
    adjacency: list[list[tuple[int, float]]] = [[] for _ in nodes]
    for left in range(len(nodes)):
        for right in range(left + 1, len(nodes)):
            segment = LineString([nodes[left], nodes[right]])
            if free.covers(segment):
                length = haversine_distance_m(nodes[left], nodes[right])
                adjacency[left].append((right, length))
                adjacency[right].append((left, length))

    def shortest_path(origin: int, destination: int) -> list[int]:
        queue = [(0.0, origin)]
        costs = {origin: 0.0}
        parents: dict[int, int] = {}
        while queue:
            distance, current = heapq.heappop(queue)
            if current == destination:
                result = [current]
                while current in parents:
                    current = parents[current]
                    result.append(current)
                return list(reversed(result))
            if distance > costs[current]:
                continue
            for neighbor, length in adjacency[current]:
                candidate = distance + length
                if candidate < costs.get(neighbor, math.inf):
                    costs[neighbor] = candidate
                    parents[neighbor] = current
                    heapq.heappush(queue, (candidate, neighbor))
        raise HTTPException(409, "No route within the survey area avoids all exclusion zones")

    ordered = [nodes.index((float(x), float(y))) for x, y in [start, *goals, home]]
    route = [nodes[ordered[0]]]
    for source, destination in zip(ordered, ordered[1:], strict=False):
        route.extend(nodes[index] for index in shortest_path(source, destination)[1:])
    if len(route) > 98:
        raise HTTPException(422, "Generated route exceeds the waypoint limit; select a smaller area")
    return route
