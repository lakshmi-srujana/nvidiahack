import React from "react";
import type { SimulationEvent } from "../contracts/contracts";
import {
  UserCheck,
  BatteryWarning,
  Wind,
  ShieldAlert,
  FileEdit,
  Activity,
  Terminal,
} from "lucide-react";

interface SimulationControlsProps {
  events: SimulationEvent[];
  onInjectSurvivor: () => void;
  onInjectLowBattery: () => void;
  onInjectWindSpike: () => void;
  onInjectNewRestrictedZone: () => void;
  onInjectOperatorChange: () => void;
}

export const SimulationControls: React.FC<SimulationControlsProps> = ({
  events,
  onInjectSurvivor,
  onInjectLowBattery,
  onInjectWindSpike,
  onInjectNewRestrictedZone,
  onInjectOperatorChange,
}) => {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      {/* Event Trigger Injector Toolbar */}
      <div className="glass-panel" style={{ padding: "16px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
          <Activity size={18} color="#00e5ff" />
          <h3 style={{ fontSize: "0.95rem", fontWeight: 700, color: "#f8fafc" }}>
            Seeded Event Injectors (5 Approved Replanning Families)
          </h3>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "10px" }}>
          {/* Trigger 1: Survivor Detected */}
          <button
            className="btn btn-outline"
            style={{ borderColor: "rgba(16, 185, 129, 0.4)", justifyContent: "flex-start" }}
            onClick={onInjectSurvivor}
          >
            <UserCheck size={16} color="#10b981" />
            <div style={{ textAlign: "left" }}>
              <div style={{ fontSize: "0.8rem", fontWeight: 700, color: "#10b981" }}>
                Survivor Detected
              </div>
              <div style={{ fontSize: "0.65rem", color: "#94a3b8" }}>
                Inject AI visual detection
              </div>
            </div>
          </button>

          {/* Trigger 2: Low Battery */}
          <button
            className="btn btn-outline"
            style={{ borderColor: "rgba(245, 158, 11, 0.4)", justifyContent: "flex-start" }}
            onClick={onInjectLowBattery}
          >
            <BatteryWarning size={16} color="#f59e0b" />
            <div style={{ textAlign: "left" }}>
              <div style={{ fontSize: "0.8rem", fontWeight: 700, color: "#f59e0b" }}>
                Low Battery Alarm
              </div>
              <div style={{ fontSize: "0.65rem", color: "#94a3b8" }}>
                Trigger 18% reserve warning
              </div>
            </div>
          </button>

          {/* Trigger 3: Wind Spike */}
          <button
            className="btn btn-outline"
            style={{ borderColor: "rgba(239, 68, 68, 0.4)", justifyContent: "flex-start" }}
            onClick={onInjectWindSpike}
          >
            <Wind size={16} color="#ef4444" />
            <div style={{ textAlign: "left" }}>
              <div style={{ fontSize: "0.8rem", fontWeight: 700, color: "#ef4444" }}>
                Wind Gust Spike
              </div>
              <div style={{ fontSize: "0.65rem", color: "#94a3b8" }}>
                14.8 m/s (Limit: 12.0)
              </div>
            </div>
          </button>

          {/* Trigger 4: New Restricted Zone */}
          <button
            className="btn btn-outline"
            style={{ borderColor: "rgba(239, 68, 68, 0.4)", justifyContent: "flex-start" }}
            onClick={onInjectNewRestrictedZone}
          >
            <ShieldAlert size={16} color="#ef4444" />
            <div style={{ textAlign: "left" }}>
              <div style={{ fontSize: "0.8rem", fontWeight: 700, color: "#ef4444" }}>
                New Hazard Zone
              </div>
              <div style={{ fontSize: "0.65rem", color: "#94a3b8" }}>
                Inject emergency flood zone
              </div>
            </div>
          </button>

          {/* Trigger 5: Operator Mission Change */}
          <button
            className="btn btn-outline"
            style={{ borderColor: "rgba(0, 229, 255, 0.4)", justifyContent: "flex-start" }}
            onClick={onInjectOperatorChange}
          >
            <FileEdit size={16} color="#00e5ff" />
            <div style={{ textAlign: "left" }}>
              <div style={{ fontSize: "0.8rem", fontWeight: 700, color: "#00e5ff" }}>
                Operator Boundary Change
              </div>
              <div style={{ fontSize: "0.65rem", color: "#94a3b8" }}>
                Expand search corridor
              </div>
            </div>
          </button>
        </div>
      </div>

      {/* Live Event Audit Timeline Stream */}
      <div className="glass-panel" style={{ padding: "16px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <Terminal size={18} color="#8b5cf6" />
            <h3 style={{ fontSize: "0.95rem", fontWeight: 700, color: "#f8fafc" }}>
              Live Event Audit Timeline ({events.length} events recorded)
            </h3>
          </div>
          <span className="mono" style={{ fontSize: "0.7rem", color: "#64748b" }}>
            MONOTONIC STREAM
          </span>
        </div>

        <div
          style={{
            maxHeight: "340px",
            overflowY: "auto",
            display: "flex",
            flexDirection: "column",
            gap: "8px",
          }}
        >
          {events.length === 0 ? (
            <div style={{ padding: "20px", textAlign: "center", color: "#64748b", fontSize: "0.8rem" }}>
              No simulation events recorded yet. Launch mission or inject triggers.
            </div>
          ) : (
            [...events].reverse().map((evt) => (
              <div
                key={evt.event_id}
                className="glass-panel-elevated"
                style={{ padding: "10px 12px", borderLeft: "3px solid #00e5ff" }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <span className="mono" style={{ fontSize: "0.75rem", fontWeight: 700, color: "#00e5ff" }}>
                      {evt.event_id}
                    </span>
                    <span
                      className={`badge ${
                        evt.event_type === "SURVIVOR_DETECTED"
                          ? "badge-emerald"
                          : evt.event_type === "LOW_BATTERY" || evt.event_type === "WIND_SPIKE"
                          ? "badge-rose"
                          : "badge-cyan"
                      }`}
                      style={{ fontSize: "0.65rem" }}
                    >
                      {evt.event_type}
                    </span>
                  </div>

                  <span className="mono" style={{ fontSize: "0.7rem", color: "#64748b" }}>
                    T+{evt.sim_time_s.toFixed(0)}s • SRC: {evt.source}
                  </span>
                </div>

                <div
                  className="mono"
                  style={{
                    fontSize: "0.75rem",
                    color: "#cbd5e1",
                    background: "rgba(0, 0, 0, 0.3)",
                    padding: "6px 8px",
                    borderRadius: "4px",
                    overflowX: "auto",
                  }}
                >
                  {JSON.stringify(evt.payload)}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
