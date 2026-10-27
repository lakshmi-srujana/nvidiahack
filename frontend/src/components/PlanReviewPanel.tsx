import React from "react";
import type {
  Plan,
  Mission,
  VerificationResult,
  Certificate,
} from "../contracts/contracts";
import {
  ShieldCheck,
  ShieldAlert,
  CheckCircle2,
  Rocket,
  Wrench,
  Hash,
  AlertTriangle,
} from "lucide-react";

interface PlanReviewPanelProps {
  plan: Plan | null;
  mission: Mission;
  verificationResult: VerificationResult | null;
  certificate: Certificate | null;
  isVerifying: boolean;
  onRunVerification: () => void;
  onLaunchFlight: () => void;
  onTriggerRepair: () => void;
}

export const PlanReviewPanel: React.FC<PlanReviewPanelProps> = ({
  plan,
  verificationResult,
  certificate,
  isVerifying,
  onRunVerification,
  onLaunchFlight,
  onTriggerRepair,
}) => {
  if (!plan) {
    return (
      <div className="glass-panel" style={{ padding: "32px", textAlign: "center" }}>
        <p style={{ color: "#94a3b8" }}>No candidate flight plan generated yet.</p>
      </div>
    );
  }

  const passed = verificationResult?.passed ?? false;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      {/* Plan Summary Card */}
      <div className="glass-panel" style={{ padding: "16px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
          <div>
            <h3 style={{ fontSize: "1rem", fontWeight: 700, color: "#f8fafc" }}>
              Flight Plan Candidate: {plan.plan_id}
            </h3>
            <span className="mono" style={{ fontSize: "0.75rem", color: "#94a3b8" }}>
              Revision {plan.revision} • Planner: {plan.provenance.planner_type} (Attempt {plan.provenance.repair_attempt}/3)
            </span>
          </div>

          <button
            className="btn btn-primary"
            onClick={onRunVerification}
            disabled={isVerifying}
          >
            <ShieldCheck size={16} />
            {isVerifying ? "VERIFYING..." : "RUN DETERMINISTIC VERIFIER"}
          </button>
        </div>

        {/* Quick Metrics Grid */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "10px" }}>
          <div className="glass-panel-elevated" style={{ padding: "8px 12px" }}>
            <div style={{ fontSize: "0.7rem", color: "#94a3b8" }}>Waypoints</div>
            <div className="mono" style={{ fontSize: "1.1rem", fontWeight: 700, color: "#00e5ff" }}>
              {plan.waypoints.length}
            </div>
          </div>
          <div className="glass-panel-elevated" style={{ padding: "8px 12px" }}>
            <div style={{ fontSize: "0.7rem", color: "#94a3b8" }}>Estimated Duration</div>
            <div className="mono" style={{ fontSize: "1.1rem", fontWeight: 700, color: "#f8fafc" }}>
              {plan.estimated_duration_s.toFixed(0)}s
            </div>
          </div>
          <div className="glass-panel-elevated" style={{ padding: "8px 12px" }}>
            <div style={{ fontSize: "0.7rem", color: "#94a3b8" }}>Energy Budget</div>
            <div className="mono" style={{ fontSize: "1.1rem", fontWeight: 700, color: "#10b981" }}>
              {plan.estimated_energy_wh.toFixed(1)} Wh
            </div>
          </div>
        </div>
      </div>

      {/* Safety Gate Outcome: Certificate or Violation Report */}
      {verificationResult && (
        <div>
          {passed && certificate ? (
            /* Digital Safety Certificate View */
            <div
              className="glass-panel"
              style={{
                padding: "20px",
                border: "1px solid rgba(16, 185, 129, 0.4)",
                background: "linear-gradient(180deg, rgba(16, 185, 129, 0.08) 0%, rgba(15, 23, 42, 0.85) 100%)",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "16px" }}>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <ShieldCheck size={24} color="#10b981" />
                    <h3 style={{ fontSize: "1.1rem", fontWeight: 800, color: "#10b981" }}>
                      IMMUTABLE SAFETY CERTIFICATE
                    </h3>
                  </div>
                  <span className="mono" style={{ fontSize: "0.75rem", color: "#94a3b8" }}>
                    ID: {certificate.certificate_id} • Issued: {new Date(certificate.issued_at).toLocaleTimeString()}
                  </span>
                </div>

                <button
                  className="btn btn-success"
                  style={{ padding: "10px 20px", fontSize: "0.95rem" }}
                  onClick={onLaunchFlight}
                >
                  <Rocket size={18} />
                  LAUNCH CERTIFIED MISSION
                </button>
              </div>

              {/* Certificate Digest & Cryptographic Proof */}
              <div
                className="glass-panel-elevated mono"
                style={{
                  padding: "10px 14px",
                  fontSize: "0.75rem",
                  color: "#cbd5e1",
                  display: "flex",
                  flexDirection: "column",
                  gap: "4px",
                  marginBottom: "16px",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                  <Hash size={14} color="#00e5ff" />
                  <span>SHA-256 Plan Digest:</span>
                  <strong style={{ color: "#00e5ff", wordBreak: "break-all" }}>
                    {certificate.plan_digest}
                  </strong>
                </div>
                <div style={{ color: "#64748b" }}>
                  Policy Ref: {certificate.policy_ref} | World Ref: {certificate.world_ref}
                </div>
              </div>

              {/* 10 Checkpoints List */}
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                <div style={{ fontSize: "0.8rem", fontWeight: 600, color: "#94a3b8", textTransform: "uppercase" }}>
                  Mandatory Deterministic Safety Checks (10 / 10 Passed)
                </div>
                {certificate.rule_results.map((rule) => (
                  <div
                    key={rule.rule_id}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      padding: "8px 12px",
                      background: "rgba(16, 185, 129, 0.05)",
                      borderRadius: "6px",
                      border: "1px solid rgba(16, 185, 129, 0.2)",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <CheckCircle2 size={16} color="#10b981" />
                      <div>
                        <div style={{ fontSize: "0.85rem", fontWeight: 600, color: "#f8fafc" }}>
                          {rule.name}
                        </div>
                        <div style={{ fontSize: "0.75rem", color: "#94a3b8" }}>
                          {rule.message}
                        </div>
                      </div>
                    </div>
                    <span className="badge badge-emerald" style={{ fontSize: "0.65rem" }}>
                      PASSED
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            /* Structured Violation Report View */
            <div
              className="glass-panel"
              style={{
                padding: "20px",
                border: "1px solid rgba(239, 68, 68, 0.4)",
                background: "linear-gradient(180deg, rgba(239, 68, 68, 0.08) 0%, rgba(15, 23, 42, 0.85) 100%)",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "16px" }}>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <ShieldAlert size={24} color="#ef4444" />
                    <h3 style={{ fontSize: "1.1rem", fontWeight: 800, color: "#ef4444" }}>
                      SAFETY GATE REJECTION — NO CERTIFICATE ISSUED
                    </h3>
                  </div>
                  <p style={{ fontSize: "0.8rem", color: "#94a3b8", marginTop: "4px" }}>
                    Mandatory safety rules failed. Mission launch blocked per Decision A09.
                  </p>
                </div>

                <button
                  className="btn btn-primary"
                  onClick={onTriggerRepair}
                  disabled={plan.provenance.repair_attempt >= 3}
                >
                  <Wrench size={16} />
                  TRIGGER REPAIR LOOP ({plan.provenance.repair_attempt + 1} / 3)
                </button>
              </div>

              {/* List of Violations */}
              <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                {verificationResult.violations.map((violation, idx) => (
                  <div
                    key={idx}
                    className="glass-panel-elevated"
                    style={{
                      padding: "12px 14px",
                      borderLeft: "4px solid #ef4444",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span className="mono" style={{ fontSize: "0.8rem", fontWeight: 700, color: "#ef4444" }}>
                        {violation.rule_id}
                      </span>
                      <span className="badge badge-rose" style={{ fontSize: "0.65rem" }}>
                        {violation.severity}
                      </span>
                    </div>

                    <div style={{ fontSize: "0.85rem", color: "#f8fafc", marginTop: "6px" }}>
                      {violation.message}
                    </div>

                    {violation.remediation && (
                      <div
                        style={{
                          marginTop: "8px",
                          fontSize: "0.75rem",
                          color: "#38bdf8",
                          display: "flex",
                          alignItems: "center",
                          gap: "6px",
                        }}
                      >
                        <AlertTriangle size={14} color="#38bdf8" />
                        <span>Actionable Remediation: <strong>{violation.remediation}</strong></span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Waypoints Route Inspection Table */}
      <div className="glass-panel" style={{ padding: "16px" }}>
        <h4 style={{ fontSize: "0.9rem", fontWeight: 700, color: "#f8fafc", marginBottom: "10px" }}>
          Waypoints Route Table ({plan.waypoints.length} points)
        </h4>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8rem" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.1)", textAlign: "left", color: "#94a3b8" }}>
                <th style={{ padding: "8px" }}>ID</th>
                <th style={{ padding: "8px" }}>Longitude (WGS84)</th>
                <th style={{ padding: "8px" }}>Latitude (WGS84)</th>
                <th style={{ padding: "8px" }}>Altitude (m AGL)</th>
                <th style={{ padding: "8px" }}>Speed (m/s)</th>
                <th style={{ padding: "8px" }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {plan.waypoints.map((wp) => (
                <tr
                  key={wp.waypoint_id}
                  style={{
                    borderBottom: "1px solid rgba(255, 255, 255, 0.05)",
                    fontFamily: "var(--font-mono)",
                  }}
                >
                  <td style={{ padding: "8px", fontWeight: 700, color: "#00e5ff" }}>{wp.waypoint_id}</td>
                  <td style={{ padding: "8px", color: "#cbd5e1" }}>{wp.longitude.toFixed(5)}</td>
                  <td style={{ padding: "8px", color: "#cbd5e1" }}>{wp.latitude.toFixed(5)}</td>
                  <td style={{ padding: "8px", color: "#f8fafc" }}>{wp.altitude_agl_m.toFixed(1)}</td>
                  <td style={{ padding: "8px", color: "#f8fafc" }}>{wp.speed_mps.toFixed(1)}</td>
                  <td style={{ padding: "8px" }}>
                    <span
                      style={{
                        padding: "2px 6px",
                        borderRadius: "4px",
                        fontSize: "0.7rem",
                        background: wp.action === "SURVEY" ? "rgba(0, 229, 255, 0.15)" : "rgba(139, 92, 246, 0.15)",
                        color: wp.action === "SURVEY" ? "#00e5ff" : "#a78bfa",
                      }}
                    >
                      {wp.action}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
