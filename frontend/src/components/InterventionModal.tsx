import React from "react";
import { AlertOctagon, RotateCcw, Home, XOctagon } from "lucide-react";

interface InterventionModalProps {
  isOpen: boolean;
  attemptCount: number;
  reason: string;
  onReturnHome: () => void;
  onResetAndModify: () => void;
  onAbortMission: () => void;
}

export const InterventionModal: React.FC<InterventionModalProps> = ({
  isOpen,
  attemptCount,
  reason,
  onReturnHome,
  onResetAndModify,
  onAbortMission,
}) => {
  if (!isOpen) return null;

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(0, 0, 0, 0.8)",
        backdropFilter: "blur(8px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
      }}
    >
      <div
        className="glass-panel"
        style={{
          width: "90%",
          maxWidth: "540px",
          padding: "28px",
          border: "2px solid #ef4444",
          boxShadow: "0 0 40px rgba(239, 68, 68, 0.4)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "16px" }}>
          <AlertOctagon size={36} color="#ef4444" />
          <div>
            <h2 style={{ fontSize: "1.2rem", fontWeight: 800, color: "#ef4444" }}>
              OPERATOR INTERVENTION REQUIRED
            </h2>
            <span className="mono" style={{ fontSize: "0.75rem", color: "#94a3b8" }}>
              DECISION A08 ENFORCED: REPAIR CAP REACHED ({attemptCount} ATTEMPTS)
            </span>
          </div>
        </div>

        <p style={{ fontSize: "0.85rem", color: "#f8fafc", lineHeight: 1.5, marginBottom: "20px" }}>
          Autonomous replanning has been halted because the automated repair loop failed to converge
          on a verifiable safe plan after 3 consecutive attempts.
        </p>

        <div
          className="glass-panel-elevated mono"
          style={{
            padding: "10px 14px",
            fontSize: "0.75rem",
            color: "#fca5a5",
            marginBottom: "24px",
            borderLeft: "3px solid #ef4444",
          }}
        >
          {reason}
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
          <button
            className="btn btn-primary"
            style={{ width: "100%", justifyContent: "center" }}
            onClick={onReturnHome}
          >
            <Home size={18} />
            ORDER DETERMINISTIC RETURN-TO-HOME (RTH)
          </button>

          <button
            className="btn btn-outline"
            style={{ width: "100%", justifyContent: "center" }}
            onClick={onResetAndModify}
          >
            <RotateCcw size={18} />
            RESET COUNTER & MANUALLY RESHAPE CONSTRAINTS
          </button>

          <button
            className="btn btn-danger"
            style={{ width: "100%", justifyContent: "center" }}
            onClick={onAbortMission}
          >
            <XOctagon size={18} />
            ABORT MISSION & GROUND DRONE
          </button>
        </div>
      </div>
    </div>
  );
};
