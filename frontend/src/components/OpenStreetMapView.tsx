import { useEffect, useRef, useState, type Ref } from "react";
import * as maplibregl from "maplibre-gl";
import type { GeoJSONSource, LngLatBoundsLike } from "maplibre-gl";
import type { FeatureCollection } from "geojson";
import "maplibre-gl/dist/maplibre-gl.css";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";

maplibregl.setWorkerUrl(workerUrl);

export type Point = [number, number];
export type MapMode = "browse" | "area" | "zone" | "route" | "event_zone" | "pick";
export type ZoneKind = "restricted" | "planned" | "no_man" | "no_fly" | "destination_drop" | "pickup" | "safe" | "unknown";
export type MapZone = {
  zone_id: string; name: string; zone_type: ZoneKind; boundary: { coordinates: Point[][] };
  active: boolean; source: string;
};
export type MapFinding = {
  kind: "building" | "water" | "possible_threat"; label: string;
  coordinates: Point[]; osm_id?: number; source_url?: string;
  source?: string; model?: string; review_required?: boolean;
};
export type MapState = {
  scenario: string;
  mission: { mission_id: string };
  world: { geofence_boundary: { coordinates: Point[][] }; zones: MapZone[] };
  plan: { waypoints: { longitude: number; latitude: number }[] };
  drone: { location: Point };
  map_findings: MapFinding[];
  vision_findings?: MapFinding[];
};
export type MapHandle = {
  visibleArea: () => Point[] | null;
  capture: () => Promise<{ image_base64: string; bounds: [number, number, number, number] } | null>;
  goTo: (point: Point, zoom: number) => void;
};

const emptyCollection: FeatureCollection = { type: "FeatureCollection", features: [] };
const zoneColors: Record<ZoneKind, string> = {
  restricted: "#dc2626", planned: "#2563eb", no_man: "#a21caf", no_fly: "#b91c1c",
  destination_drop: "#f97316", pickup: "#0d9488", safe: "#16a34a", unknown: "#64748b",
};
const zoneColorExpression: maplibregl.ExpressionSpecification = [
  "match", ["get", "zone_type"],
  "restricted", zoneColors.restricted, "planned", zoneColors.planned,
  "no_man", zoneColors.no_man, "no_fly", zoneColors.no_fly,
  "destination_drop", zoneColors.destination_drop, "pickup", zoneColors.pickup,
  "safe", zoneColors.safe, "unknown", zoneColors.unknown, "#64748b",
];

function polygons(polygonsToDraw: { coordinates: Point[][]; properties?: Record<string, unknown> }[]): FeatureCollection {
  return {
    type: "FeatureCollection",
    features: polygonsToDraw.filter((polygon) => polygon.coordinates[0]?.length >= 4).map((polygon) => ({
      type: "Feature", properties: polygon.properties || {},
      geometry: { type: "Polygon", coordinates: polygon.coordinates },
    })),
  };
}

function line(points: Point[]): FeatureCollection {
  return points.length < 2 ? emptyCollection : {
    type: "FeatureCollection",
    features: [{ type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: points } }],
  };
}

function dots(points: Point[]): FeatureCollection {
  return {
    type: "FeatureCollection",
    features: points.map((coordinates, index) => ({
      type: "Feature", properties: { label: String(index + 1) },
      geometry: { type: "Point", coordinates },
    })),
  };
}

function setSource(map: maplibregl.Map, id: string, data: FeatureCollection) {
  (map.getSource(id) as GeoJSONSource).setData(data);
}

type Props = {
  state: MapState;
  mode: MapMode;
  locked: boolean;
  onPick: (point: Point) => void;
  onDrawComplete: (mode: MapMode, points: Point[]) => Promise<boolean>;
  onCancel: () => void;
  searchPoint: Point | null;
  mapRef: Ref<MapHandle>;
};

export default function OpenStreetMapView({ state, mode, locked, onPick, onDrawComplete, onCancel, searchPoint, mapRef: externalRef }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const modeRef = useRef(mode);
  const missionRef = useRef(state.mission.mission_id);
  const onPickRef = useRef(onPick);
  const lastMission = useRef("");
  const [ready, setReady] = useState(false);
  const [tileError, setTileError] = useState(false);
  const [draft, setDraft] = useState<{ mode: MapMode; mission: string; points: Point[] }>({ mode: "browse", mission: "", points: [] });
  const [hover, setHover] = useState<Point | null>(null);

  useEffect(() => { modeRef.current = mode; onPickRef.current = onPick; missionRef.current = state.mission.mission_id; }, [mode, onPick, state.mission.mission_id]);

  useEffect(() => {
    if (!container.current) return;
    const map = new maplibregl.Map({
      container: container.current,
      style: {
        version: 8,
        sources: {
          osm: {
            type: "raster",
            tiles: [import.meta.env.VITE_OSM_TILE_URL || "https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256, maxzoom: 19,
            attribution: import.meta.env.VITE_OSM_TILE_ATTRIBUTION || '<a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">© OpenStreetMap contributors</a>',
          },
        },
        layers: [{ id: "osm", type: "raster", source: "osm" }],
      },
      center: [-122.0825, 37.4235], zoom: 14, maxZoom: 19,
      canvasContextAttributes: { preserveDrawingBuffer: true },
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.on("error", (event) => { if ("sourceId" in event && event.sourceId === "osm") setTileError(true); });
    map.on("mousemove", (event) => setHover([event.lngLat.lng, event.lngLat.lat]));
    const clearHover = () => setHover(null);
    map.getCanvas().addEventListener("mouseleave", clearHover);
    map.on("click", (event) => {
      const point: Point = [event.lngLat.lng, event.lngLat.lat];
      if (modeRef.current === "pick") onPickRef.current(point);
      if (["area", "zone", "route", "event_zone"].includes(modeRef.current)) {
        setDraft((previous) => ({
          mode: modeRef.current, mission: missionRef.current,
          points: previous.mode === modeRef.current && previous.mission === missionRef.current
            ? [...previous.points, point] : [point],
        }));
      }
    });
    map.on("load", () => {
      for (const id of ["geofence", "zones", "route", "waypoints", "drone", "draft-line", "draft-points", "findings", "search"]) {
        map.addSource(id, { type: "geojson", data: emptyCollection });
      }
      map.addLayer({ id: "geofence-fill", type: "fill", source: "geofence", paint: { "fill-color": "#15803d", "fill-opacity": 0.12 } });
      map.addLayer({ id: "geofence-line", type: "line", source: "geofence", paint: { "line-color": "#15803d", "line-width": 2, "line-dasharray": [3, 2] } });
      map.addLayer({ id: "zone-fill", type: "fill", source: "zones", paint: { "fill-color": zoneColorExpression, "fill-opacity": 0.32 } });
      map.addLayer({ id: "zone-line", type: "line", source: "zones", paint: { "line-color": zoneColorExpression, "line-width": 2 } });
      map.addLayer({ id: "finding-line", type: "line", source: "findings", paint: { "line-color": ["match", ["get", "source"], "local_vision", "#fb923c", "#facc15"], "line-width": 2, "line-dasharray": [2, 2] } });
      map.addLayer({ id: "route-shadow", type: "line", source: "route", paint: { "line-color": "#064e3b", "line-width": 5 } });
      map.addLayer({ id: "route-line", type: "line", source: "route", paint: { "line-color": "#a7f3d0", "line-width": 2.5 } });
      map.addLayer({ id: "waypoint-circles", type: "circle", source: "waypoints", paint: { "circle-radius": 5, "circle-color": "#064e3b", "circle-stroke-color": "#d1fae5", "circle-stroke-width": 2 } });
      map.addLayer({ id: "waypoint-labels", type: "symbol", source: "waypoints", layout: { "text-field": ["get", "label"], "text-size": 12, "text-offset": [0, -1.4] }, paint: { "text-color": "#064e3b", "text-halo-color": "#ffffff", "text-halo-width": 2 } });
      map.addLayer({ id: "drone-circle", type: "circle", source: "drone", paint: { "circle-radius": 9, "circle-color": "#fef08a", "circle-stroke-color": "#1e293b", "circle-stroke-width": 3 } });
      map.addLayer({ id: "search-circle", type: "circle", source: "search", paint: { "circle-radius": 9, "circle-color": "#2563eb", "circle-stroke-color": "#fff", "circle-stroke-width": 3 } });
      map.addLayer({ id: "draft-line-layer", type: "line", source: "draft-line", paint: { "line-color": "#facc15", "line-width": 3, "line-dasharray": [2, 1] } });
      map.addLayer({ id: "draft-point-layer", type: "circle", source: "draft-points", paint: { "circle-radius": 5, "circle-color": "#facc15", "circle-stroke-color": "#111827", "circle-stroke-width": 2 } });
      setReady(true);
    });
    return () => { map.getCanvas().removeEventListener("mouseleave", clearHover); map.remove(); mapRef.current = null; };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const moveEnabled = !locked && mode === "browse";
    if (moveEnabled) { map.dragPan.enable(); map.scrollZoom.enable(); map.doubleClickZoom.enable(); }
    else { map.dragPan.disable(); map.scrollZoom.disable(); map.doubleClickZoom.disable(); }
    map.getCanvas().style.cursor = mode === "browse" ? (locked ? "default" : "grab") : "crosshair";
  }, [locked, mode]);

  useEffect(() => {
    if (!externalRef || typeof externalRef === "function") return;
    externalRef.current = {
      visibleArea: () => {
        const map = mapRef.current;
        if (!map) return null;
        const bounds = map.getBounds();
        return [[bounds.getWest(), bounds.getSouth()], [bounds.getEast(), bounds.getSouth()],
                [bounds.getEast(), bounds.getNorth()], [bounds.getWest(), bounds.getNorth()]];
      },
      capture: async () => {
        const map = mapRef.current;
        if (!map) return null;
        if (!map.areTilesLoaded()) {
          await new Promise<void>((resolve, reject) => {
            const timeout = window.setTimeout(() => {
              map.off("idle", done);
              reject(new Error("Map tiles are still loading. Retry when the map is visible."));
            }, 12000);
            const done = () => { window.clearTimeout(timeout); resolve(); };
            map.once("idle", done);
          });
        }
        const image = map.getCanvas().toDataURL("image/png");
        const bounds = map.getBounds();
        return {
          image_base64: image.split(",")[1],
          bounds: [bounds.getWest(), bounds.getSouth(), bounds.getEast(), bounds.getNorth()],
        };
      },
      goTo: (point, zoom) => {
        mapRef.current?.flyTo({ center: point, zoom, duration: 350 });
      },
    };
    return () => { externalRef.current = null; };
  }, [externalRef]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    const fence = state.world.geofence_boundary.coordinates[0] || [];
    const route = state.plan.waypoints.map((point) => [point.longitude, point.latitude] as Point);
    setSource(map, "geofence", polygons([{ coordinates: state.world.geofence_boundary.coordinates }]));
    setSource(map, "zones", polygons((state.world.zones ?? []).filter((zone) => zone.active).map((zone) => ({
      coordinates: zone.boundary.coordinates, properties: { zone_type: zone.zone_type, name: zone.name },
    }))));
    setSource(map, "route", line(route));
    setSource(map, "waypoints", dots(route));
    setSource(map, "drone", dots([state.drone.location]));
    setSource(map, "search", dots(searchPoint ? [searchPoint] : []));
    setSource(map, "findings", polygons([...(state.map_findings ?? []), ...(state.vision_findings ?? [])].map((finding) => ({
      coordinates: [finding.coordinates], properties: { kind: finding.kind, label: finding.label, source: finding.source || "osm" },
    }))));
    const missionKey = `${state.scenario}:${state.mission.mission_id}`;
    if (lastMission.current !== missionKey) {
      lastMission.current = missionKey;
      const points = [...fence, ...route, state.drone.location];
      if (points.length > 0) {
        const west = Math.min(...points.map((point) => point[0]));
        const east = Math.max(...points.map((point) => point[0]));
        const south = Math.min(...points.map((point) => point[1]));
        const north = Math.max(...points.map((point) => point[1]));
        map.fitBounds([[west, south], [east, north]] as LngLatBoundsLike, { padding: 48, duration: 0, maxZoom: 19 });
      }
    }
  }, [ready, state, searchPoint]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    const visible = draft.mode === mode && draft.mission === state.mission.mission_id ? draft.points : [];
    setSource(map, "draft-line", line(visible));
    setSource(map, "draft-points", dots(visible));
  }, [ready, draft, mode, state.mission.mission_id]);

  const drawing = ["area", "zone", "route", "event_zone"].includes(mode);
  const visibleDraft = draft.mode === mode && draft.mission === state.mission.mission_id ? draft.points : [];
  const canFinish = visibleDraft.length >= (mode === "route" ? 2 : 3);
  const finish = async () => {
    if (!canFinish) return;
    if (await onDrawComplete(mode, visibleDraft)) setDraft({ mode: "browse", mission: "", points: [] });
  };

  return <div className="map">
    <div className="map-title"><span>OPENSTREETMAP · SURVEY SECTOR</span><span>{locked ? "AREA LOCKED" : "BROWSE MAP"} · WGS84</span></div>
    <div className="map-stage">
      <div className="map-canvas" ref={container} role="region" aria-label="OpenStreetMap basemap with simulated geofence, zones, planned route and drone position" />
      {locked && <div className="map-hover">{hover ? `LAT ${hover[1].toFixed(6)}° · LON ${hover[0].toFixed(6)}°` : "Hover for latitude and longitude"}</div>}
      {drawing && <div className="map-draw-controls"><span>{mode === "route" ? "Click route waypoints" : "Click polygon vertices"} · {visibleDraft.length} selected</span><button type="button" onClick={() => setDraft({ mode, mission: state.mission.mission_id, points: visibleDraft.slice(0, -1) })} disabled={!visibleDraft.length}>Undo</button><button type="button" onClick={() => void finish()} disabled={!canFinish}>Finish drawing</button><button type="button" onClick={() => { setDraft({ mode: "browse", mission: "", points: [] }); onCancel(); }}>Cancel</button></div>}
      {mode === "pick" && <div className="map-draw-controls"><span>Click a location to use its map coordinate</span><button type="button" onClick={onCancel}>Cancel</button></div>}
    </div>
    {tileError && <div className="map-warning" role="status">Map tiles are unavailable. Coordinates and mission overlays are still accessible.</div>}
    <div className="legend"><span><i className="green" /> Planned route</span><span><i className="red" /> Restricted / no-fly</span><span><i className="light" /> Drone</span><span>© OpenStreetMap contributors · simulation only</span></div>
    <details className="map-coordinates"><summary>Mission coordinates</summary><p>Drone: {state.drone.location[1].toFixed(6)}°, {state.drone.location[0].toFixed(6)}°</p><p>Waypoints: {state.plan.waypoints.map((point, index) => `${index + 1}: ${point.latitude.toFixed(6)}°, ${point.longitude.toFixed(6)}°`).join(" · ")}</p></details>
  </div>;
}
