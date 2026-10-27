import React, { useState, useRef, useMemo } from "react";
import type {
  Mission,
  Plan,
  WorldState,
  DroneState,
  Coordinate,
} from "../contracts/contracts";
import {
  ZoomIn,
  ZoomOut,
  Crosshair,
  Compass,
  UserCheck,
} from "lucide-react";

interface TacticalMapProps {
  mission: Mission;
  plan: Plan | null;
  world: WorldState;
  drone: DroneState;
  survivorLocation: Coordinate | null;
  breadcrumbs: Coordinate[];
}

export const TacticalMap: React.FC<TacticalMapProps> = ({
  mission,
  plan,
  world,
  drone,
  survivorLocation,
  breadcrumbs,
}) => {
  const [zoom, setZoom] = useState<number>(1);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [cursorCoord, setCursorCoord] = useState<{ lon: number; lat: number } | null>(null);

  // Layer toggles
  const [showGeofence, setShowGeofence] = useState(true);
  const [showRestricted, setShowRestricted] = useState(true);
  const [showWaypoints, setShowWaypoints] = useState(true);
  const [showBreadcrumbs, setShowBreadcrumbs] = useState(true);
  const [showSensorCone, setShowSensorCone] = useState(true);

  const svgRef = useRef<SVGSVGElement | null>(null);

  // Coordinate projection bounds centered around Googleplex / Mountain View test sector
  const BASE_BOUNDS = useMemo(() => {
    return {
      minLon: -122.092,
      maxLon: -122.074,
      minLat: 37.419,
      maxLat: 37.431,
    };
  }, []);

  const SVG_WIDTH = 900;
  const SVG_HEIGHT = 650;

  // Project (lon, lat) to SVG (x, y)
  const project = (lon: number, lat: number): [number, number] => {
    const lonRange = BASE_BOUNDS.maxLon - BASE_BOUNDS.minLon;
    const latRange = BASE_BOUNDS.maxLat - BASE_BOUNDS.minLat;

    const normX = (lon - BASE_BOUNDS.minLon) / lonRange;
    const normY = (lat - BASE_BOUNDS.minLat) / latRange;

    // Invert Y because SVG y goes downwards
    const x = normX * SVG_WIDTH;
    const y = (1.0 - normY) * SVG_HEIGHT;
    return [x, y];
  };

  // Inverse project SVG (x, y) to (lon, lat)
  const inverseProject = (x: number, y: number): { lon: number; lat: number } => {
    const lonRange = BASE_BOUNDS.maxLon - BASE_BOUNDS.minLon;
    const latRange = BASE_BOUNDS.maxLat - BASE_BOUNDS.minLat;

    const normX = x / SVG_WIDTH;
    const normY = 1.0 - y / SVG_HEIGHT;

    return {
      lon: BASE_BOUNDS.minLon + normX * lonRange,
      lat: BASE_BOUNDS.minLat + normY * latRange,
    };
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isDragging) {
      setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
    }
    if (svgRef.current) {
      const rect = svgRef.current.getBoundingClientRect();
      const localX = (e.clientX - rect.left - pan.x) / zoom;
      const localY = (e.clientY - rect.top - pan.y) / zoom;
      setCursorCoord(inverseProject(localX, localY));
    }
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  // Convert GeoPolygon coordinates to SVG polygon points string
  const polygonToSvgPoints = (coords: Coordinate[]): string => {
    return coords.map((c) => project(c[0], c[1]).join(",")).join(" ");
  };

  const droneSvgPos = project(drone.location[0], drone.location[1]);
  const homeSvgPos = project(drone.home_position[0], drone.home_position[1]);

  return (
    <div
      style={{
        position: "relative",
        width: "100%",
        height: "100%",
        minHeight: "560px",
        overflow: "hidden",
        backgroundColor: "#070c18",
        borderRadius: "12px",
        border: "1px solid rgba(0, 229, 255, 0.2)",
        boxShadow: "inset 0 0 40px rgba(0, 0, 0, 0.7)",
      }}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
    >
      {/* Tactical Grid Background */}
      <svg
        ref={svgRef}
        viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
        style={{
          width: "100%",
          height: "100%",
          cursor: isDragging ? "grabbing" : "crosshair",
          transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
          transformOrigin: "center center",
          transition: isDragging ? "none" : "transform 0.1s ease-out",
        }}
      >
        <defs>
          {/* Neon Survey Hatch */}
          <pattern id="survey-hatch" width="20" height="20" patternTransform="rotate(45 0 0)" patternUnits="userSpaceOnUse">
            <line x1="0" y1="0" x2="0" y2="20" stroke="rgba(0, 229, 255, 0.12)" strokeWidth="2" />
          </pattern>
          {/* Restricted Zone Warning Stripes */}
          <pattern id="hazard-stripes" width="16" height="16" patternTransform="rotate(45 0 0)" patternUnits="userSpaceOnUse">
            <line x1="0" y1="0" x2="0" y2="16" stroke="rgba(239, 68, 68, 0.35)" strokeWidth="4" />
          </pattern>
          {/* Radar Sweep Gradient */}
          <radialGradient id="sensor-gradient" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="rgba(0, 229, 255, 0.3)" />
            <stop offset="70%" stopColor="rgba(0, 229, 255, 0.08)" />
            <stop offset="100%" stopColor="rgba(0, 229, 255, 0.0)" />
          </radialGradient>
        </defs>

        {/* Coordinate Grid Lines */}
        <g stroke="rgba(255, 255, 255, 0.04)" strokeWidth="1">
          {Array.from({ length: 9 }).map((_, i) => (
            <line key={`vert-${i}`} x1={i * 100} y1="0" x2={i * 100} y2={SVG_HEIGHT} />
          ))}
          {Array.from({ length: 7 }).map((_, i) => (
            <line key={`horiz-${i}`} x1="0" y1={i * 100} x2={SVG_WIDTH} y2={i * 100} />
          ))}
        </g>

        {/* Geofence Boundary Layer */}
        {showGeofence && world.geofence_boundary.coordinates[0] && (
          <g>
            <polygon
              points={polygonToSvgPoints(world.geofence_boundary.coordinates[0])}
              fill="rgba(16, 185, 129, 0.02)"
              stroke="#10b981"
              strokeWidth="2"
              strokeDasharray="6,4"
            />
            <text
              x={project(world.geofence_boundary.coordinates[0][0][0], world.geofence_boundary.coordinates[0][0][1])[0] + 10}
              y={project(world.geofence_boundary.coordinates[0][0][0], world.geofence_boundary.coordinates[0][0][1])[1] - 8}
              fill="#10b981"
              fontSize="10"
              fontFamily="var(--font-mono)"
              letterSpacing="1"
            >
              [SAFE GEOFENCE ENVELOPE]
            </text>
          </g>
        )}

        {/* Survey Area Polygon */}
        {mission.survey_area.coordinates[0] && (
          <g>
            <polygon
              points={polygonToSvgPoints(mission.survey_area.coordinates[0])}
              fill="url(#survey-hatch)"
              stroke="#00e5ff"
              strokeWidth="2.5"
            />
            <text
              x={project(mission.survey_area.coordinates[0][0][0], mission.survey_area.coordinates[0][0][1])[0] + 12}
              y={project(mission.survey_area.coordinates[0][0][0], mission.survey_area.coordinates[0][0][1])[1] + 20}
              fill="#00e5ff"
              fontSize="11"
              fontWeight="700"
              fontFamily="var(--font-mono)"
            >
              TARGET SURVEY SECTOR ALPHA
            </text>
          </g>
        )}

        {/* Restricted / Hazard Zones Layer */}
        {showRestricted &&
          world.restricted_zones
            .filter((z) => z.active)
            .map((zone) => {
              const pts = polygonToSvgPoints(zone.boundary.coordinates[0]);
              const firstPt = project(zone.boundary.coordinates[0][0][0], zone.boundary.coordinates[0][0][1]);
              return (
                <g key={zone.zone_id}>
                  {/* Buffer halo */}
                  <polygon
                    points={pts}
                    fill="none"
                    stroke="rgba(245, 158, 11, 0.4)"
                    strokeWidth="14"
                    strokeLinejoin="round"
                  />
                  {/* Danger Zone Fill */}
                  <polygon
                    points={pts}
                    fill="url(#hazard-stripes)"
                    stroke="#ef4444"
                    strokeWidth="2"
                  />
                  <text
                    x={firstPt[0] + 8}
                    y={firstPt[1] + 16}
                    fill="#ef4444"
                    fontSize="10"
                    fontWeight="700"
                    fontFamily="var(--font-mono)"
                  >
                    ⚠️ {zone.name.toUpperCase()} (BUFFER: {zone.buffer_m}m)
                  </text>
                </g>
              );
            })}

        {/* Flight Path Breadcrumbs Trail */}
        {showBreadcrumbs && breadcrumbs.length > 1 && (
          <polyline
            points={breadcrumbs.map((c) => project(c[0], c[1]).join(",")).join(" ")}
            fill="none"
            stroke="rgba(0, 229, 255, 0.3)"
            strokeWidth="2"
            strokeDasharray="2,3"
          />
        )}

        {/* Planned Flight Route Segments */}
        {plan && plan.waypoints.length > 1 && (
          <g>
            <polyline
              points={plan.waypoints.map((wp) => project(wp.longitude, wp.latitude).join(",")).join(" ")}
              fill="none"
              stroke="#00e5ff"
              strokeWidth="2.5"
              strokeLinejoin="round"
            />
            {/* Directional Segment Chevrons */}
            {plan.waypoints.slice(0, -1).map((w1, idx) => {
              const w2 = plan.waypoints[idx + 1];
              const p1 = project(w1.longitude, w1.latitude);
              const p2 = project(w2.longitude, w2.latitude);
              const midX = (p1[0] + p2[0]) / 2;
              const midY = (p1[1] + p2[1]) / 2;
              const angle = Math.atan2(p2[1] - p1[1], p2[0] - p1[0]) * (180 / Math.PI);
              return (
                <polygon
                  key={`arrow-${idx}`}
                  points="-5,-4 5,0 -5,4"
                  fill="#00e5ff"
                  transform={`translate(${midX}, ${midY}) rotate(${angle})`}
                />
              );
            })}
          </g>
        )}

        {/* Planned Waypoints Layer */}
        {showWaypoints &&
          plan &&
          plan.waypoints.map((wp, idx) => {
            const [x, y] = project(wp.longitude, wp.latitude);
            const isNext = idx === drone.current_waypoint_index;
            return (
              <g key={wp.waypoint_id} transform={`translate(${x}, ${y})`}>
                <circle
                  r={isNext ? 9 : 6}
                  fill={isNext ? "#00e5ff" : "#0f172a"}
                  stroke={isNext ? "#ffffff" : "#00e5ff"}
                  strokeWidth="2"
                />
                {isNext && (
                  <circle
                    r="15"
                    fill="none"
                    stroke="#00e5ff"
                    strokeWidth="1.5"
                    strokeDasharray="4,4"
                    opacity="0.8"
                  />
                )}
                <text
                  x="12"
                  y="4"
                  fill="#f8fafc"
                  fontSize="10"
                  fontFamily="var(--font-mono)"
                  fontWeight="600"
                >
                  {wp.waypoint_id} ({wp.altitude_agl_m}m AGL)
                </text>
              </g>
            );
          })}

        {/* Home Launch Site Marker */}
        <g transform={`translate(${homeSvgPos[0]}, ${homeSvgPos[1]})`}>
          <circle r="12" fill="rgba(16, 185, 129, 0.2)" stroke="#10b981" strokeWidth="2" />
          <text x="0" y="4" textAnchor="middle" fill="#10b981" fontSize="10" fontWeight="bold">
            H
          </text>
          <text x="0" y="24" textAnchor="middle" fill="#10b981" fontSize="9" fontFamily="var(--font-mono)">
            HOME SITE
          </text>
        </g>

        {/* Survivor Detection Marker (If Active) */}
        {survivorLocation && (
          <g transform={`translate(${project(survivorLocation[0], survivorLocation[1])[0]}, ${project(survivorLocation[0], survivorLocation[1])[1]})`}>
            <circle r="18" fill="rgba(239, 68, 68, 0.25)" stroke="#ef4444" strokeWidth="2" />
            <circle r="28" fill="none" stroke="#ef4444" strokeWidth="1.5" opacity="0.6">
              <animate attributeName="r" values="18;36;18" dur="2s" repeatCount="indefinite" />
              <animate attributeName="opacity" values="0.8;0;0.8" dur="2s" repeatCount="indefinite" />
            </circle>
            <UserCheck size={18} color="#ef4444" x="-9" y="-9" />
            <text x="24" y="4" fill="#ef4444" fontSize="11" fontWeight="bold" fontFamily="var(--font-mono)">
              SURVIVOR DETECTED [CONFIDENCE: 94%]
            </text>
          </g>
        )}

        {/* Live Simulated Drone */}
        <g transform={`translate(${droneSvgPos[0]}, ${droneSvgPos[1]})`}>
          {/* Sensor Scan Cone Footprint */}
          {showSensorCone && drone.is_airborne && (
            <path
              d="M 0 0 L -45 -120 A 130 130 0 0 1 45 -120 Z"
              fill="url(#sensor-gradient)"
              transform={`rotate(${drone.heading_deg})`}
            />
          )}

          {/* Radar Ring */}
          <circle r="22" fill="none" stroke="rgba(0, 229, 255, 0.4)" strokeWidth="1" strokeDasharray="3,3" />

          {/* Heading Vector Arrow */}
          <line
            x1="0"
            y1="0"
            x2="0"
            y2="-32"
            stroke="#00e5ff"
            strokeWidth="2.5"
            transform={`rotate(${drone.heading_deg})`}
          />

          {/* Drone Body Glyph */}
          <polygon
            points="0,-14 10,12 0,7 -10,12"
            fill="#00e5ff"
            stroke="#ffffff"
            strokeWidth="1.5"
            transform={`rotate(${drone.heading_deg})`}
          />

          {/* Telemetry Tag beside drone */}
          <g transform="translate(18, -12)">
            <rect width="110" height="34" rx="4" fill="rgba(15, 23, 42, 0.85)" stroke="#00e5ff" strokeWidth="1" />
            <text x="6" y="14" fill="#00e5ff" fontSize="9" fontWeight="bold" fontFamily="var(--font-mono)">
              {drone.drone_id}
            </text>
            <text x="6" y="27" fill="#f8fafc" fontSize="9" fontFamily="var(--font-mono)">
              AGL: {drone.altitude_agl_m.toFixed(1)}m | {drone.velocity_mps.toFixed(1)}m/s
            </text>
          </g>
        </g>
      </svg>

      {/* Floating HUD Map Overlays */}
      <div
        style={{
          position: "absolute",
          top: "12px",
          left: "12px",
          display: "flex",
          gap: "8px",
          zIndex: 10,
        }}
      >
        <div className="glass-panel" style={{ padding: "6px 12px", display: "flex", alignItems: "center", gap: "8px" }}>
          <Crosshair size={14} color="#00e5ff" />
          <span className="mono" style={{ fontSize: "0.75rem", color: "#94a3b8" }}>
            {cursorCoord
              ? `WGS84: ${cursorCoord.lat.toFixed(5)}°N, ${cursorCoord.lon.toFixed(5)}°W`
              : "HOVER OVER MAP FOR GPS COORDS"}
          </span>
        </div>

        <div className="glass-panel" style={{ padding: "6px 12px", display: "flex", alignItems: "center", gap: "8px" }}>
          <Compass size={14} color="#10b981" />
          <span className="mono" style={{ fontSize: "0.75rem", color: "#f8fafc" }}>
            WIND: {world.wind_speed_mps.toFixed(1)} m/s @ {world.wind_direction_deg}°
          </span>
        </div>
      </div>

      {/* Map Control Buttons (Zoom, Reset, Layers) */}
      <div
        style={{
          position: "absolute",
          bottom: "16px",
          right: "16px",
          display: "flex",
          flexDirection: "column",
          gap: "6px",
          zIndex: 10,
        }}
      >
        <button
          className="btn btn-outline"
          style={{ width: "36px", height: "36px", padding: 0 }}
          onClick={() => setZoom((z) => Math.min(z + 0.25, 3.5))}
          title="Zoom In"
        >
          <ZoomIn size={16} />
        </button>
        <button
          className="btn btn-outline"
          style={{ width: "36px", height: "36px", padding: 0 }}
          onClick={() => setZoom((z) => Math.max(z - 0.25, 0.6))}
          title="Zoom Out"
        >
          <ZoomOut size={16} />
        </button>
        <button
          className="btn btn-outline"
          style={{ width: "36px", height: "36px", padding: 0 }}
          onClick={() => {
            setZoom(1);
            setPan({ x: 0, y: 0 });
          }}
          title="Reset Center"
        >
          <Crosshair size={16} />
        </button>
      </div>

      {/* Layer Toggles Floating Card */}
      <div
        style={{
          position: "absolute",
          bottom: "16px",
          left: "16px",
          zIndex: 10,
        }}
      >
        <div className="glass-panel" style={{ padding: "8px 12px", display: "flex", gap: "12px", fontSize: "0.75rem" }}>
          <label style={{ display: "flex", alignItems: "center", gap: "5px", cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={showGeofence}
              onChange={(e) => setShowGeofence(e.target.checked)}
            />
            <span style={{ color: "#10b981" }}>Geofence</span>
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: "5px", cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={showRestricted}
              onChange={(e) => setShowRestricted(e.target.checked)}
            />
            <span style={{ color: "#ef4444" }}>Hazards</span>
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: "5px", cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={showWaypoints}
              onChange={(e) => setShowWaypoints(e.target.checked)}
            />
            <span style={{ color: "#00e5ff" }}>Waypoints</span>
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: "5px", cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={showSensorCone}
              onChange={(e) => setShowSensorCone(e.target.checked)}
            />
            <span style={{ color: "#8b5cf6" }}>Sensor Cone</span>
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: "5px", cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={showBreadcrumbs}
              onChange={(e) => setShowBreadcrumbs(e.target.checked)}
            />
            <span style={{ color: "#38bdf8" }}>Trail</span>
          </label>
        </div>
      </div>
    </div>
  );
};
