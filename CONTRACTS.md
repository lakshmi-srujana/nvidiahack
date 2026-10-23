# SkyWarden — Shared Interface Contracts

**Repository target:** `lakshmi-srujana/nvidiahack`  
**File:** `CONTRACTS.md` (independent of `projectplan.md`)  
**Document status:** **PRE-FREEZE / REVIEW REQUIRED**  
**Prepared:** 2026-10-24  
**Target contract release:** `v1.0.0` *after both developers approve remaining field-level and behavioral decisions*.

> **Do not treat the tables tagged PROPOSED as frozen code.** The 11 design decisions below were expressly approved. The 16 follow-up recommendations were offered by the assistant but have not yet received explicit approval. This document avoids silently turning those recommendations into implementation requirements.

## 1. Purpose and authority

This file specifies the boundary between (A) the AI/backend developer and (B) the verifier/simulator/frontend developer. **Both teams implement from a single source of truth.** After the freeze, Pydantic v2 models will be canonical, exported JSON Schemas and generated TypeScript types will be derived artifacts, and CI will detect drift.

- **Developer A — AI/backend:** Nebius/NVIDIA model client; model tiering and usage logging; mission parser; planner and verify/repair integration; event-driven Nano replanner; Tavily retrieval and untrusted-content sanitation; adversarial attack generation; benchmark runner/Serverless Jobs/scoreboard data API; FastAPI/WebSocket integration and backend deployment.
- **Developer B — safety/simulation/product:** Deterministic verifier and tests; safety certificates; simulator/world/telemetry, flood/dam/wind/battery scenarios; Open-Meteo weather and SQLite memory; generation of simulator events; map/dashboard/verification/certificate viewers and scoreboard UI; frontend deployment and demo video.
- **Shared:** schema review, integration tests, acceptance criteria, permissions and execution safety. Neither side invents different field names, enum values, coordinate conventions, error semantics, or defaults.

## 2. Approved design decisions — BINDING

The following **11 decisions are approved**:

| ID | Approved decision |
|---|---|
| A01 | One simulated drone and one active mission in v1. |
| A02 | External positions use **WGS84 longitude/latitude**; distances are calculated in metres. |
| A03 | Flight altitude uses **metres AGL** (above ground level). |
| A04 | The sole v1 mission capability is **survey a specified area**. |
| A05 | Safety authority comes from **trusted drone/environment configuration plus operator-approved mission restrictions**. |
| A06 | Waypoints specify **position, altitude, speed**, and may specify **action and dwell time**. |
| A07 | Replanning-relevant events: **survivor detected, low battery, wind spike, operator changes mission, new restricted zone**. |
| A08 | **At most three repair attempts**, then reject/request operator intervention. |
| A09 | **Safety certificates are issued only after mandatory checks pass**; unsuccessful candidates receive violation reports instead. |
| A10 | **Pydantic v2** canonical models → exported JSON Schema → generated TypeScript types. |
| A11 | In addition to the six named contracts, define shared **DroneState, WorldState, SafetyPolicy, VerificationResult** support contracts. |

### Boundaries the approved decisions already imply

- The LLM returns **candidate plans**, not actuator/motor commands.
- Validation and safety checks are the simulator/verifier developer's responsibility; planner/repair consumes the returned structured result.
- Survey-only does **not** grant permission to autonomously divert into rescue operations.
- The exact numeric airframe constraints, geometry buffers, waypoint action enum, event payload fields, coverage metric, execution lifecycle and emergency policies remain undecided until approved.

## 3. Contract inventory and dataflow

| Contract | Primary producer | Consumer(s) | Purpose | Status |
|---|---|---|---|---|
| `Mission` | AI parser, after operator input | Planner, verifier, dashboard | Authorized survey objective and restrictions | Design approved; **field names PROPOSED** |
| `Plan` | AI planner/repair/replanner | Verifier, simulator, UI | Candidate route for a mission | Design approved; **field names PROPOSED** |
| `Waypoint` | AI planner/repair/replanner | Verifier, simulator, UI | Individual planned point/action | Attributes approved; **field names PROPOSED** |
| `Violation` | Deterministic verifier | Repair loop, API, UI, benchmarks | Structured failed safety check | Existence approved; **field names PROPOSED** |
| `Certificate` | Deterministic verifier/certificate issuer | Executor, dashboard, benchmarks | Evidence of passing verification | Issuance rule approved; **field names PROPOSED** |
| `SimulationEvent` | Simulator/operator adapters | AI replanner, logger, UI | Trigger for safe re-evaluation | Event families approved; **payloads PROPOSED** |
| `DroneState` | Simulator | Planner, verifier, replan, dashboard | Telemetry and battery/position state | Supporting type approved; **fields PROPOSED** |
| `WorldState` | Simulator + weather context adapter | Planner, verifier, UI | Zones, environment and world revision | Supporting type approved; **fields PROPOSED** |
| `SafetyPolicy` | Trusted configuration/operator-approval boundary | Verifier, runtime controller | Enforceable constraints | Supporting type approved; **fields and precedence PROPOSED** |
| `VerificationResult` | Verifier | AI repair, simulator gate, UI, benchmark | Aggregate pass/fail result | Supporting type approved; **fields PROPOSED** |

**Intended flow:** operator → parser → `Mission` → planner → candidate `Plan[Waypoint]` → verifier(`SafetyPolicy`, `DroneState`, `WorldState`) → `VerificationResult[Violation]`; if rejected, AI repairs (≤3 attempts); if passed, issue `Certificate` → simulator; events → validate current situation → Nano replanner/appropriate contingency → verifier again.

## 4. Proposed field specifications — REVIEW, NOT FROZEN

The following names establish a concrete *review surface*, **not approved wire names**. Requiredness and exact constraints must be decided at freeze. Types are illustrative Pydantic/JSON meanings, not runnable model definitions.

### 4.1 `Mission` — AI/backend owns production

| Candidate field | Candidate type | Meaning / open point |
|---|---|---|
| `schema_version` | string | Contract version; exact versioning strategy pending. |
| `mission_id` | string | Unique identity; UUIDv4 proposed, unapproved. |
| `objective_type` | enum | Survey-area only in v1; exact enum literal pending. |
| `survey_area` | geographic polygon | Operator-approved area; `Polygon` GeoJSON proposed, unapproved. |
| `operator_instruction` | string | Original untrusted natural-language request for traceability; **not safety authority**. |
| `operator_restrictions` | structured object | Additional operator-approved restrictions; schema/precedence pending. |
| `created_at` | timestamp | UTC ISO-8601 proposed; pending. |
| `approval_ref` | string or object | Authorization of restrictions; whether required pending. |

**Required invariants:** Objective is survey-area only; geographic order and geometry must be unambiguous; no Tavily text or LLM free text may override trusted safety configuration.

### 4.2 `Waypoint` — AI/backend produces, verifier/simulator consumes

| Candidate field | Candidate type | Meaning / open point |
|---|---|---|
| `waypoint_id` | string | Stable identity within a plan; scheme pending. |
| `longitude` | float | WGS84 longitude; expected range [-180, 180]. |
| `latitude` | float | WGS84 latitude; expected range [-90, 90]. |
| `altitude_agl_m` | finite nonnegative number | Height above simulated terrain; minimum/maximum from policy, not guessed. |
| `speed_mps` | finite positive number | Planned speed; final wire name/units convention pending. |
| `action` | optional enum | Exact action set pending; proposal: TRANSIT/SURVEY/HOVER/RETURN_HOME. |
| `dwell_s` | optional nonnegative number | Stationary action time; whether null/omission differs pending. |

**Required invariants:** No NaN/Infinity; verifier checks route *segments* and not just points; AGL is not a GeoJSON Z-coordinate. Exact handling of waypoint action defaults is unapproved.

### 4.3 `Plan` — AI/backend produces, verifier approves/rejects

| Candidate field | Candidate type | Meaning / open point |
|---|---|---|
| `plan_id` | string | Candidate plan identity. |
| `mission_id` | string | Foreign key to authorized `Mission`. |
| `revision` | integer | Increases on repair/replan; numbering convention pending. |
| `waypoints` | array of `Waypoint` | Ordered route, including start/home semantics to be decided. |
| `state_ref` | structured reference | World/drone snapshots used during planning; exact model pending. |
| `generated_by` | model provenance | Model/tier and trigger reason; shape pending. |
| `estimated_duration_s` | number | Optional AI estimate; verifier owns authoritative feasibility check. |
| `estimated_energy_wh` | number | Optional AI estimate; verifier recomputes. |

**Required invariants:** A new or altered route is a new candidate needing verification; no execution on an unverified plan; no direct low-level motor commands.

### 4.4 `Violation` — verifier produces, AI repairs from it

| Candidate field | Candidate type | Meaning / open point |
|---|---|---|
| `rule_id` | enum/string | Stable machine-readable rule identifier. |
| `message` | string | Human-readable explanation. |
| `observed` | typed value | Actual value/geometry implicated; structure pending. |
| `limit` | typed value | Applicable policy threshold or boundary; structure pending. |
| `unit` | optional string | Explicit units when numeric; enum pending. |
| `waypoint_refs` | array of identifiers | Related waypoint(s), if applicable. |
| `severity` | optional enum | Distinguish mandatory failures/advisories only if approved. |

**Required invariants:** A failed candidate returns actionable, structured failures; do not rely on prose matching to drive repairs.

### 4.5 `VerificationResult` — verifier aggregate

| Candidate field | Candidate type | Meaning / open point |
|---|---|---|
| `plan_id` | string | Plan examined. |
| `policy_ref` | string/object | Safety policy version/snapshot. |
| `world_ref` / `drone_ref` | structured refs | Evidence of assumptions tested. |
| `passed` | bool | True only if **all mandatory checks** pass. |
| `checks` | array | Complete list of checks, including passes; exact result type pending. |
| `violations` | array of `Violation` | Failed checks; should be empty for a pass. |
| `verified_at` | timestamp | Provenance; clock convention pending. |

**Required invariants:** The LLM cannot produce or alter authoritative verifier results; plan execution is blocked on failure.

### 4.6 `Certificate` — verifier/certificate component issues on PASS only

| Candidate field | Candidate type | Meaning / open point |
|---|---|---|
| `certificate_id` | string | Unique identity. |
| `mission_id`, `plan_id` | strings | Exact target of approval. |
| `verification_ref` | string/object | Links to passing `VerificationResult`. |
| `plan_digest` | optional hash | Proposed SHA-256 digest for audit/integrity; unapproved. |
| `policy_ref`, `world_ref` | structured refs | Snapshot binding proposal; unapproved. |
| `issued_at` | timestamp | Issue time. |
| `rule_results` | array | Checked rules, evidence and verdict; exact representation pending. |

**Required invariants:** No certificate for a failing candidate; a certificate proves only the implemented rules and assumptions, not real-world flight safety.

### 4.7 `SimulationEvent` — simulator/operator adapter produces

| Candidate field | Candidate type | Meaning / open point |
|---|---|---|
| `event_id` | string | Unique event/deduplication identifier, proposed. |
| `mission_id` | string | Current mission. |
| `event_type` | enum | Five approved trigger families; literal names pending. |
| `payload` | discriminated object | Specific event details; see below. |
| `sim_time_s` | number | Simulated monotonic time, proposed. |
| `sequence` | integer | Simulator order, proposed. |
| `source` | enum/string | Trusted source kind; semantics pending. |

**Approved event families; candidate payloads:**

| Event family (approved) | Proposed typed data (not approved) | Safety question |
|---|---|---|
| Survivor detected | GPS location, detection ID, confidence, source | Record/continue, divert, or operator approval? **Survey-only limits action.** |
| Low battery | remaining Wh/%; current GPS; return energy estimate | At what threshold does deterministic contingency supersede AI? |
| Wind spike | wind vector/speed and observation time | What limit and how is it enforced during execution? |
| Operator changes mission | signed/approved replacement survey area/restrictions; revision | Approval authority and permitted change types? |
| New restricted zone | GeoJSON polygon, effective time, trusted approval | Source of authority and zone buffer? |

**Cloud link-loss:** *not included* in the five approved replanning events. It is mentioned in the blueprint/dashboard scope; recommended to model it as an independent connectivity/safety state. **Not approved yet.**

### 4.8 `DroneState`, `WorldState`, `SafetyPolicy` — supporting models

| Supporting contract | Proposed contents | Owned by | Not settled |
|---|---|---|---|
| `DroneState` | location (WGS84), AGL, velocity, heading, remaining energy/battery %, home position, simulated time, state revision | Simulator (B) | Energy units; initial/home initialization; tick and revision semantics |
| `WorldState` | survey/geofence/no-fly geometries, restricted zones, wind, environmental snapshot/revision | Simulator/Weather (B) | Flat vs terrain, weather freshness, coordinate projection, zone source trust |
| `SafetyPolicy` | altitude limits, max speed/turn, wind limit, battery reserve, mission time/waypoint caps, no-fly buffer, energy/return model | Trusted config + verifier (B) | **All numeric values and precedence require explicit freeze** |

### 4.9 Verifier rule classes from blueprint (proposed implementation scope)

The blueprint lists ten rules, not numerical limits. Adopting *all ten* was recommended, **not explicitly approved**:

1. Geofence containment for every waypoint **and path segment**.
2. Restricted/no-fly polygon avoidance (including buffer).
3. Altitude and terrain clearance.
4. Maximum speed and turn rate.
5. Wind-adjusted energy budget plus reserve.
6. Return-to-home feasibility from every waypoint.
7. Wind limit.
8. Schema and physics sanity (finite numbers, valid coordinates, no impossible motion).
9. Mission-time and waypoint-count caps.
10. Constraint/injection integrity: untrusted text cannot override authoritative restrictions.

Do not hardcode aircraft specifications. These checks are meaningful only with a defined simulator physics model and trusted `SafetyPolicy` values.

## 5. Proposed API boundaries (paths and payload names NOT FROZEN)

| Producer → consumer | Proposed action | Expected response | Owner |
|---|---|---|---|
| UI → AI parser | Submit survey instruction and operator-approved restrictions | `Mission` or structured validation/clarification failure | A |
| AI planner → verifier | Submit candidate `Plan` + relevant state/policy refs | `VerificationResult` + `Violation[]` | A calls, B implements |
| Verifier → certificate issuer | Passing verification for an unchanged candidate | `Certificate` | B |
| UI → executor | Request launch of approved plan | Accept/reject based on certificate/approval validity | B, endpoint A |
| Simulator → event handler | Stream `SimulationEvent` and telemetry | Acknowledged or deduplicated event | B publishes, A consumes |
| AI replanner → verifier | Revised `Plan` after event | New `VerificationResult`/`Certificate` | A calls, B implements |
| Benchmark runner → APIs | Fixed test cases through raw / verified / repaired configurations | Comparable attempts, verdicts, logs | A |
| Benchmark API → scoreboard | Aggregate run metadata, metrics, artifacts | Dashboard visualizations | A data, B UI |

**Protocol recommendation, not frozen:** REST commands/results; WebSocket telemetry/events; schema versions, event IDs and sequence numbers. No route names, HTTP error shapes, timeout/retry behavior or version headers have yet been approved.

## 6. Repair and runtime safety

**Approved:** retry up to three times, then reject/request operator intervention. **Pending clarification:** whether that means initial candidate + three repairs (recommended), whether full route regeneration is allowed (recommended), and whether schema-malformed candidates count toward the limit.

**Recommended but not approved:** deterministic execution safety controller; approval before initial execution; no execution without current passing certificate; safe response to wind/battery events before discretionary replanning; prevalidated return-to-home on link loss when feasible. A cloud-hosted Nano model is **not** an offline fallback.

## 7. Candidate schema publication and CI (after freeze)

```text
contracts/
  schemas.py                  # canonical Pydantic v2 models
  generated/
    jsonschema/*.schema.json  # exported from models
    typescript/contracts.ts   # generated, not handwritten
  examples/valid/*.json
  examples/invalid/*.json
tests/
  test_contracts.py
  test_schema_generation.py
CONTRACTS.md                  # explanatory contract spec (this file)
```

CI acceptance criteria once fields have been approved:

- `schemas.py` builds under pinned Python/Pydantic versions.
- Every valid example validates; every invalid example fails the intended check.
- Generate schemas and TS types, then fail CI if generated artifacts differ from committed versions.
- Cross-language JSON round-trips preserve field meanings and units.
- Verifier fixtures check polygon **segments**, near-boundary cases, battery reserve, return energy, non-finite numbers and changing world revisions.
- No API may invent a fallback field or silently accept an unknown enum during v1.0.0 validation.
- At least one end-to-end test uses a rejected plan, a structured repair, a passing verification, a certificate and simulated execution.

## 8. Recommendations register — all 16 still PENDING APPROVAL

| ID | Topic | Assistant's recommended v1 choice | Approval |
|---|---|---|---|
| R01 | Geometry | GeoJSON `Polygon` for survey; `Polygon`/`MultiPolygon` for limits; `[lon,lat]` | Pending |
| R02 | Home | Simulator supplies launch/home; home fixed per mission | Pending |
| R03 | Units | m, m/s, seconds, Wh internally, battery % display | Pending |
| R04 | Terrain | Flat simulated terrain; explicit absence of real terrain guarantee | Pending |
| R05 | Actions | TRANSIT/SURVEY/HOVER/RETURN_HOME | Pending |
| R06 | Success | Mandatory waypoint completion and ≥95% deterministic accessible-cell coverage; safe return separately | Pending |
| R07 | Time/identity | UUIDv4, UTC ISO-8601, sim clock, schema version, integer revisions | Pending |
| R08 | Snapshots | Bind candidate/verification to world, drone, safety policy revisions | Pending |
| R09 | Rules | Implement 10 blueprint safety rule classes; trusted numeric configuration | Pending |
| R10 | Authority | Operator can tighten limits; Tavily advisory until separately validated/approved | Pending |
| R11 | Repair | One initial + ≤3 full-route repairs, then reject | Pending |
| R12 | Replan | Survivor mark/continue; zone/operator change verified replan; battery/wind safety first | Pending |
| R13 | Link loss | Separate connectivity state, prevalidated deterministic fallback | Pending |
| R14 | Certificate | Bind passing verdict to plan/policy/state digests, invalidate on relevant change | Pending |
| R15 | Lifecycle | Explicit states; operator initial approval; verified automatic in-scope replan only | Pending |
| R16 | API | REST commands, WebSockets events, IDs/sequence/dedup | Pending |

### Additional explicit implementation blockers

1. **Exact simulator `SafetyPolicy` parameters:** min/max altitude; max speed, turn; wind limit; energy model, reserve and return-home threshold; mission time/waypoint caps; zone buffers. Each must have a unit and trusted source.
2. **Survey coverage model:** accessible-cell grid resolution, sensor footprint, required coverage threshold and definition of survey completion.
3. **Emergency behaviors:** what the simulation can actually do if a return is not feasible; runtime stop/hold/abort conditions.
4. **Operational API details:** exact endpoint/event names, error and retry semantics, consumer acknowledgments, version negotiation, and idempotency guarantees.

## 9. Freeze checklist and change control

- [x] 11 high-level decisions recorded.
- [ ] Both developers approve/modify R01–R16.
- [ ] Numeric safety/energy/coverage parameters approved.
- [ ] Primary and supporting schema fields, requiredness, enums and defaults approved.
- [ ] Event payload discriminators, sequencing and trust boundaries approved.
- [ ] API paths, errors, auth and retry/idempotency behavior approved.
- [ ] Two developers review positive/negative example messages.
- [ ] Implement and pin Pydantic v2 canonical models.
- [ ] Export JSON Schema and generated TypeScript types.
- [ ] CI/test fixtures pass, with no schema drift.
- [ ] Create immutable `v1.0.0` Git tag; subsequent incompatible edits require version bump.

**Rule:** Until everything above is approved, this is **`CONTRACTS.md` pre-freeze specification**, not a released interface. Never claim the contracts are fully frozen simply because the document exists in GitHub.
