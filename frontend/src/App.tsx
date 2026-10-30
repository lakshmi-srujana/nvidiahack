import { useCallback, useEffect, useRef, useState } from "react";
import { Activity, AlertTriangle, CheckCircle2, Compass, Play, RefreshCw, Shield, Sparkles } from "lucide-react";
import OpenStreetMapView, { type MapFinding, type MapHandle, type MapMode, type MapState, type MapZone, type Point, type ZoneKind } from "./components/OpenStreetMapView";
import "./App.css";

type State = MapState & {
  title: string; status: string;
  world: MapState["world"] & { wind_speed_mps: number };
  drone: MapState["drone"] & { battery_pct: number; altitude_agl_m: number; sim_time_s: number; current_waypoint_index: number };
  mission: MapState["mission"] & { operator_instruction: string };
  plan: MapState["plan"] & { plan_id: string; revision: number; provenance: { planner_type: string }; waypoints: { longitude: number; latitude: number; altitude_agl_m: number; speed_mps: number }[] };
  verdict: { passed: boolean; checks: { rule_id: string; name: string; passed: boolean; message: string }[]; violations: { rule_id: string; message: string; remediation?: string }[] } | null;
  certificate: { certificate_id: string; plan_digest: string } | null;
  replan_attempts: number;
  events: { event_id: string; event_type: string; sim_time_s: number; payload: Record<string, unknown> }[];
  map_analysis: { source: string; retrieved_at: string; count: number; note: string } | null;
  vision_analysis?: { source: string; model: string; retrieved_at: string; count: number; note: string } | null;
};
type LocationResult = {
  label: string; latitude: number; longitude: number;
  bounds: [number, number, number, number]; osm_type?: string; osm_id?: number;
};

const scenarios = [
  ["flood", "Flash flood · nominal"], ["dam", "Dam breach · restricted zone"],
  ["wind", "High wind"], ["battery", "Low battery"],
];
const events = [
  ["SURVIVOR_DETECTED", "Survivor detected"], ["LOW_BATTERY", "Low battery"],
  ["WIND_SPIKE", "Wind spike"], ["NEW_RESTRICTED_ZONE", "New restricted zone"],
  ["OPERATOR_MISSION_CHANGE", "Operator change"],
];
const zoneOptions: [ZoneKind, string, string][] = [
  ["restricted", "Restricted zone", "#dc2626"], ["planned", "Planned zone", "#2563eb"],
  ["no_man", "No-man zone", "#a21caf"], ["no_fly", "No-fly zone", "#b91c1c"],
  ["destination_drop", "Destination / drop zone", "#f97316"], ["pickup", "Pickup zone", "#0d9488"],
  ["safe", "Safe zone", "#16a34a"], ["unknown", "Unknown territory", "#64748b"],
];
const zoneLabel = (kind: ZoneKind) => zoneOptions.find(([value]) => value === kind)?.[1] || kind;
const zoneColor = (kind: ZoneKind) => zoneOptions.find(([value]) => value === kind)?.[2] || "#64748b";

async function request(path: string, body?: unknown, method?: "POST" | "DELETE"): Promise<State> {
  const response = await fetch(`/api/v1/demo${path}`, body === undefined && !method ? undefined : {
    method: method || "POST", headers: { "Content-Type": "application/json" },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  const data = await response.json();
  if (!response.ok) {
    const detail = data.detail;
    throw new Error(typeof detail === "string" ? detail : Array.isArray(detail) ? detail.map((part) => part.msg).join("; ") : "The backend request failed.");
  }
  if (data.operation_status && data.operation_status !== "VERIFIED") throw new Error(data.error || `Planning ended with ${data.operation_status}.`);
  return data.state || data;
}

export default function App() {
  const [state, setState] = useState<State | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState<MapMode>("browse");
  const [locked, setLocked] = useState(false);
  const [instruction, setInstruction] = useState("Survey the selected area");
  const [zoneType, setZoneType] = useState<ZoneKind>("restricted");
  const [zoneName, setZoneName] = useState("");
  const [event, setEvent] = useState(events[0][0]);
  const [picked, setPicked] = useState<Point | null>(null);
  const [locationQuery, setLocationQuery] = useState("");
  const [locationResults, setLocationResults] = useState<LocationResult[]>([]);
  const [locationSearched, setLocationSearched] = useState(false);
  const [locationBusy, setLocationBusy] = useState(false);
  const [searchPoint, setSearchPoint] = useState<Point | null>(null);
  const mapRef = useRef<MapHandle>(null);
  const mutationEpoch = useRef(0);
  const tickPending = useRef(false);

  const perform = useCallback(async (path: string, body?: unknown, method?: "POST" | "DELETE") => {
    mutationEpoch.current += 1;
    setBusy(true); setError("");
    try { setState(await request(path, body, method)); return true; }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Request failed"); return false; }
    finally { setBusy(false); }
  }, []);

  useEffect(() => {
    let active = true;
    void request("/state").then((initial) => {
      if (active) { setState(initial); setLocked(initial.scenario === "custom"); }
    }).catch((cause: unknown) => {
      if (active) setError(cause instanceof Error ? cause.message : "Request failed");
    });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (state?.status !== "ACTIVE") return;
    let active = true;
    const timer = window.setInterval(() => {
      if (tickPending.current || busy) return;
      tickPending.current = true;
      const epoch = mutationEpoch.current;
      void request("/tick", {}).then((next) => {
        if (active && epoch === mutationEpoch.current) setState(next);
      }).catch((cause: unknown) => {
        if (active && epoch === mutationEpoch.current) setError(cause instanceof Error ? cause.message : "Simulation tick failed");
      }).finally(() => { tickPending.current = false; });
    }, 1000);
    return () => { active = false; window.clearInterval(timer); };
  }, [state?.status, busy]);

  const saveArea = async (points: Point[]) => {
    const ok = await perform("/survey", { instruction, coordinates: points });
    if (ok) { setLocked(true); setMode("browse"); setPicked(null); }
    return ok;
  };
  const saveZone = async (points: Point[], source: "operator" | "osm_confirmed" = "operator", label?: string) => {
    const ok = await perform("/zones", { name: label || zoneName.trim() || zoneLabel(zoneType), zone_type: zoneType, coordinates: points, source });
    if (ok) { setMode("browse"); setZoneName(""); }
    return ok;
  };
  const onDrawComplete = async (drawingMode: MapMode, points: Point[]) => {
    if (drawingMode === "area") return saveArea(points);
    if (drawingMode === "zone") return saveZone(points);
    if (drawingMode === "route") {
      const ok = await perform("/route/manual", { coordinates: points });
      if (ok) setMode("browse");
      return ok;
    }
    if (drawingMode === "event_zone") {
      const ok = await perform("/event", { family: "NEW_RESTRICTED_ZONE", zone_coordinates: points });
      if (ok) setMode("browse");
      return ok;
    }
    return false;
  };
  const lockVisibleArea = async () => {
    const points = mapRef.current?.visibleArea();
    if (!points) { setError("The map is still loading."); return; }
    await saveArea(points);
  };
  const searchLocation = async () => {
    const query = locationQuery.trim();
    if (query.length < 3) { setError("Enter an address or six-digit Indian PIN code."); return; }
    setLocationBusy(true); setError(""); setLocationSearched(false);
    try {
      const response = await fetch(`/api/v1/demo/location/search?q=${encodeURIComponent(query)}`);
      const body = await response.json();
      if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : "Address lookup failed");
      setLocationResults(body.results || []);
      setLocationSearched(true);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Address lookup failed");
    } finally { setLocationBusy(false); }
  };
  const chooseLocation = (result: LocationResult) => {
    const point: Point = [result.longitude, result.latitude];
    setSearchPoint(point);
    setLocked(false);
    setMode("browse");
    mapRef.current?.goTo(point, /^[1-9][0-9]{5}$/.test(locationQuery.trim()) ? 14 : 16);
  };
  const runLocalVision = async () => {
    try {
      const capture = await mapRef.current?.capture();
      if (!capture?.image_base64) throw new Error("The map image is not ready. Wait for the tiles and retry.");
      await perform("/vision/local", capture);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not capture the map image");
    }
  };
  const verifyAndStart = async () => {
    mutationEpoch.current += 1;
    setBusy(true); setError("");
    try {
      const verified = await request("/verify", {});
      setState(verified);
      if (verified.certificate) setState(await request("/launch", {}));
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Verification failed"); }
    finally { setBusy(false); }
  };
  const injectEvent = async () => {
    if (event === "NEW_RESTRICTED_ZONE") { setMode("event_zone"); return; }
    const ok = await perform("/event", { family: event, ...(event === "SURVIVOR_DETECTED" && picked ? { location: picked } : {}) });
    if (ok) setPicked(null);
  };
  const changeScenario = async (name: string) => {
    if (await perform(`/scenario/${name}`, {})) { setLocked(false); setMode("browse"); setPicked(null); }
  };
  const findings = [...(state?.map_findings || []), ...(state?.vision_findings || [])];

  return <main>
    <header><div className="brand"><div className="brand-icon"><Compass size={22}/></div><div><strong>SKYWARDEN</strong><small>MISSION CONTROL / PROTOTYPE</small></div></div><div className="header-right"><span className="online-dot" /> {state ? "BACKEND CONNECTED" : "CONNECTING"} <span className="version">SIMULATION ONLY</span></div></header>
    <div className="shell">
      <div className="page-head"><div><p className="eyebrow">OPERATIONS / SINGLE DRONE</p><h1>Survey mission control<span>.</span></h1><p>Choose real map coordinates, review zones, verify a route and observe its simulation.</p></div><div className="status-pill"><span /> {state?.status.replaceAll("_", " ") || "OFFLINE"}</div></div>
      {error && <div className="error" role="alert"><AlertTriangle size={18} /> {error}<button onClick={() => setError("")}>Dismiss</button></div>}
      {!state ? <div className="empty"><RefreshCw size={22} /> Start the backend to connect the dashboard.</div> : <div className="layout">
        <section className="main-column">
          <div className="section-heading"><div><p className="eyebrow">01 / MAP</p><h2>{state.title}</h2></div><span className="subtle">{state.mission.mission_id}</span></div>
          <OpenStreetMapView state={state} mode={mode} locked={locked} searchPoint={searchPoint} mapRef={mapRef} onPick={(point) => { setPicked(point); setMode("browse"); }} onDrawComplete={onDrawComplete} onCancel={() => setMode("browse")} />
          <div className="metrics">
            <div><small>BATTERY</small><strong>{state.drone.battery_pct.toFixed(1)}<em>%</em></strong><span>Simulated remaining</span></div>
            <div><small>ALTITUDE</small><strong>{state.drone.altitude_agl_m.toFixed(1)}<em>m AGL</em></strong><span>Above ground level</span></div>
            <div><small>WIND</small><strong>{state.world.wind_speed_mps.toFixed(1)}<em>m/s</em></strong><span>Scenario conditions</span></div>
            <div><small>MISSION TIME</small><strong>{Math.round(state.drone.sim_time_s)}<em>sec</em></strong><span>Simulation clock</span></div>
          </div>
          <div className="panel timeline"><div className="section-heading"><div><p className="eyebrow">05 / ACTIVITY</p><h2>Event timeline</h2></div><Activity size={19} /></div>
            {state.events.length === 0 ? <p className="muted">Events will appear here as the simulation progresses.</p> : <div className="event-list">{[...state.events].reverse().slice(0, 12).map((item) => <div className="event" key={item.event_id}><span className="event-dot" /><div><strong>{item.event_type.replaceAll("_", " ")}</strong><small>{item.event_id} · {item.sim_time_s.toFixed(0)}s</small></div></div>)}</div>}
          </div>
        </section>
        <aside>
          <div className="panel controls"><p className="eyebrow">02 / SELECT AREA</p><h2>Lock a map area</h2><p className="muted">Pan and zoom to a real location, then lock the visible area or draw a polygon. Coordinates come from the map.</p>
            <form className="location-search" onSubmit={(event) => { event.preventDefault(); void searchLocation(); }}>
              <label htmlFor="location-query">Address or Indian PIN code</label>
              <input id="location-query" value={locationQuery} onChange={(event) => setLocationQuery(event.target.value)} placeholder="Enter an address or 6-digit PIN" />
              <button type="submit" className="secondary" disabled={locationBusy || state.status === "ACTIVE"}>{locationBusy ? "Searching…" : "Find on map"}</button>
            </form>
            {locationSearched && locationResults.length === 0 && <p className="hint">No matching location found. Add a city or state and try again.</p>}
            {locationResults.length > 0 && <div className="location-results">{locationResults.map((result, index) => <button key={`${result.osm_type}-${result.osm_id}-${index}`} type="button" className="ghost" disabled={state.status === "ACTIVE"} onClick={() => chooseLocation(result)}><strong>{result.label}</strong><small>{result.latitude.toFixed(6)}°, {result.longitude.toFixed(6)}°</small></button>)}</div>}
            <p className="hint">Search runs only when submitted through OpenStreetMap Nominatim. Do not enter confidential addresses. Select a result, adjust the map, then lock the area.</p>
            <label htmlFor="scenario">Seeded scenario</label><select id="scenario" value={state.scenario} disabled={busy || state.status === "ACTIVE"} onChange={(event) => void changeScenario(event.target.value)}>{state.scenario === "custom" && <option value="custom">Map-selected area</option>}{scenarios.map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select>
            <label htmlFor="instruction">Survey instruction</label><input id="instruction" value={instruction} onChange={(event) => setInstruction(event.target.value)} />
            <div className="map-tools"><button className="secondary" disabled={busy || state.status === "ACTIVE" || locked} onClick={() => void lockVisibleArea()}>Lock visible area</button><button className="secondary" disabled={busy || state.status === "ACTIVE" || locked} onClick={() => setMode("area")}>Draw survey polygon</button></div>
            {locked && <button className="ghost" disabled={busy || state.status === "ACTIVE"} onClick={() => { setLocked(false); setMode("browse"); }}>Explore another area</button>}
            <p className="hint">{locked ? "Area locked. Hover over the map to read WGS84 coordinates; click a drawing tool to edit." : "Map movement stays available until you lock an area."}</p>
          </div>
          <div className="panel controls"><p className="eyebrow">03 / MAP FEATURES & ZONES</p><h2>Review geographic features</h2><p className="muted">OpenStreetMap tags and optional local image review suggest buildings, water and utility sites. Review suggestions before flight restrictions.</p>
            <button className="secondary" disabled={busy || state.status === "ACTIVE" || !locked} onClick={() => void perform("/analyze-map", {})}>Find mapped features · no AI credits</button>
            {state.map_analysis && <p className="hint">{state.map_analysis.count} mapped features · {state.map_analysis.source} · {new Date(state.map_analysis.retrieved_at).toLocaleString()}</p>}
            <button className="secondary" disabled={busy || state.status === "ACTIVE" || !locked} onClick={() => void runLocalVision()}>Review map image with local AI · no credits</button>
            {state.vision_analysis && <p className="hint">{state.vision_analysis.count} image suggestions · {state.vision_analysis.model} · {new Date(state.vision_analysis.retrieved_at).toLocaleString()}</p>}
            <button className="secondary" disabled={busy || state.status === "ACTIVE" || findings.length === 0} onClick={() => void perform("/zones/auto", {})}>Draft zones from suggestions</button>
            <p className="hint">Suggested buildings become planned zones, water becomes unknown territory, and marked utility hazards become restricted zones. Remove or redraw any draft before verification.</p>
            <label htmlFor="zone-type">Zone type</label><select id="zone-type" value={zoneType} onChange={(event) => setZoneType(event.target.value as ZoneKind)}>{zoneOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
            <label htmlFor="zone-name">Zone name</label><input id="zone-name" value={zoneName} onChange={(event) => setZoneName(event.target.value)} placeholder="Optional name" />
            <button className="secondary" disabled={busy || state.status === "ACTIVE" || !locked} onClick={() => setMode("zone")}>Draw {zoneLabel(zoneType).toLowerCase()}</button>
            <div className="zone-list">{(state.world.zones ?? []).map((zone: MapZone) => <div className="zone-row" key={zone.zone_id}><i className="zone-swatch" style={{ background: zoneColor(zone.zone_type) }} /><strong>{zone.name}</strong><span>{zoneLabel(zone.zone_type)}</span>{zone.source !== "seeded" && <button className="ghost" disabled={busy || state.status === "ACTIVE"} onClick={() => void perform(`/zones/${zone.zone_id}`, undefined, "DELETE")}>Remove</button>}</div>)}</div>
            {findings.length > 0 && <div className="analysis-list">{findings.slice(0, 24).map((finding: MapFinding, index: number) => <div className="analysis-item" key={`${finding.osm_id ?? "vision"}-${finding.kind}-${index}`}><strong>{finding.label}</strong><small>{finding.kind.replaceAll("_", " ")} · {finding.source_url ? <a href={finding.source_url} target="_blank" rel="noreferrer">OSM way {finding.osm_id}</a> : `Local vision suggestion · ${finding.model || "Ollama"}`}</small><button className="secondary" disabled={busy || state.status === "ACTIVE"} onClick={() => void saveZone(finding.coordinates, finding.source_url ? "osm_confirmed" : "operator", finding.label)}>Use as {zoneLabel(zoneType).toLowerCase()}</button></div>)}{findings.length > 24 && <p className="hint">Showing 24 of {findings.length} suggestions. Select a smaller area for focused review.</p>}</div>}
          </div>
          <div className="panel controls"><p className="eyebrow">04 / ROUTE</p><h2>Design the path</h2><p className="muted">Click map waypoints for a manual path, or generate a geographic route around confirmed exclusion zones.</p>
            <button className="secondary" disabled={busy || state.status === "ACTIVE" || !locked} onClick={() => setMode("route")}>Draw manual route</button>
            <button className="secondary" disabled={busy || state.status === "ACTIVE" || !locked} onClick={() => void perform("/route/auto", {})}>Auto route · no AI credits</button>
            <button className="ghost" disabled={busy || state.status === "ACTIVE" || !locked} onClick={() => void perform("/route/ai", {})}><Sparkles size={16} /> AI route proposal <span>paid, opt-in</span></button>
            <p className="hint">Plan {state.plan.plan_id} · revision {state.plan.revision} · {state.plan.provenance.planner_type}. Every route needs safety verification.</p>
          </div>
          <div className="panel verification"><div className="section-heading"><div><p className="eyebrow">SAFETY GATE</p><h2>Verification</h2></div>{state.certificate ? <CheckCircle2 className="ok" size={20} /> : <Shield size={20} />}</div>
            {!state.verdict ? <p className="muted">Verify the current route before launching.</p> : <><div className={state.verdict.passed ? "result pass" : "result fail"}>{state.verdict.passed ? "All checks passed" : `${state.verdict.violations.length} violation(s) found`}</div>{state.certificate && <div className="certificate"><small>CERTIFICATE</small><strong>{state.certificate.certificate_id}</strong><code>{state.certificate.plan_digest.slice(0, 24)}…</code></div>}{state.verdict.violations.map((violation, index) => <div className="violation" key={index}><strong>{violation.rule_id}</strong><p>{violation.message}</p>{violation.remediation && <small>{violation.remediation}</small>}</div>)}<details><summary>View {state.verdict.checks.length} rule checks</summary>{state.verdict.checks.map((check) => <div className="check" key={check.rule_id}><span>{check.passed ? "✓" : "×"}</span>{check.name}</div>)}</details></>}
            <div className="controls"><button className="primary" disabled={busy || state.status === "ACTIVE"} onClick={() => void verifyAndStart()}><Play size={17} /> Verify & start simulation</button><button className="secondary" disabled={busy || state.status === "ACTIVE"} onClick={() => void perform("/verify", {})}><Shield size={17} /> Verify plan</button><button className="secondary" disabled={busy || state.status !== "CERTIFIED"} onClick={() => void perform("/launch", {})}>Launch simulation</button></div>
          </div>
          <div className="panel controls"><p className="eyebrow">LIVE SCENARIO</p><h2>Inject an event</h2><p className="muted">Events pause the simulation and revoke its certificate. Draw a new restricted zone on the map when selecting that event.</p>
            <select aria-label="Event family" value={event} onChange={(change) => setEvent(change.target.value)}>{events.map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select>
            {event === "SURVIVOR_DETECTED" && <><button className="secondary" disabled={busy || state.status !== "ACTIVE"} onClick={() => setMode("pick")}>Pick detection coordinate</button>{picked && <p className="picked-coordinate">Selected: {picked[1].toFixed(6)}°, {picked[0].toFixed(6)}°</p>}</>}
            <button className="secondary" disabled={busy || state.status !== "ACTIVE"} onClick={() => void injectEvent()}><AlertTriangle size={16} /> {event === "NEW_RESTRICTED_ZONE" ? "Draw & inject zone" : "Inject event"}</button>
            <button className="secondary" disabled={busy || !["INTERVENTION_REQUIRED", "REJECTED"].includes(state.status) || state.replan_attempts >= 3} onClick={() => void perform("/replan", {})}><RefreshCw size={16} /> Replan & verify ({state.replan_attempts}/3)</button>
            <p className="hint">Replanning is reverified. If it fails, draw a new safe route or request intervention.</p>
          </div>
        </aside>
      </div>}
      <footer>SKYWARDEN · DEMO SYSTEM <span>Simulation only. Map data and prototype safety thresholds are not real-flight authority.</span></footer>
    </div>
  </main>;
}
