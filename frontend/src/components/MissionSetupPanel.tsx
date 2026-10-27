import React, { useState } from "react";
import type { Mission } from "../contracts/contracts";
import { Compass, Sliders, Shield } from "lucide-react";

interface MissionSetupPanelProps {
  mission: Mission;
  onUpdateMission: (updated: Mission) => void;
  onGeneratePlan: (altitudeAg: number, speedMps: number) => void;
}

export const MissionSetupPanel: React.FC<MissionSetupPanelProps> = ({
  mission,
  onUpdateMission,
  onGeneratePlan,
}) => {
  const [instruction, setInstruction] = useState(mission.operator_instruction);
  const [altitude, setAltitude] = useState(45.0);
  const [speed, setSpeed] = useState(10.0);
  const [minAlt, setMinAlt] = useState(mission.operator_restrictions.min_altitude_agl_m ?? 25.0);
  const [maxAlt, setMaxAlt] = useState(mission.operator_restrictions.max_altitude_agl_m ?? 80.0);

  const handleSaveRestrictions = () => {
    onUpdateMission({
      ...mission,
      operator_instruction: instruction,
      operator_restrictions: {
        ...mission.operator_restrictions,
        min_altitude_agl_m: minAlt,
        max_altitude_agl_m: maxAlt,
      },
    });
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      {/* Objective & Natural Language Prompt */}
      <div className="glass-panel" style={{ padding: "16px" }}>
        <h3 style={{ fontSize: "0.95rem", fontWeight: 700, color: "#f8fafc", marginBottom: "8px" }}>
          Mission Authorization & Objective
        </h3>

        <div style={{ display: "flex", gap: "12px", marginBottom: "12px" }}>
          <div style={{ flex: 1 }}>
            <label style={{ fontSize: "0.75rem", color: "#94a3b8" }}>Mission Identifier</label>
            <input
              type="text"
              className="mono"
              style={{
                width: "100%",
                background: "rgba(15, 23, 42, 0.8)",
                border: "1px solid rgba(255, 255, 255, 0.15)",
                borderRadius: "6px",
                padding: "8px 10px",
                color: "#00e5ff",
                fontSize: "0.85rem",
                marginTop: "4px",
              }}
              value={mission.mission_id}
              disabled
            />
          </div>

          <div style={{ flex: 1 }}>
            <label style={{ fontSize: "0.75rem", color: "#94a3b8" }}>Approved Capability (A04)</label>
            <input
              type="text"
              className="mono"
              style={{
                width: "100%",
                background: "rgba(15, 23, 42, 0.8)",
                border: "1px solid rgba(255, 255, 255, 0.15)",
                borderRadius: "6px",
                padding: "8px 10px",
                color: "#10b981",
                fontSize: "0.85rem",
                marginTop: "4px",
              }}
              value="SURVEY_AREA (FROZEN)"
              disabled
            />
          </div>
        </div>

        <div>
          <label style={{ fontSize: "0.75rem", color: "#94a3b8" }}>
            Natural Language Operator Instruction (Advisory Traceability)
          </label>
          <textarea
            className="mono"
            rows={3}
            style={{
              width: "100%",
              background: "rgba(15, 23, 42, 0.8)",
              border: "1px solid rgba(255, 255, 255, 0.15)",
              borderRadius: "6px",
              padding: "8px 10px",
              color: "#f8fafc",
              fontSize: "0.8rem",
              marginTop: "4px",
              resize: "vertical",
            }}
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
          />
        </div>
      </div>

      {/* Flight Parameters & Restrictions */}
      <div className="glass-panel" style={{ padding: "16px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
          <Sliders size={18} color="#00e5ff" />
          <h3 style={{ fontSize: "0.95rem", fontWeight: 700, color: "#f8fafc" }}>
            Survey Parameters & Airframe Controls
          </h3>
        </div>

        {/* Survey Altitude AGL Slider */}
        <div style={{ marginBottom: "14px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem" }}>
            <span style={{ color: "#94a3b8" }}>Planned Survey Altitude (AGL)</span>
            <span className="mono" style={{ color: "#00e5ff", fontWeight: 700 }}>
              {altitude.toFixed(0)} metres AGL
            </span>
          </div>
          <input
            type="range"
            min="15"
            max="120"
            step="5"
            value={altitude}
            onChange={(e) => setAltitude(parseFloat(e.target.value))}
            style={{ width: "100%", marginTop: "6px", accentColor: "#00e5ff" }}
          />
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.65rem", color: "#64748b" }}>
            <span>Min (15m AGL)</span>
            <span>Policy Ceiling (120m AGL)</span>
          </div>
        </div>

        {/* Flight Speed Slider */}
        <div style={{ marginBottom: "16px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem" }}>
            <span style={{ color: "#94a3b8" }}>Planned Flight Speed</span>
            <span className="mono" style={{ color: "#00e5ff", fontWeight: 700 }}>
              {speed.toFixed(1)} m/s
            </span>
          </div>
          <input
            type="range"
            min="4"
            max="15"
            step="0.5"
            value={speed}
            onChange={(e) => setSpeed(parseFloat(e.target.value))}
            style={{ width: "100%", marginTop: "6px", accentColor: "#00e5ff" }}
          />
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.65rem", color: "#64748b" }}>
            <span>Loiter (4 m/s)</span>
            <span>Max Cruise (15 m/s)</span>
          </div>
        </div>

        {/* Operator Altitude Restriction Controls */}
        <div style={{ marginBottom: "16px", padding: "10px", background: "rgba(0,0,0,0.2)", borderRadius: "6px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "8px" }}>
            <Shield size={14} color="#10b981" />
            <span style={{ fontSize: "0.75rem", fontWeight: 600, color: "#10b981" }}>
              Operator Mandatory Restrictions
            </span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
            <div>
              <label style={{ fontSize: "0.7rem", color: "#94a3b8" }}>Min AGL Floor: {minAlt}m</label>
              <input
                type="range"
                min="15"
                max="50"
                value={minAlt}
                onChange={(e) => setMinAlt(parseFloat(e.target.value))}
                style={{ width: "100%", accentColor: "#10b981" }}
              />
            </div>
            <div>
              <label style={{ fontSize: "0.7rem", color: "#94a3b8" }}>Max AGL Ceiling: {maxAlt}m</label>
              <input
                type="range"
                min="50"
                max="120"
                value={maxAlt}
                onChange={(e) => setMaxAlt(parseFloat(e.target.value))}
                style={{ width: "100%", accentColor: "#10b981" }}
              />
            </div>
          </div>
        </div>

        {/* Action: Generate Route */}
        <div style={{ display: "flex", gap: "10px" }}>
          <button
            className="btn btn-primary"
            style={{ flex: 1 }}
            onClick={() => {
              handleSaveRestrictions();
              onGeneratePlan(altitude, speed);
            }}
          >
            <Compass size={16} />
            GENERATE LAWNMOWER SURVEY PLAN
          </button>
        </div>
      </div>
    </div>
  );
};
