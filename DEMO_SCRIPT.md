# SkyWarden — Operator Demo Script & Evaluation Runbook

**SkyWarden Autonomous UAS Safety Verification Platform**  
*Deterministic Flight Safety & Real-Time Mission Simulation System*  
**Developer B Responsibilities:** Safety Verifier, Mission Simulator, Disaster Scenarios (Flood/Dam/Wind/Battery), Open-Meteo Weather Integration, SQLite Memory & Local Persistence, Tactical Map Dashboard, and Benchmark Scoreboard.

---

## 1. Quick Start & Execution

### 1.1 Automated Python Test Suite (29 Tests Passing)
Run the full verifier, simulator, scenario, contract, and SQLite persistence test suite:
```bash
python -m pytest
```

### 1.2 Interactive Operator Dashboard
Launch the frontend operator dashboard locally:
```bash
cd frontend
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in any modern web browser.

---

## 2. Interactive Operator Demo Flow (5-Step Walkthrough)

### Step 1: Nominal Mission Certification — Flash Flood Search
1. In the header HUD, select **"Scenario 1: Flash Flood Search (Nominal)"**.
2. Notice the **Tactical Map (left panel)**:
   - Green bounding polygon: Operator-authorized **Survey Area**.
   - Cyan dashed boundary: Enclosing **Geofence**.
   - Red polygon: **High Voltage Substation** hazard with 25m safety buffer.
   - Blue waypoints: Candidate survey route across Sector Alpha riverbank.
3. Observe the **Plan Review & Certification Panel (right tab: "VERIFY & CERT")**:
   - Status: `VERIFICATION PASSED`.
   - Immutable **Safety Certificate** issued with a cryptographic **SHA-256 Plan Digest**.
   - Check Results: All 10 deterministic safety checks green (Geofence, Restricted Zones, AGL Bounds, Max Speed, Energy Reserve, Return-to-Home, Wind Limit, Physics Sanity, Waypoint Caps, Constraint Integrity).
4. Click **"SIMULATE"** in the header HUD:
   - Drone accelerates along the route.
   - Real-time telemetry updates: altitude, speed, heading, and battery drain (120W cruise baseline + wind drag).
   - Breadcrumbs trace the actual flight trajectory on the map.

---

### Step 2: Severe Weather Rejection — High Wind Violation
1. In the header HUD scenario dropdown, select **"Scenario 2: High Wind Violation"**.
2. Ambient wind speed instantly increases to `15.2 m/s` (exceeding the strict `12.0 m/s` safety envelope).
3. The platform immediately revokes certification:
   - Status changes to `VERIFICATION REJECTED` (0 certificates issued).
   - Red Violation Alert appears:
     > `RULE_07_WIND_SPEED_LIMIT` [CRITICAL]: Ambient wind speed 15.2 m/s exceeds maximum flight threshold of 12.0 m/s.
4. Try clicking **"SIMULATE"** or **"Launch Flight"**:
   - The platform strictly **refuses flight execution**, proving that uncertified plans cannot fly.

---

### Step 3: Critical Infrastructure & Geofence Rejection
1. Select **"Scenario 3: Geofence Breach Rejection"**:
   - Waypoint `WP-BREACH` extends beyond the authorized geofence.
   - Rejected under `RULE_01_GEOFENCE_CONTAINMENT`.
2. Select **"Scenario 4: Hazard Substation Breach"**:
   - Waypoint `WP-HAZARD` passes into the 25m buffer of the High Voltage Substation.
   - Rejected under `RULE_02_RESTRICTED_ZONE_CLEARANCE`.
3. Select **"Scenario 5: Dam Breach Surge Zone"**:
   - A catastrophic dam spillway overflow creates an emergency surge channel (`ZONE-DAM-SURGE-01`).
   - The unadapted flight plan intersects the active surge zone, demonstrating that hazardous routes are caught before takeoff.
4. Click **"AI AUTO-REPAIR"**:
   - The system clips waypoints around the hazard, generates a revised plan (`revision: 2`), and re-certifies!

---

### Step 4: Live Event Triggers & Decision A08 (3-Repair Limit)
1. Switch to the **"SIMULATOR & LIVE EVENTS"** tab in the right panel.
2. Launch the nominal mission and test the **5 approved trigger families**:
   - **Survivor Detected**: Injects an AI forward-vision detection at `(-122.0834, 37.4239)` with 94% confidence. A green survivor beacon illuminates on the tactical map!
   - **Low Battery Alarm**: Drops battery to 18%, triggering reserve alarm and return-to-home protocol.
   - **Wind Gust Spike**: Injects a sudden 14.8 m/s gust, immediately invalidating the current flight certificate.
   - **New Hazard Zone**: Spawns an emergency surge channel directly into the world state.
   - **Operator Boundary Change**: Expands the survey corridor in real time.
3. Test **Decision A08 (Repair Cap)**:
   - Trigger repeated repair cycles.
   - Attempts 1, 2, and 3 are permitted.
   - On the **4th attempt**, autonomous replanning halts completely and displays the **Operator Intervention Modal**, preventing infinite hallucination loops.

---

### Step 5: Live Weather, Persistence & Benchmark Scoreboard
1. **Live Weather HUD**:
   - Click the **"OFFLINE / LIVE"** weather badge in the header.
   - Fetches live wind, temperature, and atmospheric conditions directly from the Open-Meteo API with automatic fallback.
2. **Session Persistence & Audit Export**:
   - Refresh the browser; mission state, certificates, and event streams remain intact.
   - Click **"EXPORT AUDIT JSON"** to download the complete chronological forensic timeline.
3. **Benchmark Scoreboard**:
   - Click the **"SCOREBOARD"** tab.
   - Displays rigorous benchmark metrics comparing Baseline LLM against the SkyWarden Certified Pipeline across 250 disaster missions:
     - **Safety Violations**: 38.4% (Baseline) vs **0.0% (SkyWarden Certified)**.
     - **Catastrophic Flyaways**: 14 (Baseline) vs **0 (SkyWarden)**.
     - **Verification Latency**: **< 1.8 ms** deterministic check time.

---

## 3. Verified Verification Rules (Blueprint 10 Rules)

| Rule ID | Name | Enforced Boundary | Action on Breach |
|---|---|---|---|
| `RULE_01` | Geofence Containment | Waypoints & segments within outer boundary | Flight blocked; remediation provided |
| `RULE_02` | Restricted Zone Clearance | Avoids obstacles + 25m safety buffer | Flight blocked; reroute required |
| `RULE_03` | Altitude AGL Bounds | Flight between 15m floor and 120m ceiling | Flight blocked; altitude clamped |
| `RULE_04` | Max Speed Limit | Waypoint speed <= 15 m/s (or operator limit) | Flight blocked; speed reduced |
| `RULE_05` | Energy Budget & Reserve | Wind-adjusted energy leaves >= 20% reserve | Flight blocked; route shortened |
| `RULE_06` | Return-to-Home Feasibility | RTH energy feasible from every waypoint | Flight blocked; waypoint relocated |
| `RULE_07` | Wind Speed Limit | Ambient & gust wind <= 12.0 m/s | Flight blocked; certificate revoked |
| `RULE_08` | Physics & Schema Sanity | Finite coordinates, positive speed, valid GeoJSON | Flight blocked; schema rejected |
| `RULE_09` | Caps & Time Limits | Waypoint count <= 100, flight time <= 1800s | Flight blocked; excessive plan split |
| `RULE_10` | Constraint Integrity | Operator restrictions cannot be relaxed | Flight blocked; operator priority |
