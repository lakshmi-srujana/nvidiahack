"""
SkyWarden SQLite Memory & Audit Persistence Store
Implements SQLite memory required for Developer B in CONTRACTS.md:
"Open-Meteo weather and SQLite memory; generation of simulator events"
"""

import sqlite3
import json
from typing import Optional, List, Dict, Any
from verifier.models import (
    Mission,
    Plan,
    VerificationResult,
    Certificate,
    SimulationEvent,
)


class SQLiteMemoryStore:
    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        return self._conn

    def _init_db(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        # Missions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS missions (
                mission_id TEXT PRIMARY KEY,
                objective_type TEXT NOT NULL,
                status TEXT NOT NULL,
                survey_area TEXT NOT NULL,
                operator_restrictions TEXT,
                operator_instruction TEXT,
                created_at TEXT NOT NULL
            )
        """)
        # Plans table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS plans (
                plan_id TEXT PRIMARY KEY,
                mission_id TEXT NOT NULL,
                revision INTEGER NOT NULL,
                waypoints TEXT NOT NULL,
                estimated_duration_s REAL,
                estimated_energy_wh REAL,
                provenance TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(mission_id) REFERENCES missions(mission_id)
            )
        """)
        # Verification results table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS verification_results (
                plan_id TEXT PRIMARY KEY,
                mission_id TEXT NOT NULL,
                passed INTEGER NOT NULL,
                policy_ref TEXT,
                world_ref TEXT,
                drone_ref TEXT,
                checks TEXT NOT NULL,
                violations TEXT NOT NULL,
                verified_at TEXT NOT NULL,
                FOREIGN KEY(plan_id) REFERENCES plans(plan_id)
            )
        """)
        # Safety certificates table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS certificates (
                certificate_id TEXT PRIMARY KEY,
                mission_id TEXT NOT NULL,
                plan_id TEXT NOT NULL,
                plan_digest TEXT NOT NULL,
                is_valid INTEGER NOT NULL,
                invalidation_reason TEXT,
                issued_at TEXT NOT NULL,
                rule_results TEXT NOT NULL,
                FOREIGN KEY(plan_id) REFERENCES plans(plan_id)
            )
        """)
        # Simulation events timeline table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS simulation_events (
                event_id TEXT PRIMARY KEY,
                mission_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                sim_time_s REAL NOT NULL,
                sequence INTEGER NOT NULL,
                source TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(mission_id) REFERENCES missions(mission_id)
            )
        """)
        conn.commit()

    # --- Mission Persistence ---
    def save_mission(self, mission: Mission) -> None:
        conn = self._get_connection()
        restrictions_json = None
        if mission.operator_restrictions:
            restrictions_json = json.dumps(mission.operator_restrictions.model_dump())

        conn.execute("""
            INSERT OR REPLACE INTO missions 
            (mission_id, objective_type, status, survey_area, operator_restrictions, operator_instruction, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            mission.mission_id,
            mission.objective_type.value,
            mission.status.value,
            json.dumps(mission.survey_area.model_dump()),
            restrictions_json,
            mission.operator_instruction,
            mission.created_at,
        ))
        conn.commit()

    def get_mission(self, mission_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        row = conn.execute("SELECT * FROM missions WHERE mission_id = ?", (mission_id,)).fetchone()
        if not row:
            return None
        return {
            "mission_id": row["mission_id"],
            "objective_type": row["objective_type"],
            "status": row["status"],
            "survey_area": json.loads(row["survey_area"]),
            "operator_restrictions": json.loads(row["operator_restrictions"]) if row["operator_restrictions"] else None,
            "operator_instruction": row["operator_instruction"],
            "created_at": row["created_at"],
        }

    # --- Plan Persistence ---
    def save_plan(self, plan: Plan) -> None:
        conn = self._get_connection()
        conn.execute("""
            INSERT OR REPLACE INTO plans 
            (plan_id, mission_id, revision, waypoints, estimated_duration_s, estimated_energy_wh, provenance, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            plan.plan_id,
            plan.mission_id,
            plan.revision,
            json.dumps([w.model_dump() for w in plan.waypoints]),
            plan.estimated_duration_s,
            plan.estimated_energy_wh,
            json.dumps(plan.provenance.model_dump()),
            plan.created_at,
        ))
        conn.commit()

    # --- Verification & Certificate Persistence ---
    def save_verification(self, result: VerificationResult) -> None:
        conn = self._get_connection()
        conn.execute("""
            INSERT OR REPLACE INTO verification_results 
            (plan_id, mission_id, passed, policy_ref, world_ref, drone_ref, checks, violations, verified_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            result.plan_id,
            result.mission_id,
            1 if result.passed else 0,
            result.policy_ref,
            result.world_ref,
            result.drone_ref,
            json.dumps([c.model_dump() for c in result.checks]),
            json.dumps([v.model_dump() for v in result.violations]),
            result.verified_at,
        ))
        conn.commit()

    def save_certificate(self, certificate: Certificate) -> None:
        conn = self._get_connection()
        conn.execute("""
            INSERT OR REPLACE INTO certificates 
            (certificate_id, mission_id, plan_id, plan_digest, is_valid, invalidation_reason, issued_at, rule_results)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            certificate.certificate_id,
            certificate.mission_id,
            certificate.plan_id,
            certificate.plan_digest,
            1 if certificate.is_valid else 0,
            certificate.invalidation_reason,
            certificate.issued_at,
            json.dumps([r.model_dump() for r in certificate.rule_results]),
        ))
        conn.commit()

    # --- Simulation Event Logging & Audit Replay ---
    def log_event(self, event: SimulationEvent) -> None:
        conn = self._get_connection()
        conn.execute("""
            INSERT OR REPLACE INTO simulation_events 
            (event_id, mission_id, event_type, sim_time_s, sequence, source, payload, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event.event_id,
            event.mission_id,
            event.event_type.value,
            event.sim_time_s,
            event.sequence,
            event.source,
            json.dumps(event.payload),
            event.created_at,
        ))
        conn.commit()

    def get_events(self, mission_id: str) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        rows = conn.execute(
            "SELECT * FROM simulation_events WHERE mission_id = ? ORDER BY sequence ASC",
            (mission_id,),
        ).fetchall()
        return [
            {
                "event_id": r["event_id"],
                "mission_id": r["mission_id"],
                "event_type": r["event_type"],
                "sim_time_s": r["sim_time_s"],
                "sequence": r["sequence"],
                "source": r["source"],
                "payload": json.loads(r["payload"]),
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def export_audit_json(self, mission_id: str) -> str:
        events = self.get_events(mission_id)
        return json.dumps(events, indent=2)

    def close(self):
        self._conn.close()
