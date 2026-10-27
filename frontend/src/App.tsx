import { useCallback, useEffect, useState } from "react";
import { Activity, AlertTriangle, CheckCircle2, Compass, Play, Radar, RefreshCw, Shield, Sparkles } from "lucide-react";
import "./App.css";

type Point = [number, number];
type State = {
  scenario: string; title: string; status: string;
  world: { geofence_boundary: { coordinates: Point[][] }; restricted_zones: { name: string; boundary: { coordinates: Point[][] }; active: boolean }[]; wind_speed_mps: number };
  drone: { location: Point; battery_pct: number; altitude_agl_m: number; sim_time_s: number; current_waypoint_index: number };
  mission: { operator_instruction: string; mission_id: string };
  plan: { plan_id: string; waypoints: { longitude: number; latitude: number; altitude_agl_m: number; speed_mps: number }[] };
  verdict: { passed: boolean; checks: { rule_id: string; name: string; passed: boolean; message: string }[]; violations: { rule_id: string; message: string; remediation?: string }[] } | null;
  certificate: { certificate_id: string; plan_digest: string } | null;
  replan_attempts: number;
  events: { event_id: string; event_type: string; sim_time_s: number; payload: Record<string, unknown> }[];
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

async function request(path: string, body?: unknown): Promise<State> {
  const response = await fetch(`/api/v1/demo${path}`, body === undefined ? undefined : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || "The backend request failed.");
  if (data.operation_status && data.operation_status !== "VERIFIED") {
    throw new Error(data.error || `AI planning ended with ${data.operation_status}.`);
  }
  return data.state || data;
}

function RouteMap({ state }: { state: State }) {
  const fence = state.world.geofence_boundary.coordinates[0];
  const all = [...fence, ...state.plan.waypoints.map((p) => [p.longitude, p.latitude] as Point), state.drone.location];
  const xs = all.map((p) => p[0]), ys = all.map((p) => p[1]);
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
  const project = ([x, y]: Point) => [30 + (x - minX) / (maxX - minX || 1) * 540, 330 - (y - minY) / (maxY - minY || 1) * 300];
  const line = (points: Point[]) => points.map((p) => project(p).join(",")).join(" ");
  const [dx, dy] = project(state.drone.location);
  return <div className="map">
    <div className="map-title"><span><Radar size={16} /> SURVEY SECTOR</span><span>WGS84 · SIMULATED</span></div>
    <svg viewBox="0 0 600 360" role="img" aria-label="Schematic geofence, restricted zones, planned route and simulated drone position">
      <defs><pattern id="grid" width="30" height="30" patternUnits="userSpaceOnUse"><path d="M 30 0 L 0 0 0 30" fill="none" stroke="#244542" strokeWidth="0.5" /></pattern></defs>
      <rect width="600" height="360" fill="url(#grid)" />
      <polygon points={line(fence)} fill="#1d544a55" stroke="#5ba68b" strokeDasharray="5 5" />
      {state.world.restricted_zones.filter((z) => z.active).map((z) => <polygon key={z.name} points={line(z.boundary.coordinates[0])} fill="#f8717130" stroke="#f87171" />)}
      <polyline points={line(state.plan.waypoints.map((p) => [p.longitude, p.latitude]))} fill="none" stroke="#a7f3c7" strokeWidth="3" />
      {state.plan.waypoints.map((p, i) => { const [x,y] = project([p.longitude,p.latitude]); return <g key={i}><circle cx={x} cy={y} r="5" fill="#a7f3c7" /><text x={x+8} y={y-8} fill="#dcefe6" fontSize="10">{i+1}</text></g>; })}
      <circle cx={dx} cy={dy} r="11" fill="#e5fbce33" /><circle cx={dx} cy={dy} r="5" fill="#e5fbce" stroke="#fff" />
    </svg>
    <div className="legend"><span><i className="green" /> Planned route</span><span><i className="red" /> Restricted zone</span><span><i className="light" /> Drone</span><span>Schematic view · not navigation</span></div>
  </div>;
}

export default function App() {
  const [state, setState] = useState<State | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [event, setEvent] = useState(events[0][0]);
  const [survey, setSurvey] = useState({ instruction: "Survey the approved area", west: "-122.0850", east: "-122.0830", south: "37.4215", north: "37.4235" });
  const perform = useCallback(async (path: string, body?: unknown) => {
    setBusy(true); setError("");
    try { setState(await request(path, body)); } catch (e) { setError(e instanceof Error ? e.message : "Request failed"); }
    finally { setBusy(false); }
  }, []);
  useEffect(() => { void perform("/state"); }, [perform]);
  useEffect(() => {
    if (state?.status !== "ACTIVE" || busy) return;
    const timer = window.setTimeout(() => void perform("/tick", {}), 1000);
    return () => window.clearTimeout(timer);
  }, [state, busy, perform]);

  return <main>
    <header><div className="brand"><div className="brand-icon"><Compass size={22}/></div><div><strong>SKYWARDEN</strong><small>MISSION CONTROL / PROTOTYPE</small></div></div><div className="header-right"><span className="online-dot" /> {state ? "BACKEND CONNECTED" : "CONNECTING"} <span className="version">SIMULATION ONLY</span></div></header>
    <div className="shell">
      <div className="page-head"><div><p className="eyebrow">OPERATIONS / SINGLE DRONE</p><h1>Survey mission control<span>.</span></h1><p>Plan, verify and observe a simulated disaster-survey mission.</p></div><div className="status-pill"><span /> {state?.status.replaceAll("_"," ") || "OFFLINE"}</div></div>
      {error && <div className="error" role="alert"><AlertTriangle size={18} /> {error}<button onClick={() => setError("")}>Dismiss</button></div>}
      {!state ? <div className="empty"><RefreshCw size={22} /> Start the backend to connect the dashboard.</div> : <>
      <div className="layout">
        <section className="main-column">
          <div className="section-heading"><div><p className="eyebrow">01 / MISSION VIEW</p><h2>{state.title}</h2></div><span className="subtle">{state.mission.mission_id}</span></div>
          <RouteMap state={state}/>
          <div className="metrics">
            <div><small>BATTERY</small><strong>{state.drone.battery_pct.toFixed(1)}<em>%</em></strong><span>Simulated remaining</span></div>
            <div><small>ALTITUDE</small><strong>{state.drone.altitude_agl_m.toFixed(1)}<em>m AGL</em></strong><span>Above ground level</span></div>
            <div><small>WIND</small><strong>{state.world.wind_speed_mps.toFixed(1)}<em>m/s</em></strong><span>Scenario conditions</span></div>
            <div><small>MISSION TIME</small><strong>{Math.round(state.drone.sim_time_s)}<em>sec</em></strong><span>Simulation clock</span></div>
          </div>
          <div className="panel timeline"><div className="section-heading"><div><p className="eyebrow">03 / ACTIVITY</p><h2>Event timeline</h2></div><Activity size={19} /></div>
            {state.events.length === 0 ? <p className="muted">Events will appear here as the simulation progresses.</p> : <div className="event-list">{[...state.events].reverse().slice(0, 12).map((e) => <div className="event" key={e.event_id}><span className="event-dot" /><div><strong>{e.event_type.replaceAll("_"," ")}</strong><small>{e.event_id} · {e.sim_time_s.toFixed(0)}s</small></div></div>)}</div>}
          </div>
        </section>
        <aside>
          <div className="panel controls"><p className="eyebrow">02 / MISSION SETUP</p><h2>Mission controls</h2><p className="muted">Choose a seeded scenario and verify its plan before launch.</p>
            <label htmlFor="scenario">Scenario</label><select id="scenario" value={state.scenario} disabled={busy || state.status === "ACTIVE"} onChange={(e) => void perform(`/scenario/${e.target.value}`, {})}>{state.scenario === "custom" && <option value="custom">Operator survey</option>}{scenarios.map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select>
            <p className="instruction">{state.mission.operator_instruction}</p>
            <details className="survey-form"><summary>Create a survey area</summary><label htmlFor="instruction">Survey instruction</label><input id="instruction" value={survey.instruction} onChange={(e) => setSurvey({...survey, instruction:e.target.value})} /><div className="coordinate-grid">{(["west", "east", "south", "north"] as const).map((field) => <label key={field}>{field.toUpperCase()}<input type="number" step="any" value={survey[field]} onChange={(e) => setSurvey({...survey, [field]:e.target.value})}/></label>)}</div><button className="secondary" disabled={busy || state.status === "ACTIVE"} onClick={() => void perform("/survey", {instruction:survey.instruction, west:Number(survey.west), east:Number(survey.east), south:Number(survey.south), north:Number(survey.north)})}>Create survey</button><p className="hint">Rectangle coordinates are longitude west/east and latitude south/north. Demo assumes no restricted zones.</p></details>
            <button className="primary" disabled={busy || state.status === "ACTIVE"} onClick={() => void perform("/verify", {})}><Shield size={17}/> Verify plan</button>
            <button className="secondary" disabled={busy || state.status !== "CERTIFIED"} onClick={() => void perform("/launch", {})}><Play size={17}/> Launch simulation</button>
            <button className="ghost" disabled={busy || state.status === "ACTIVE"} onClick={() => void perform("/ai-plan", {})}><Sparkles size={16}/> Generate AI proposal <span>paid request</span></button>
            <p className="hint">AI proposals require Nebius credentials and pass the same verifier. No automatic AI calls.</p>
          </div>
          <div className="panel verification"><div className="section-heading"><div><p className="eyebrow">SAFETY GATE</p><h2>Verification</h2></div>{state.certificate ? <CheckCircle2 className="ok" size={20}/> : <Shield size={20}/>}</div>
            {!state.verdict ? <p className="muted">Run verification to review the safety checks.</p> : <><div className={state.verdict.passed ? "result pass" : "result fail"}>{state.verdict.passed ? "All checks passed" : `${state.verdict.violations.length} violation(s) found`}</div>
            {state.certificate && <div className="certificate"><small>CERTIFICATE</small><strong>{state.certificate.certificate_id}</strong><code>{state.certificate.plan_digest.slice(0,24)}…</code></div>}
            {state.verdict.violations.map((v,i) => <div className="violation" key={i}><strong>{v.rule_id}</strong><p>{v.message}</p>{v.remediation && <small>{v.remediation}</small>}</div>)}
            <details><summary>View {state.verdict.checks.length} rule checks</summary>{state.verdict.checks.map((c) => <div className="check" key={c.rule_id}><span>{c.passed ? "✓" : "×"}</span>{c.name}</div>)}</details></>}
          </div>
          <div className="panel"><p className="eyebrow">LIVE SCENARIO</p><h2>Inject an event</h2><p className="muted">Events pause the simulation and require review before another launch.</p><select aria-label="Event family" value={event} onChange={(e) => setEvent(e.target.value)}>{events.map(([id,label]) => <option key={id} value={id}>{label}</option>)}</select><button className="secondary" disabled={busy || state.status !== "ACTIVE"} onClick={() => void perform("/event", {family:event})}><AlertTriangle size={16}/> Inject event</button><button className="secondary" disabled={busy || !["INTERVENTION_REQUIRED", "REJECTED"].includes(state.status) || state.replan_attempts >= 3} onClick={() => void perform("/replan", {})}><RefreshCw size={16}/> Replan & verify ({state.replan_attempts}/3)</button><p className="hint">Rechecks the remaining route; hazards that require a detour need operator intervention.</p></div>
        </aside>
      </div></>}
      <footer>SKYWARDEN · DEMO SYSTEM <span>Simulation only. Safety thresholds are unapproved prototype assumptions.</span></footer>
    </div>
  </main>;
}
