import React, { useState, useEffect } from "react";
import type {
  Mission,
  Plan,
  Waypoint,
  WorldState,
  SafetyPolicy,
  DroneState,
  VerificationResult,
  Certificate,
  SimulationEvent,
  Coordinate,
  RestrictedZone,
  GeoPolygon,
} from "./contracts/contracts";
import {
  INITIAL_DRONE_STATE,
  INITIAL_WORLD_STATE,
  INITIAL_MISSION,
  INITIAL_VALID_PLAN,
  DEFAULT_SAFETY_POLICY,
} from "./services/mockData";
import { verifyPlanClient, haversineDistanceM } from "./services/clientVerifier";
import { fetchOpenMeteoWeather } from "./services/weatherService";
import {
  saveSessionToStorage,
  loadSessionFromStorage,
  exportAuditLogFile,
} from "./services/storageService";
import { HeaderHUD } from "./components/HeaderHUD";
import { TacticalMap } from "./components/TacticalMap";
import { PlanReviewPanel } from "./components/PlanReviewPanel";
import { MissionSetupPanel } from "./components/MissionSetupPanel";
import { SimulationControls } from "./components/SimulationControls";
import { ResearchPanel } from "./components/ResearchPanel";
import { ScoreboardPanel } from "./components/ScoreboardPanel";
import { InterventionModal } from "./components/InterventionModal";
import {
  CheckSquare,
  Compass,
  Activity,
  Sparkles,
  Trophy,
} from "lucide-react";

export const App: React.FC = () => {
  // --- Core State ---
  const [mission, setMission] = useState<Mission>(INITIAL_MISSION);
  const [plan, setPlan] = useState<Plan | null>(INITIAL_VALID_PLAN);
  const [world, setWorld] = useState<WorldState>(INITIAL_WORLD_STATE);
  const [drone, setDrone] = useState<DroneState>(INITIAL_DRONE_STATE);
  const [policy] = useState<SafetyPolicy>(DEFAULT_SAFETY_POLICY);

  // --- Verification & Certificate State ---
  const [verificationResult, setVerificationResult] = useState<VerificationResult | null>(null);
  const [certificate, setCertificate] = useState<Certificate | null>(null);
  const [isVerifying, setIsVerifying] = useState(false);

  // --- Simulation & Live Event State ---
  const [isSimRunning, setIsSimRunning] = useState(false);
  const [simSpeed, setSimSpeed] = useState<number>(1);
  const [events, setEvents] = useState<SimulationEvent[]>([]);
  const [breadcrumbs, setBreadcrumbs] = useState<Coordinate[]>([[...INITIAL_DRONE_STATE.location]]);
  const [survivorLocation, setSurvivorLocation] = useState<Coordinate | null>(null);

  // --- Repair Policy & Intervention State (Decision A08) ---
  const [repairAttempts, setRepairAttempts] = useState<number>(0);
  const [interventionModalOpen, setInterventionModalOpen] = useState(false);
  const [interventionReason, setInterventionReason] = useState("");

  // --- Weather & Storage State ---
  const [isLiveWeather, setIsLiveWeather] = useState(false);

  // --- Active Right Panel Tab ---
  const [activeTab, setActiveTab] = useState<"review" | "setup" | "sim" | "research" | "scoreboard">("review");

  // Auto-persist session to local storage
  useEffect(() => {
    saveSessionToStorage({
      mission,
      plan,
      certificate,
      events,
      world,
    });
  }, [mission, plan, certificate, events, world]);

  // Toggle Open-Meteo Live Weather
  const handleToggleLiveWeather = async () => {
    if (isLiveWeather) {
      setIsLiveWeather(false);
      emitEvent("TELEMETRY_TICK", { weather: "MANUAL_SCENARIO_RESTORED" }, "SIMULATOR");
      return;
    }
    setIsLiveWeather(true);
    const weatherData = await fetchOpenMeteoWeather(37.4220, -122.0845);
    setWorld((w) => ({
      ...w,
      wind_speed_mps: weatherData.wind_speed_mps,
      wind_direction_deg: weatherData.wind_direction_deg,
      ambient_temperature_c: weatherData.temperature_c,
      weather_condition: weatherData.weather_condition,
    }));
    emitEvent(
      "TELEMETRY_TICK",
      {
        source: "OPEN_METEO_API",
        wind_mps: weatherData.wind_speed_mps,
        temp_c: weatherData.temperature_c,
        condition: weatherData.weather_condition,
      },
      "WEATHER_SENSOR"
    );
  };

  const handleExportAudit = () => {
    exportAuditLogFile(events, mission.mission_id);
  };

  // Helper to record an event
  const emitEvent = (
    eventType: SimulationEvent["event_type"],
    payload: any,
    source: SimulationEvent["source"] = "SIMULATOR"
  ) => {
    const newEvt: SimulationEvent = {
      event_id: `EVT-${(events.length + 1).toString().padStart(5, "0")}`,
      mission_id: mission.mission_id,
      event_type: eventType,
      payload,
      sim_time_s: drone.sim_time_s,
      sequence: events.length + 1,
      source,
      created_at: new Date().toISOString(),
    };
    setEvents((prev) => [...prev, newEvt]);
    return newEvt;
  };

  // Run Deterministic Verification
  const handleRunVerification = async () => {
    if (!plan) return;
    setIsVerifying(true);
    const { result, certificate: cert } = await verifyPlanClient(
      plan,
      mission,
      world,
      policy,
      drone
    );
    setVerificationResult(result);
    setCertificate(cert);
    setIsVerifying(false);

    if (cert && cert.is_valid) {
      setMission((m) => ({ ...m, status: "CERTIFIED" }));
      emitEvent("TELEMETRY_TICK", {
        status: "PLAN_CERTIFIED",
        digest: cert.plan_digest.slice(0, 16) + "...",
      });
    } else {
      setMission((m) => ({ ...m, status: "DRAFT" }));
      emitEvent("TELEMETRY_TICK", {
        status: "VERIFICATION_REJECTED",
        violations_count: result.violations.length,
      });
    }
  };

  // Run initial verification and load persisted session on mount
  useEffect(() => {
    const saved = loadSessionFromStorage();
    if (saved) {
      if (saved.mission) setMission(saved.mission);
      if (saved.plan) setPlan(saved.plan);
      if (saved.certificate) setCertificate(saved.certificate);
      if (saved.events && saved.events.length > 0) setEvents(saved.events);
      if (saved.world) setWorld(saved.world);
    }
    handleRunVerification();
  }, []);

  // Launch Flight (Only allowed if certified)
  const handleLaunchFlight = () => {
    if (!certificate || !certificate.is_valid) {
      alert("Cannot launch flight without an immutable safety certificate!");
      return;
    }
    setDrone((d) => ({
      ...d,
      is_airborne: true,
      velocity_mps: plan?.waypoints[0]?.speed_mps ?? 10.0,
      current_waypoint_index: 0,
    }));
    setMission((m) => ({ ...m, status: "ACTIVE" }));
    setIsSimRunning(true);
    emitEvent(
      "TELEMETRY_TICK",
      { message: "Mission launched under Certificate " + certificate.certificate_id },
      "OPERATOR"
    );
  };

  // Simulator discrete tick loop
  useEffect(() => {
    if (!isSimRunning || !drone.is_airborne || !plan) return;

    const interval = setInterval(() => {
      setDrone((prevDrone) => {
        const waypoints = plan.waypoints;
        const currIdx = prevDrone.current_waypoint_index;

        if (currIdx >= waypoints.length) {
          // Mission completed
          setIsSimRunning(false);
          setMission((m) => ({ ...m, status: "COMPLETED" }));
          emitEvent("MISSION_COMPLETED", {
            message: "All waypoints surveyed. Drone returned safely.",
          });
          return { ...prevDrone, is_airborne: false, velocity_mps: 0.0 };
        }

        const targetWp = waypoints[currIdx];
        const targetPos: [number, number] = [targetWp.longitude, targetWp.latitude];
        const currPos: [number, number] = [prevDrone.location[0], prevDrone.location[1]];

        const distM = haversineDistanceM(currPos, targetPos);
        const effectiveStep = targetWp.speed_mps * simSpeed;

        let nextLocation: [number, number];
        let nextIdx = currIdx;
        let nextAlt = prevDrone.altitude_agl_m;

        if (distM <= effectiveStep || distM < 2.0) {
          nextLocation = targetPos;
          nextIdx = currIdx + 1;
          nextAlt = targetWp.altitude_agl_m;
          emitEvent("WAYPOINT_REACHED", {
            waypoint_id: targetWp.waypoint_id,
            action: targetWp.action,
            altitude_agl_m: targetWp.altitude_agl_m,
          });
        } else {
          const ratio = effectiveStep / distM;
          nextLocation = [
            currPos[0] + (targetPos[0] - currPos[0]) * ratio,
            currPos[1] + (targetPos[1] - currPos[1]) * ratio,
          ];
          const altDiff = targetWp.altitude_agl_m - prevDrone.altitude_agl_m;
          nextAlt += altDiff * Math.min(1.0, ratio * 2.0);
        }

        // Heading calculation
        const dLon = targetPos[0] - currPos[0];
        const dLat = targetPos[1] - currPos[1];
        const headingDeg = (Math.atan2(dLon, dLat) * (180 / Math.PI) + 360) % 360;

        // Battery model
        const powerW = 120.0 + Math.pow(world.wind_speed_mps, 1.5) * 4.0;
        const energyUsedWh = (powerW * simSpeed) / 3600.0;
        const nextWh = Math.max(0, prevDrone.battery_wh - energyUsedWh);
        const nextPct = Math.max(0, (nextWh / 100.0) * 100.0);

        setBreadcrumbs((crumbs) => [...crumbs, nextLocation]);

        return {
          ...prevDrone,
          location: nextLocation,
          altitude_agl_m: nextAlt,
          velocity_mps: targetWp.speed_mps,
          heading_deg: headingDeg,
          sim_time_s: prevDrone.sim_time_s + simSpeed,
          current_waypoint_index: nextIdx,
          battery_wh: nextWh,
          battery_pct: nextPct,
        };
      });
    }, 1000 / simSpeed);

    return () => clearInterval(interval);
  }, [isSimRunning, drone.is_airborne, plan, simSpeed, world.wind_speed_mps]);

  // Scenario Switcher
  const handleSelectScenario = (scenarioId: string) => {
    setIsSimRunning(false);
    setSurvivorLocation(null);
    setRepairAttempts(0);
    setInterventionModalOpen(false);

    if (scenarioId === "scenario_flood") {
      setMission(INITIAL_MISSION);
      setPlan(INITIAL_VALID_PLAN);
      setWorld(INITIAL_WORLD_STATE);
      setDrone(INITIAL_DRONE_STATE);
      setBreadcrumbs([[...INITIAL_DRONE_STATE.location]]);
    } else if (scenarioId === "scenario_wind") {
      setWorld({ ...INITIAL_WORLD_STATE, wind_speed_mps: 15.2 });
      setPlan(INITIAL_VALID_PLAN);
      setDrone(INITIAL_DRONE_STATE);
    } else if (scenarioId === "scenario_geofence") {
      const outOfBoundsPlan: Plan = {
        ...INITIAL_VALID_PLAN,
        plan_id: "PLN-INVAL-GEOFENCE",
        waypoints: [
          ...INITIAL_VALID_PLAN.waypoints,
          {
            waypoint_id: "WP-BREACH",
            longitude: -122.0650,
            latitude: 37.4350,
            altitude_agl_m: 45.0,
            speed_mps: 10.0,
            action: "SURVEY",
          },
        ],
      };
      setPlan(outOfBoundsPlan);
      setWorld(INITIAL_WORLD_STATE);
    } else if (scenarioId === "scenario_hazard") {
      const hazardBreachPlan: Plan = {
        ...INITIAL_VALID_PLAN,
        plan_id: "PLN-INVAL-HAZARD",
        waypoints: [
          ...INITIAL_VALID_PLAN.waypoints.slice(0, 2),
          {
            waypoint_id: "WP-HAZARD",
            longitude: -122.0820,
            latitude: 37.4234,
            altitude_agl_m: 45.0,
            speed_mps: 10.0,
            action: "SURVEY",
          },
          ...INITIAL_VALID_PLAN.waypoints.slice(2),
        ],
      };
      setPlan(hazardBreachPlan);
      setWorld(INITIAL_WORLD_STATE);
    }

    setTimeout(() => handleRunVerification(), 100);
  };

  // Generate Plan
  const handleGeneratePlan = (altitudeAg: number, speedMps: number) => {
    const surveyCoords = mission.survey_area.coordinates[0];
    const minLon = Math.min(...surveyCoords.map((c) => c[0]));
    const maxLon = Math.max(...surveyCoords.map((c) => c[0]));
    const minLat = Math.min(...surveyCoords.map((c) => c[1]));
    const maxLat = Math.max(...surveyCoords.map((c) => c[1]));

    const latStep = (maxLat - minLat) / 3;
    const generatedWps: Waypoint[] = [
      {
        waypoint_id: "WP-01",
        longitude: minLon + 0.0005,
        latitude: minLat + 0.0005,
        altitude_agl_m: altitudeAg,
        speed_mps: speedMps,
        action: "TRANSIT",
      },
      {
        waypoint_id: "WP-02",
        longitude: maxLon - 0.0005,
        latitude: minLat + 0.0005,
        altitude_agl_m: altitudeAg,
        speed_mps: speedMps,
        action: "SURVEY",
      },
      {
        waypoint_id: "WP-03",
        longitude: maxLon - 0.0005,
        latitude: minLat + latStep,
        altitude_agl_m: altitudeAg,
        speed_mps: speedMps,
        action: "SURVEY",
      },
      {
        waypoint_id: "WP-04",
        longitude: minLon + 0.0005,
        latitude: minLat + latStep,
        altitude_agl_m: altitudeAg,
        speed_mps: speedMps,
        action: "SURVEY",
      },
      {
        waypoint_id: "WP-05",
        longitude: minLon + 0.0005,
        latitude: minLat + latStep * 2,
        altitude_agl_m: altitudeAg,
        speed_mps: speedMps,
        action: "SURVEY",
      },
      {
        waypoint_id: "WP-06",
        longitude: drone.home_position[0],
        latitude: drone.home_position[1],
        altitude_agl_m: 25.0,
        speed_mps: 8.0,
        action: "RETURN_HOME",
      },
    ];

    const newPlan: Plan = {
      schema_version: "1.0.0",
      plan_id: `PLN-GEN-${Date.now().toString().slice(-4)}`,
      mission_id: mission.mission_id,
      revision: 1,
      waypoints: generatedWps,
      provenance: {
        planner_type: "DETERMINISTIC_GRID",
        repair_attempt: 0,
      },
      estimated_duration_s: 360.0,
      estimated_energy_wh: 34.0,
      created_at: new Date().toISOString(),
    };

    setPlan(newPlan);
    setCertificate(null);
    setVerificationResult(null);
    setActiveTab("review");
  };

  // Trigger Repair Loop (Decision A08: Max 3 Attempts)
  const handleTriggerRepair = () => {
    const nextAttempt = repairAttempts + 1;
    setRepairAttempts(nextAttempt);

    if (nextAttempt > 3) {
      setInterventionReason("Automatic repair attempt cap (3 attempts) reached without safety convergence.");
      setInterventionModalOpen(true);
      setMission((m) => ({ ...m, status: "INTERVENTION_REQUIRED" }));
      emitEvent("OPERATOR_MISSION_CHANGE", {
        status: "INTERVENTION_REQUIRED",
        reason: "Repair attempt limit of 3 exceeded.",
      });
      return;
    }

    if (!plan) return;

    // Apply deterministic repair: shift any violating points, lower wind if needed, clamp speeds
    let repairedWaypoints = plan.waypoints.map((wp) => {
      let lon = wp.longitude;
      let lat = wp.latitude;
      // Clamp into survey area bounds
      lon = Math.max(-122.0848, Math.min(-122.0802, lon));
      lat = Math.max(37.4218, Math.min(37.4252, lat));

      // Avoid hazard zone
      if (lon > -122.0828 && lon < -122.0812 && lat > 37.4228 && lat < 37.4240) {
        lon = -122.0835;
      }

      return {
        ...wp,
        longitude: lon,
        latitude: lat,
        altitude_agl_m: Math.max(25.0, Math.min(80.0, wp.altitude_agl_m)),
        speed_mps: Math.min(12.0, wp.speed_mps),
      };
    });

    // Reset world wind if it was the issue
    if (world.wind_speed_mps > 12.0) {
      setWorld((w) => ({ ...w, wind_speed_mps: 8.5 }));
    }

    const repairedPlan: Plan = {
      ...plan,
      revision: plan.revision + 1,
      waypoints: repairedWaypoints,
      provenance: {
        planner_type: "REPAIR_LOOP",
        repair_attempt: nextAttempt,
      },
    };

    setPlan(repairedPlan);
    emitEvent(
      "OPERATOR_MISSION_CHANGE",
      {
        action: "AUTO_REPAIR_APPLIED",
        attempt: nextAttempt,
        revision: repairedPlan.revision,
      },
      "SIMULATOR"
    );

    setTimeout(() => handleRunVerification(), 150);
  };

  // --- Seeded Event Injections (5 Approved Trigger Families) ---

  const handleInjectSurvivor = () => {
    const loc: Coordinate = [-122.0834, 37.4239];
    setSurvivorLocation(loc);
    emitEvent(
      "SURVIVOR_DETECTED",
      {
        detection_id: "DET-094",
        location: loc,
        confidence: 0.94,
        source: "AI_FORWARD_VISION",
      },
      "AI_DETECTOR"
    );
  };

  const handleInjectLowBattery = () => {
    setDrone((d) => ({
      ...d,
      battery_pct: 18.0,
      battery_wh: 18.0,
    }));
    emitEvent(
      "LOW_BATTERY",
      {
        current_battery_pct: 18.0,
        remaining_wh: 18.0,
        threshold_pct: 20.0,
        warning: "Battery below mandatory 20% reserve.",
      },
      "SIMULATOR"
    );
  };

  const handleInjectWindSpike = () => {
    setWorld((w) => ({
      ...w,
      wind_speed_mps: 14.8,
    }));
    emitEvent(
      "WIND_SPIKE",
      {
        observed_speed_mps: 14.8,
        gust_speed_mps: 18.2,
        limit_mps: 12.0,
      },
      "WEATHER_SENSOR"
    );
    // Invalidate certificate on wind spike
    if (certificate) {
      setCertificate({
        ...certificate,
        is_valid: false,
        invalidation_reason: "Ambient wind spike (14.8 m/s) exceeded policy envelope.",
      });
    }
  };

  const handleInjectNewRestrictedZone = () => {
    const newZone: RestrictedZone = {
      zone_id: "ZONE-SURGE-02",
      name: "Emergency Flood Surge Channel",
      boundary: {
        type: "Polygon",
        coordinates: [
          [
            [-122.0840, 37.4225],
            [-122.0830, 37.4225],
            [-122.0830, 37.4235],
            [-122.0840, 37.4235],
            [-122.0840, 37.4225],
          ] as Coordinate[],
        ],
      },
      buffer_m: 25.0,
      active: true,
    };
    setWorld((w) => ({
      ...w,
      restricted_zones: [...w.restricted_zones, newZone],
      world_revision: w.world_revision + 1,
    }));
    emitEvent(
      "NEW_RESTRICTED_ZONE",
      {
        zone_id: newZone.zone_id,
        name: newZone.name,
      },
      "OPERATOR"
    );
  };

  const handleInjectOperatorChange = () => {
    const expandedArea: GeoPolygon = {
      type: "Polygon",
      coordinates: [
        [
          [-122.0860, 37.4210],
          [-122.0790, 37.4210],
          [-122.0790, 37.4260],
          [-122.0860, 37.4260],
          [-122.0860, 37.4210],
        ] as Coordinate[],
      ],
    };
    setMission((m) => ({ ...m, survey_area: expandedArea }));
    emitEvent(
      "OPERATOR_MISSION_CHANGE",
      {
        change: "EXPAND_SURVEY_SECTOR",
        operator: "Lead SAR Coordinator",
      },
      "OPERATOR"
    );
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", minHeight: "100vh", backgroundColor: "#070a13" }}>
      {/* Top HUD Telemetry & Navigation */}
      <HeaderHUD
        mission={mission}
        drone={drone}
        world={world}
        certificate={certificate}
        isSimRunning={isSimRunning}
        simSpeed={simSpeed}
        isLiveWeather={isLiveWeather}
        onToggleSim={() => setIsSimRunning(!isSimRunning)}
        onChangeSpeed={setSimSpeed}
        onResetSim={() => handleSelectScenario("scenario_flood")}
        onSelectScenario={handleSelectScenario}
        onToggleLiveWeather={handleToggleLiveWeather}
        onExportAudit={handleExportAudit}
      />

      {/* Main Command & Control Layout */}
      <main
        style={{
          flex: 1,
          display: "grid",
          gridTemplateColumns: "1.15fr 0.85fr",
          gap: "16px",
          padding: "16px",
          overflow: "hidden",
        }}
      >
        {/* Left Column: Interactive Tactical Map */}
        <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
          <TacticalMap
            mission={mission}
            plan={plan}
            world={world}
            drone={drone}
            survivorLocation={survivorLocation}
            breadcrumbs={breadcrumbs}
          />
        </div>

        {/* Right Column: Tabbed Command & Control Center */}
        <div style={{ display: "flex", flexDirection: "column", gap: "12px", overflowY: "auto", maxHeight: "calc(100vh - 100px)" }}>
          {/* Tab Navigation Buttons */}
          <div
            className="glass-panel"
            style={{
              padding: "4px",
              display: "flex",
              gap: "4px",
              border: "1px solid rgba(255, 255, 255, 0.1)",
            }}
          >
            <button
              className="btn"
              style={{
                flex: 1,
                fontSize: "0.8rem",
                background: activeTab === "review" ? "rgba(0, 229, 255, 0.2)" : "transparent",
                color: activeTab === "review" ? "#00e5ff" : "#94a3b8",
                border: "none",
              }}
              onClick={() => setActiveTab("review")}
            >
              <CheckSquare size={14} />
              Safety Gate
            </button>

            <button
              className="btn"
              style={{
                flex: 1,
                fontSize: "0.8rem",
                background: activeTab === "setup" ? "rgba(0, 229, 255, 0.2)" : "transparent",
                color: activeTab === "setup" ? "#00e5ff" : "#94a3b8",
                border: "none",
              }}
              onClick={() => setActiveTab("setup")}
            >
              <Compass size={14} />
              Mission Setup
            </button>

            <button
              className="btn"
              style={{
                flex: 1,
                fontSize: "0.8rem",
                background: activeTab === "sim" ? "rgba(0, 229, 255, 0.2)" : "transparent",
                color: activeTab === "sim" ? "#00e5ff" : "#94a3b8",
                border: "none",
              }}
              onClick={() => setActiveTab("sim")}
            >
              <Activity size={14} />
              Triggers & Stream
            </button>

            <button
              className="btn"
              style={{
                flex: 1,
                fontSize: "0.8rem",
                background: activeTab === "research" ? "rgba(0, 229, 255, 0.2)" : "transparent",
                color: activeTab === "research" ? "#00e5ff" : "#94a3b8",
                border: "none",
              }}
              onClick={() => setActiveTab("research")}
            >
              <Sparkles size={14} />
              Tavily Intel
            </button>

            <button
              className="btn"
              style={{
                flex: 1,
                fontSize: "0.8rem",
                background: activeTab === "scoreboard" ? "rgba(0, 229, 255, 0.2)" : "transparent",
                color: activeTab === "scoreboard" ? "#00e5ff" : "#94a3b8",
                border: "none",
              }}
              onClick={() => setActiveTab("scoreboard")}
            >
              <Trophy size={14} />
              Scoreboard
            </button>
          </div>

          {/* Active Tab Panel Content */}
          {activeTab === "review" && (
            <PlanReviewPanel
              plan={plan}
              mission={mission}
              verificationResult={verificationResult}
              certificate={certificate}
              isVerifying={isVerifying}
              onRunVerification={handleRunVerification}
              onLaunchFlight={handleLaunchFlight}
              onTriggerRepair={handleTriggerRepair}
            />
          )}

          {activeTab === "setup" && (
            <MissionSetupPanel
              mission={mission}
              onUpdateMission={setMission}
              onGeneratePlan={handleGeneratePlan}
            />
          )}

          {activeTab === "sim" && (
            <SimulationControls
              events={events}
              onInjectSurvivor={handleInjectSurvivor}
              onInjectLowBattery={handleInjectLowBattery}
              onInjectWindSpike={handleInjectWindSpike}
              onInjectNewRestrictedZone={handleInjectNewRestrictedZone}
              onInjectOperatorChange={handleInjectOperatorChange}
            />
          )}

          {activeTab === "research" && <ResearchPanel />}

          {activeTab === "scoreboard" && <ScoreboardPanel />}
        </div>
      </main>

      {/* Operator Intervention Modal (Decision A08 Enforced) */}
      <InterventionModal
        isOpen={interventionModalOpen}
        attemptCount={repairAttempts}
        reason={interventionReason}
        onReturnHome={() => {
          setInterventionModalOpen(false);
          setIsSimRunning(true);
          emitEvent("WAYPOINT_REACHED", { action: "OPERATOR_ORDERED_RTH" }, "OPERATOR");
        }}
        onResetAndModify={() => {
          setRepairAttempts(0);
          setInterventionModalOpen(false);
          setActiveTab("setup");
        }}
        onAbortMission={() => {
          setInterventionModalOpen(false);
          setIsSimRunning(false);
          setDrone((d) => ({ ...d, is_airborne: false, velocity_mps: 0 }));
          setMission((m) => ({ ...m, status: "ABORTED" }));
          emitEvent("MISSION_COMPLETED", { status: "OPERATOR_ABORTED" }, "OPERATOR");
        }}
      />
    </div>
  );
};

export default App;
