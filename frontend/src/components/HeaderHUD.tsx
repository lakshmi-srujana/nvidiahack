import React from "react";
import type {
  Mission,
  DroneState,
  WorldState,
  Certificate,
} from "../contracts/contracts";
import {
  ShieldCheck,
  ShieldAlert,
  BatteryCharging,
  Gauge,
  Wind,
  Clock,
  Play,
  Pause,
  RotateCcw,
  Activity,
  CloudSun,
  Download,
} from "lucide-react";

interface HeaderHUDProps {
  mission: Mission;
  drone: DroneState;
  world: WorldState;
  certificate: Certificate | null;
  isSimRunning: boolean;
  simSpeed: number;
  isLiveWeather: boolean;
  onToggleSim: () => void;
  onChangeSpeed: (spd: number) => void;
  onResetSim: () => void;
  onSelectScenario: (scenarioId: string) => void;
  onToggleLiveWeather: () => void;
  onExportAudit: () => void;
}

export const HeaderHUD: React.FC<HeaderHUDProps> = ({
  mission,
  drone,
  world,
  certificate,
  isSimRunning,
  simSpeed,
  isLiveWeather,
  onToggleSim,
  onChangeSpeed,
  onResetSim,
  onSelectScenario,
  onToggleLiveWeather,
  onExportAudit,
}) => {
  // Format monotonic seconds to MM:SS
  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `T+${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  };

  const getStatusBadge = () => {
    if (mission.status === "INTERVENTION_REQUIRED") {
      return (
        <span className="badge badge-rose">
          <span className="pulse-indicator" style={{ backgroundColor: "#ef4444" }} />
          INTERVENTION REQUIRED
        </span>
      );
    }
    if (drone.is_airborne) {
      return (
        <span className="badge badge-cyan">
          <span className="pulse-indicator" style={{ backgroundColor: "#00e5ff" }} />
          AIRBORNE SURVEY
        </span>
      );
    }
    if (certificate && certificate.is_valid) {
      return (
        <span className="badge badge-emerald">
          <ShieldCheck size={14} />
          CERTIFIED SAFE
        </span>
      );
    }
    return (
      <span className="badge badge-amber">
        <ShieldAlert size={14} />
        AWAITING CERTIFICATION
      </span>
    );
  };

  return (
    <header
      className="glass-panel"
      style={{
        padding: "12px 20px",
        display: "flex",
        flexWrap: "wrap",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "16px",
        borderBottom: "1px solid rgba(0, 229, 255, 0.2)",
      }}
    >
      {/* Brand & Mission Status */}
      <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <Activity color="#00e5ff" size={20} />
            <h1
              style={{
                fontSize: "1.25rem",
                fontWeight: 800,
                letterSpacing: "0.08em",
                background: "linear-gradient(90deg, #00e5ff, #38bdf8)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
              }}
            >
              SKYWArDEN
            </h1>
            <span
              className="mono"
              style={{
                fontSize: "0.65rem",
                color: "#64748b",
                border: "1px solid #334155",
                padding: "2px 6px",
                borderRadius: "4px",
              }}
            >
              v1.0-SAFETY
            </span>
          </div>
          <div
            style={{
              fontSize: "0.75rem",
              color: "#94a3b8",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              marginTop: "2px",
            }}
          >
            <span>MISSION: <strong style={{ color: "#f8fafc" }}>{mission.mission_id}</strong></span>
            <span>•</span>
            <span>DRONE: <strong style={{ color: "#00e5ff" }}>{drone.drone_id}</strong></span>
          </div>
        </div>

        <div>{getStatusBadge()}</div>
      </div>

      {/* Real-time Telemetry HUD Gauges */}
      <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
        {/* Battery Gauge */}
        <div
          className="glass-panel-elevated"
          style={{ padding: "6px 12px", display: "flex", alignItems: "center", gap: "8px" }}
        >
          <BatteryCharging
            size={18}
            color={drone.battery_pct > 25 ? "#10b981" : "#ef4444"}
          />
          <div>
            <div style={{ fontSize: "0.65rem", color: "#94a3b8", textTransform: "uppercase" }}>
              Battery Reserve
            </div>
            <div
              className="mono"
              style={{
                fontSize: "0.9rem",
                fontWeight: 700,
                color: drone.battery_pct > 25 ? "#f8fafc" : "#ef4444",
              }}
            >
              {drone.battery_pct.toFixed(0)}%{" "}
              <span style={{ fontSize: "0.7rem", color: "#64748b" }}>
                ({drone.battery_wh.toFixed(1)} Wh)
              </span>
            </div>
          </div>
        </div>

        {/* Altitude AGL Gauge */}
        <div
          className="glass-panel-elevated"
          style={{ padding: "6px 12px", display: "flex", alignItems: "center", gap: "8px" }}
        >
          <Gauge size={18} color="#00e5ff" />
          <div>
            <div style={{ fontSize: "0.65rem", color: "#94a3b8", textTransform: "uppercase" }}>
              Altitude AGL
            </div>
            <div className="mono" style={{ fontSize: "0.9rem", fontWeight: 700, color: "#f8fafc" }}>
              {drone.altitude_agl_m.toFixed(1)}{" "}
              <span style={{ fontSize: "0.7rem", color: "#64748b" }}>metres</span>
            </div>
          </div>
        </div>

        {/* Ground Speed Gauge */}
        <div
          className="glass-panel-elevated"
          style={{ padding: "6px 12px", display: "flex", alignItems: "center", gap: "8px" }}
        >
          <Activity size={18} color="#38bdf8" />
          <div>
            <div style={{ fontSize: "0.65rem", color: "#94a3b8", textTransform: "uppercase" }}>
              Ground Speed
            </div>
            <div className="mono" style={{ fontSize: "0.9rem", fontWeight: 700, color: "#f8fafc" }}>
              {drone.velocity_mps.toFixed(1)}{" "}
              <span style={{ fontSize: "0.7rem", color: "#64748b" }}>m/s</span>
            </div>
          </div>
        </div>

        {/* Ambient Wind & Live Weather Gauge */}
        <div
          className="glass-panel-elevated"
          onClick={onToggleLiveWeather}
          style={{
            padding: "6px 12px",
            display: "flex",
            alignItems: "center",
            gap: "8px",
            cursor: "pointer",
            border: isLiveWeather ? "1px solid rgba(16, 185, 129, 0.4)" : "1px solid rgba(255, 255, 255, 0.12)",
          }}
          title={isLiveWeather ? "Live Open-Meteo weather active. Click to switch to scenario manual." : "Click to fetch live Open-Meteo weather."}
        >
          {isLiveWeather ? (
            <CloudSun size={18} color="#10b981" />
          ) : (
            <Wind size={18} color={world.wind_speed_mps <= 12 ? "#38bdf8" : "#ef4444"} />
          )}
          <div>
            <div style={{ fontSize: "0.62rem", color: "#94a3b8", textTransform: "uppercase", display: "flex", alignItems: "center", gap: "4px" }}>
              {isLiveWeather && <span className="pulse-indicator" style={{ backgroundColor: "#10b981", width: "6px", height: "6px" }} />}
              {isLiveWeather ? "OPEN-METEO LIVE" : "SCENARIO WIND"}
            </div>
            <div
              className="mono"
              style={{
                fontSize: "0.85rem",
                fontWeight: 700,
                color: world.wind_speed_mps <= 12 ? "#f8fafc" : "#ef4444",
              }}
            >
              {world.wind_speed_mps.toFixed(1)} m/s{" "}
              <span style={{ fontSize: "0.68rem", color: "#94a3b8" }}>
                ({world.ambient_temperature_c.toFixed(0)}°C)
              </span>
            </div>
          </div>
        </div>

        {/* Sim Clock */}
        <div
          className="glass-panel-elevated"
          style={{ padding: "6px 12px", display: "flex", alignItems: "center", gap: "8px" }}
        >
          <Clock size={18} color="#8b5cf6" />
          <div>
            <div style={{ fontSize: "0.65rem", color: "#94a3b8", textTransform: "uppercase" }}>
              Sim Monotonic
            </div>
            <div className="mono" style={{ fontSize: "0.9rem", fontWeight: 700, color: "#a78bfa" }}>
              {formatTime(drone.sim_time_s)}
            </div>
          </div>
        </div>
      </div>

      {/* Simulator Playback & Scenario Controls */}
      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
        {/* Scenario Preloader */}
        <select
          className="btn btn-outline mono"
          style={{ fontSize: "0.75rem", padding: "6px 10px" }}
          onChange={(e) => onSelectScenario(e.target.value)}
          defaultValue="scenario_flood"
        >
          <option value="scenario_flood">Scenario 1: Flash Flood Search (Nominal)</option>
          <option value="scenario_wind">Scenario 2: High Wind Violation</option>
          <option value="scenario_geofence">Scenario 3: Geofence Breach Rejection</option>
          <option value="scenario_hazard">Scenario 4: Hazard Substation Breach</option>
          <option value="scenario_dam">Scenario 5: Dam Breach Surge Zone</option>
          <option value="scenario_battery">Scenario 6: Battery Critical Emergency RTH</option>
        </select>

        {/* Play/Pause Button */}
        <button
          className={`btn ${isSimRunning ? "btn-danger" : "btn-primary"}`}
          onClick={onToggleSim}
          style={{ padding: "8px 14px" }}
          title={isSimRunning ? "Pause Simulation" : "Start Simulation"}
        >
          {isSimRunning ? <Pause size={16} /> : <Play size={16} />}
          <span>{isSimRunning ? "PAUSE" : "SIMULATE"}</span>
        </button>

        {/* Speed Multiplier */}
        <div className="glass-panel" style={{ display: "flex", padding: "2px" }}>
          {[1, 2, 5].map((spd) => (
            <button
              key={spd}
              className="btn mono"
              style={{
                padding: "4px 8px",
                fontSize: "0.75rem",
                background: simSpeed === spd ? "rgba(0, 229, 255, 0.2)" : "transparent",
                color: simSpeed === spd ? "#00e5ff" : "#94a3b8",
                border: "none",
              }}
              onClick={() => onChangeSpeed(spd)}
            >
              {spd}x
            </button>
          ))}
        </div>

        {/* Export Audit Log Button */}
        <button
          className="btn btn-outline"
          onClick={onExportAudit}
          style={{ padding: "8px", color: "#38bdf8" }}
          title="Export Simulation Audit Log (JSON)"
        >
          <Download size={16} />
        </button>

        {/* Reset Simulation Button */}
        <button
          className="btn btn-outline"
          onClick={onResetSim}
          style={{ padding: "8px" }}
          title="Reset Simulation"
        >
          <RotateCcw size={16} />
        </button>
      </div>
    </header>
  );
};
