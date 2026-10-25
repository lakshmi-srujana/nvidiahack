/**
 * Local Storage & Audit Persistence Service
 * Retains mission states, certificates, and simulation logs across browser sessions.
 */

import type { Mission, Plan, Certificate, SimulationEvent, WorldState } from "../contracts/contracts";

const STORAGE_KEYS = {
  MISSION: "skywarden_mission_v1",
  PLAN: "skywarden_plan_v1",
  CERTIFICATE: "skywarden_certificate_v1",
  EVENTS: "skywarden_events_v1",
  WORLD: "skywarden_world_v1",
};

export interface PersistedSession {
  mission: Mission | null;
  plan: Plan | null;
  certificate: Certificate | null;
  events: SimulationEvent[];
  world: WorldState | null;
}

export function saveSessionToStorage(data: {
  mission: Mission;
  plan: Plan | null;
  certificate: Certificate | null;
  events: SimulationEvent[];
  world: WorldState;
}): void {
  try {
    localStorage.setItem(STORAGE_KEYS.MISSION, JSON.stringify(data.mission));
    if (data.plan) localStorage.setItem(STORAGE_KEYS.PLAN, JSON.stringify(data.plan));
    if (data.certificate) localStorage.setItem(STORAGE_KEYS.CERTIFICATE, JSON.stringify(data.certificate));
    localStorage.setItem(STORAGE_KEYS.EVENTS, JSON.stringify(data.events));
    localStorage.setItem(STORAGE_KEYS.WORLD, JSON.stringify(data.world));
  } catch (err) {
    console.warn("Storage persistence error:", err);
  }
}

export function loadSessionFromStorage(): PersistedSession | null {
  try {
    const rawMission = localStorage.getItem(STORAGE_KEYS.MISSION);
    if (!rawMission) return null;

    const mission = JSON.parse(rawMission) as Mission;
    const rawPlan = localStorage.getItem(STORAGE_KEYS.PLAN);
    const plan = rawPlan ? (JSON.parse(rawPlan) as Plan) : null;
    const rawCert = localStorage.getItem(STORAGE_KEYS.CERTIFICATE);
    const certificate = rawCert ? (JSON.parse(rawCert) as Certificate) : null;
    const rawEvents = localStorage.getItem(STORAGE_KEYS.EVENTS);
    const events = rawEvents ? (JSON.parse(rawEvents) as SimulationEvent[]) : [];
    const rawWorld = localStorage.getItem(STORAGE_KEYS.WORLD);
    const world = rawWorld ? (JSON.parse(rawWorld) as WorldState) : null;

    return { mission, plan, certificate, events, world };
  } catch (err) {
    console.warn("Could not load persisted session:", err);
    return null;
  }
}

export function clearPersistedSession(): void {
  try {
    localStorage.removeItem(STORAGE_KEYS.MISSION);
    localStorage.removeItem(STORAGE_KEYS.PLAN);
    localStorage.removeItem(STORAGE_KEYS.CERTIFICATE);
    localStorage.removeItem(STORAGE_KEYS.EVENTS);
    localStorage.removeItem(STORAGE_KEYS.WORLD);
  } catch (err) {
    console.warn("Could not clear storage:", err);
  }
}

export function exportAuditLogFile(events: SimulationEvent[], missionId: string): void {
  const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(events, null, 2));
  const downloadAnchor = document.createElement("a");
  downloadAnchor.setAttribute("href", dataStr);
  downloadAnchor.setAttribute("download", `skywarden_audit_${missionId}_${Date.now()}.json`);
  document.body.appendChild(downloadAnchor);
  downloadAnchor.click();
  downloadAnchor.remove();
}
