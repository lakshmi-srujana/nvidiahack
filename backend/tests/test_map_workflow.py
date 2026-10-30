import base64

from fastapi.testclient import TestClient

from app.config import Settings
from app.context.geocoding import parse_results
from app.context.local_vision import parse_vision_boxes
from app.context.osm_features import parse_osm_features
from app.main import create_app

AREA = [
    [-122.085, 37.4215], [-122.083, 37.4215],
    [-122.083, 37.4235], [-122.085, 37.4235],
]
ZONE = [
    [-122.0842, 37.4221], [-122.0838, 37.4221],
    [-122.0838, 37.4225], [-122.0842, 37.4225],
]


def client():
    return TestClient(create_app(Settings(_env_file=None, app_mode="test")))


def test_map_selected_polygon_manual_route_and_zone_safety():
    with client() as api:
        created = api.post("/api/v1/demo/survey", json={
            "instruction": "Survey the selected area", "coordinates": AREA,
        })
        assert created.status_code == 200
        assert created.json()["mission"]["survey_area"]["coordinates"][0][:4] == AREA

        route = api.post("/api/v1/demo/route/manual", json={
            "coordinates": [[-122.0846, 37.4218], [-122.0835, 37.4223]],
        })
        assert route.status_code == 200
        assert route.json()["plan"]["waypoints"][1]["longitude"] == -122.0846
        assert api.post("/api/v1/demo/verify").json()["certificate"]

        safe = api.post("/api/v1/demo/zones", json={
            "name": "Pickup", "zone_type": "pickup", "coordinates": ZONE,
        })
        assert safe.status_code == 200
        assert safe.json()["certificate"] is None
        assert api.post("/api/v1/demo/verify").json()["certificate"]

        blocked = api.post("/api/v1/demo/zones", json={
            "name": "No flight", "zone_type": "no_fly", "coordinates": ZONE,
        })
        assert blocked.status_code == 200
        assert blocked.json()["status"] == "DRAFT"
        rejected = api.post("/api/v1/demo/verify").json()
        assert rejected["status"] == "REJECTED"
        assert rejected["certificate"] is None
        assert any(item["rule_id"] == "RULE_02_RESTRICTED_ZONE_CLEARANCE" for item in rejected["verdict"]["violations"])

        zone_id = next(zone["zone_id"] for zone in blocked.json()["world"]["zones"] if zone["name"] == "No flight")
        assert api.delete(f"/api/v1/demo/zones/{zone_id}").status_code == 200
        assert api.post("/api/v1/demo/verify").json()["certificate"]


def test_auto_route_is_geographic_and_verified():
    with client() as api:
        result = api.post("/api/v1/demo/route/auto")
        assert result.status_code == 200
        body = result.json()
        assert body["status"] == "CERTIFIED"
        assert body["certificate"]
        assert len(body["plan"]["waypoints"]) > 3
        assert body["plan"]["waypoints"][0]["longitude"] == body["drone"]["location"][0]


def test_injected_event_uses_operator_picked_coordinates():
    with client() as api:
        api.post("/api/v1/demo/verify")
        api.post("/api/v1/demo/launch")
        picked = [-122.084, 37.422]
        event = api.post("/api/v1/demo/event", json={"family": "SURVIVOR_DETECTED", "location": picked})
        assert event.status_code == 200
        assert event.json()["events"][-1]["payload"]["location"] == picked
        assert event.json()["events"][-1]["source"] == "OPERATOR"

    with client() as api:
        api.post("/api/v1/demo/verify")
        api.post("/api/v1/demo/launch")
        assert api.post("/api/v1/demo/event", json={"family": "NEW_RESTRICTED_ZONE"}).status_code == 422
        result = api.post("/api/v1/demo/event", json={"family": "NEW_RESTRICTED_ZONE", "zone_coordinates": ZONE})
        assert result.status_code == 200
        assert any(zone["source"] == "event" for zone in result.json()["world"]["zones"])


def test_osm_mapped_geometry_is_not_invented_and_requires_confirmation(monkeypatch):
    osm_way = {"type": "way", "id": 42, "tags": {"building": "yes", "name": "Mapped hall"},
               "geometry": [{"lon": lon, "lat": lat} for lon, lat in [*ZONE, ZONE[0]]]}
    parsed = parse_osm_features({"elements": [osm_way]}, [*AREA, AREA[0]])
    assert set(parsed[0]["coordinates"][:-1]) == {tuple(point) for point in ZONE}
    assert parsed[0]["source_url"] == "https://www.openstreetmap.org/way/42"

    async def fake_fetch(_ring):
        return parsed, "OpenStreetMap test fixture"

    monkeypatch.setattr("app.demo.fetch_osm_features", fake_fetch)
    with client() as api:
        first = api.post("/api/v1/demo/analyze-map").json()
        second = api.post("/api/v1/demo/analyze-map").json()
        assert first["map_findings"] == second["map_findings"]
        assert first["map_findings"][0]["osm_id"] == 42
        assert first["certificate"] is None


def test_local_vision_boxes_use_real_viewport_coordinates_and_stay_suggestions(monkeypatch):
    bounds = (-122.086, 37.4205, -122.082, 37.4245)
    content = '{"detections":[{"kind":"building","label":"Roof","box":[250,250,500,500]}]}'
    parsed = parse_vision_boxes(content, bounds, [*AREA, AREA[0]])
    assert len(parsed) == 1
    assert len(parse_vision_boxes('{"kind":"building","box":[250,250,500,500]}', bounds, [*AREA, AREA[0]])) == 1
    assert parsed[0]["source"] == "local_vision"
    assert parsed[0]["review_required"] is True
    assert all(-122.085 <= lon <= -122.083 and 37.4215 <= lat <= 37.4235
               for lon, lat in parsed[0]["coordinates"])

    async def fake_analyze(_image, _bounds, _ring):
        return parsed, {"source": "Local Ollama vision", "model": "fixture",
                        "count": 1, "retrieved_at": "2026-10-30T00:00:00Z",
                        "note": "Review required"}

    monkeypatch.setattr("app.demo.analyze_local_image", fake_analyze)
    with client() as api:
        api.post("/api/v1/demo/survey", json={"instruction": "Survey this area", "coordinates": AREA})
        image = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"x" * 120).decode()
        result = api.post("/api/v1/demo/vision/local", json={
            "image_base64": image, "bounds": bounds,
        })
        assert result.status_code == 200
        assert result.json()["vision_findings"][0]["label"] == "Roof"
        assert result.json()["world"]["restricted_zones"] == []


def test_automatic_suggestions_become_reviewable_zones_and_affect_verification(monkeypatch):
    threat = {"kind": "possible_threat", "label": "Utility site", "coordinates": [*ZONE, ZONE[0]],
              "osm_id": 99, "source_url": "https://www.openstreetmap.org/way/99"}

    async def fake_fetch(_ring):
        return [threat], "OpenStreetMap fixture"

    monkeypatch.setattr("app.demo.fetch_osm_features", fake_fetch)
    with client() as api:
        api.post("/api/v1/demo/survey", json={"instruction": "Survey this area", "coordinates": AREA})
        api.post("/api/v1/demo/analyze-map")
        first = api.post("/api/v1/demo/zones/auto")
        assert first.status_code == 200
        zones = first.json()["world"]["zones"]
        assert len(zones) == 1
        assert zones[0]["zone_type"] == "restricted"
        assert zones[0]["source"] == "auto_suggestion"
        assert api.post("/api/v1/demo/zones/auto").json()["world"]["zones"] == zones
        assert len(api.post("/api/v1/demo/verify").json()["world"]["restricted_zones"]) == 1


def test_address_or_pin_lookup_returns_provider_coordinates(monkeypatch):
    provider = [{"display_name": "MG Road, Bengaluru", "lat": "12.975",
                 "lon": "77.605", "boundingbox": ["12.974", "12.976", "77.604", "77.606"],
                 "osm_type": "way", "osm_id": 123}]
    assert parse_results(provider)[0]["bounds"] == [77.604, 12.974, 77.606, 12.976]

    async def fake_search(query):
        assert query == "560001"
        return parse_results(provider)

    monkeypatch.setattr("app.demo.search_location", fake_search)
    with client() as api:
        result = api.get("/api/v1/demo/location/search", params={"q": "560001"})
        assert result.status_code == 200
        assert result.json()["results"][0]["latitude"] == 12.975
        assert result.json()["results"][0]["longitude"] == 77.605


def test_replan_detours_around_injected_restriction():
    with client() as api:
        api.post("/api/v1/demo/survey", json={"instruction": "Survey this area", "coordinates": AREA})
        route = [
            [-122.0845, 37.4218], [-122.084, 37.4223], [-122.0834, 37.4229],
        ]
        api.post("/api/v1/demo/route/manual", json={"coordinates": route})
        assert api.post("/api/v1/demo/verify").json()["certificate"]
        assert api.post("/api/v1/demo/launch").json()["status"] == "ACTIVE"
        api.post("/api/v1/demo/tick")
        blocked = [[-122.0841, 37.4222], [-122.0839, 37.4222],
                   [-122.0839, 37.4224], [-122.0841, 37.4224]]
        event = api.post("/api/v1/demo/event", json={
            "family": "NEW_RESTRICTED_ZONE", "zone_coordinates": blocked,
        })
        assert event.status_code == 200
        replanned = api.post("/api/v1/demo/replan")
        assert replanned.status_code == 200
        state = replanned.json()
        assert state["plan"]["revision"] == 3
        assert state["plan"]["provenance"]["repair_attempt"] == 1
        assert state["certificate"]
        assert all(
            not (-122.0841 < waypoint["longitude"] < -122.0839
                 and 37.4222 < waypoint["latitude"] < 37.4224)
            for waypoint in state["plan"]["waypoints"]
        )
