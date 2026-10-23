# SkyWarden — v1 Project Plan

**Purpose:** Build a demonstrable, safety-first autonomous-search mission system for a single simulated drone. SkyWarden accepts a survey mission, generates and validates a flight plan, issues a verification certificate only when it is safe, simulates the flight, detects changes, and replans safely with a complete audit trail.

**Document status:** implementation plan. The 11 decisions in section 2 are approved. The 16 engineering choices in section 3 are recommendations only; they are deliberately **not frozen** until the users approve them. “Developer A” and “Developer B” are role labels for the two developers.

**Schedule notation:** `T` is the hackathon submission/demo deadline. Replace relative dates with calendar dates once the deadline is confirmed.

---

## 1. v1 outcome and non-goals

### Demo outcome

An operator can create one survey mission for one simulated drone, review a generated route on a map, obtain either a safety certificate or a violation report, launch a certified mission, watch state/events update, and see a safe replan after a seeded event such as a survivor detection, low battery, wind spike, operator change, or new restricted zone.

### v1 non-goals

- No real aircraft, autopilot, telemetry hardware, or autonomous physical actuation.
- No multi-drone coordination, multiple concurrent missions, swarm planning, or fleet management.
- No claims that the system is aviation-certified, emergency-dispatch ready, or suitable for real rescue operations.
- No AI authority to bypass the deterministic safety gate or issue a certificate.

---

## 2. Approved decisions — frozen scope and contract direction

These are the 11 explicitly approved decisions. Implementation must conform to them; an implementation detail not stated here is still open.

| # | Approved decision | Implementation consequence |
| --- | --- | --- |
| 1 | **One simulated drone; one active mission.** | Enforce one `ACTIVE` mission and one simulator instance. Queue/reject a second launch rather than invent concurrent behavior. |
| 2 | **WGS84 longitude/latitude; distances in metres.** | Persist positions as WGS84 coordinates. Convert/project only inside geometry calculations; label all distance values with metres. |
| 3 | **Altitude is AGL, in metres.** | Every waypoint altitude is `altitude_agl_m`; simulator controls and UI must not imply MSL. |
| 4 | **Mission capability: survey a specified area.** | v1 mission input is a survey polygon/area with operational constraints, not delivery, tracking, or free-flight missions. |
| 5 | **Safety authority: trusted drone/environment configuration plus operator-approved mission restrictions.** | A validated configuration and the approved mission define constraints. AI suggestions and external research cannot relax them. |
| 6 | **Waypoint command fields: position, altitude, speed, optional action, optional dwell time.** | Keep all five concepts in the `Waypoint` contract; omitted action/dwell must have explicit null/default behavior in schemas. |
| 7 | **Replan on survivor detection, low battery, wind spike, operator mission change, or new restricted zone.** | These five events must be seedable in the simulator and represented/audited as replanning triggers. |
| 8 | **Repair policy: retry up to three times, then reject/request operator intervention.** | Track repair attempt count. A fourth automatic repair is prohibited; return a violation report and an actionable operator state. |
| 9 | **Certificates only after every mandatory safety check passes; rejected attempts get separate violation reports.** | Certificate issuance is downstream of deterministic validation. Never create a “partial” certificate for a rejected plan. |
| 10 | **Python Pydantic v2 models are the source of truth; export JSON Schemas and generate TypeScript types.** | Contract changes start in Python and are versioned, schema-exported, type-generated, and reviewed by both developers. |
| 11 | **Define supporting data contracts alongside the six primary contracts.** | Supporting models (for example drone state, environment, restriction, audit metadata, and replan request) live beside—not embedded ambiguously in—the primary contract package. Exact support-model fields remain open until reviewed. |

### Primary shared contracts

The frozen contract set is `Mission`, `Plan`, `Waypoint`, `Violation`, `Certificate`, and `SimulationEvent`. All have a semantic `schema_version`, stable identifier, timestamp where applicable, and validation rules in the Pydantic source package. JSON Schema and generated TypeScript definitions are build artifacts, never hand-edited competing sources of truth.

| Contract | Minimum responsibility |
| --- | --- |
| `Mission` | Survey area, selected drone/configuration reference, operator-approved restrictions, lifecycle status, and links to the current plan. |
| `Plan` | Mission reference, ordered waypoints, planner/repair metadata, safety-validation result, and provenance. |
| `Waypoint` | WGS84 position, AGL altitude, speed, optional action, and optional dwell time. |
| `Violation` | Failed rule, severity, affected object/location/time where relevant, evidence, remediation, and plan/attempt reference. |
| `Certificate` | Immutable assertion that all mandatory checks passed for a specific plan/configuration/restriction snapshot, including check results and expiry/invalidation conditions. |
| `SimulationEvent` | Time-ordered simulator fact or injected trigger, payload, correlation/mission ID, and resulting state/replan linkage. |

### Contract-management rules

1. Developer A owns Pydantic definitions and schema export; Developer B owns generated-type consumption. Both must approve any breaking version change.
2. Every endpoint/event uses IDs, `schema_version`, ISO-8601 UTC timestamps, and a correlation ID. These envelope details are a proposed implementation convention pending approval under recommendation 5.
3. Add fixtures for a valid mission, an invalid/geofence-crossing plan, a low-battery event, and a completed certificate. Contract tests validate Python, JSON Schema, and TypeScript parsing of the same fixtures.
4. Do not mutate a certified plan in place. A replan creates a new plan version and records whether the old certificate became invalid.

---

## 3. Sixteen recommended v1 engineering choices — pending user approval

None of the choices below is an approved requirement. They are a coherent, low-risk hackathon baseline; mark each Approved, Replaced, or Deferred before treating it as a build commitment.

| # | Recommendation | Why it helps v1 | Status |
| --- | --- | --- | --- |
| R1 | Use a modular monolith: one backend service, one web client, and one shared `contracts/` package. | Fast integration and fewer deployment points. | **Pending approval** |
| R2 | Use Python 3.12, FastAPI, Pydantic v2, and `pytest` for backend/contracts. | Matches the approved Python source-of-truth decision. | **Pending approval** |
| R3 | Use React + TypeScript + Vite for the operator dashboard. | Fast map/event UI iteration and strong generated-type use. | **Pending approval** |
| R4 | Use SQLite for the demo, with repository abstraction and a Postgres migration path. | Zero-operational-overhead persistence while retaining a production direction. | **Pending approval** |
| R5 | Expose REST for commands/reads and WebSocket (or SSE) for mission events; use a versioned `/api/v1` envelope. | Clear request/response behavior plus live simulator updates. | **Pending approval** |
| R6 | Use MapLibre with an OpenStreetMap-compatible tile source and visible attribution. | An understandable operator map without a proprietary dependency. | **Pending approval** |
| R7 | Use a deterministic, discrete-time simulator (one-second ticks; controllable acceleration/pause). | Makes demos and tests reproducible. | **Pending approval** |
| R8 | Start survey planning with a deterministic lawnmower/serpentine coverage path clipped to the survey area. | Meets the survey scope before attempting complex optimization. | **Pending approval** |
| R9 | Implement safety checks as named deterministic rules in a rule engine, not as LLM judgments. | Reproducible certificates and explainable violations. | **Pending approval** |
| R10 | Keep AI behind an orchestrator that returns schema-constrained suggestions; only deterministic services can create plans/certificates. | AI can assist without becoming the safety authority. | **Pending approval** |
| R11 | Call Tavily only from the backend for optional situational research; store query, sources, timestamp, and summary as non-authoritative evidence. | Allows current context while protecting the API key and auditability. | **Pending approval** |
| R12 | Use an in-process background task for v1 replanning, with an interface that can later move to a queue. | Handles short jobs simply without premature infrastructure. | **Pending approval** |
| R13 | Use seeded demo scenarios and recorded Tavily responses in automated tests. | Avoids flaky demos/tests caused by network changes. | **Pending approval** |
| R14 | Use structured JSON logs, correlation IDs, and a simple in-app audit timeline before adding a hosted observability platform. | Gives credible traceability within hackathon time. | **Pending approval** |
| R15 | Package the system with Docker Compose and environment-variable configuration; never commit secrets. | One-command repeatable local/demo deployment. | **Pending approval** |
| R16 | Add GitHub Actions for formatting, unit/contract tests, type checks, and a minimal build. | Protects the shared contract and catches integration regressions. | **Pending approval** |

### Explicitly open decisions

The plan must not silently decide: LLM/provider/model and budget; exact safety thresholds; authentication level; tile provider/usage limits; persistence retention; external deployment host; Tavily entitlement/query policy; exact support-contract fields; event transport (WebSocket versus SSE); and the real calendar deadline. Until decided, use local/demo-safe defaults only and label them in code/UI as assumptions.

---

## 4. Finalized two-developer task split

### Developer A — Flight safety, contracts, simulator, and backend platform

**Owns**

- Pydantic v2 primary/supporting models, JSON Schema export, fixture corpus, semantic-version policy, and contract review gate.
- Mission/plan APIs, persistence, lifecycle state machine, deterministic survey planner, and replan coordinator.
- Simulator state/tick engine, injected events, telemetry/event publishing, low-battery and wind calculations.
- Safety rule engine, violation reports, retry limit, immutable certificates, audit links, and backend test suite.
- Container configuration, environment examples, and CI backend/contract jobs.

**Must provide to Developer B**

- Versioned schemas/types and a fixture bundle before UI integration starts.
- A locally runnable API with seeded scenarios and documented endpoint/event behavior.
- Stable event payloads and acceptance-test evidence for each safety outcome.

### Developer B — Operator experience, AI/research, integration, and demo quality

**Owns**

- Operator dashboard: mission creation, map/polygon input, route visualization, status, event timeline, certificate and violation views, intervention flow.
- Generated TypeScript type integration, API client, live-event client, UI validation, and accessibility/demo states.
- AI orchestration boundary: prompt/templates, structured response validation, repair-suggestion UX, refusal/fallback presentation, and provenance display.
- Tavily backend-client integration in coordination with Developer A: research UI, source presentation, cached/demo response UX, and source-disclaimer copy.
- End-to-end demo script, benchmark dashboard/report, screenshots/video, pitch narrative, and frontend/e2e test suite.

**Must provide to Developer A**

- API/event integration issues with reproducible payloads.
- UX requirements for lifecycle states, operator intervention, errors, and certificate/violation evidence.
- A repeatable full-demo checklist and browser-test results before release candidate.

### Shared and handoff responsibilities

| Area | Accountable | Shared checkpoint |
| --- | --- | --- |
| Contract changes | A | Both review every breaking change; B confirms generated types compile. |
| Safety policy and thresholds | A | Both review; operator-facing wording is B’s responsibility. |
| API and live events | A | B supplies an integration consumer and contract-test fixtures. |
| AI and Tavily safety boundary | B | A validates that no suggestion bypasses deterministic safety rules. |
| End-to-end scenarios | B | A verifies simulator determinism and audit evidence. |
| Release/demo | B | A signs off on safety assertions; both run the rehearsal. |

**Working agreement:** merge small vertical slices; do not merge a producer/consumer change without regenerated types and fixtures; use one integration branch only if main is protected; raise a blocking contract question immediately rather than guessing.

---

## 5. System flow and API dependencies

```text
Operator Dashboard
   | create/change mission, review plan, launch/intervene
   v
Mission API --> Contract validation --> Planner/Repair --> Safety rule engine
   ^                                                    | pass / fail
   |                                                    v
Live events <--- Simulator <--- certified plan     Certificate / Violation report
   |                  |                                   |
   +---- replan trigger (five approved event types) -------+

AI + Tavily (optional, non-authoritative) --> schema-constrained suggestion/evidence
                                              --> Planner/Repair --> Safety rule engine
```

### Proposed API surface (R5 pending approval)

| Interface | Depends on | Behavior and acceptance intent |
| --- | --- | --- |
| `POST /api/v1/missions` | `Mission`, supporting config/restriction contracts | Validates survey input; returns mission ID and lifecycle state. |
| `GET /api/v1/missions/{id}` | `Mission`, latest `Plan`, sim state | Returns an operator-safe aggregate without hiding violation/certificate status. |
| `POST /api/v1/missions/{id}/plans` | Mission, planner, `Plan` | Creates a proposed plan; no launch authority. |
| `POST /api/v1/plans/{id}/validate` | Plan, config, restrictions, rule engine | Returns a certificate if all mandatory checks pass, otherwise separate violations. |
| `POST /api/v1/missions/{id}/launch` | Valid certificate, simulator | Refuses absent/stale/invalid certificate; starts only the one active mission. |
| `POST /api/v1/missions/{id}/events` | `SimulationEvent`, replan coordinator | Accepts only test/operator-approved injected events; records correlation and outcome. |
| `POST /api/v1/missions/{id}/replan` | Event/operator change, repair policy | Makes at most three automated repair attempts, then requests intervention. |
| `GET /api/v1/certificates/{id}` / `GET /api/v1/violations` | Certificate/Violation | Retrieves immutable safety evidence and remediations. |
| `GET /api/v1/missions/{id}/stream` | Event transport, simulator | Sends ordered mission/simulator/replan events for the dashboard. |
| `POST /api/v1/research` | Tavily adapter, AI boundary | Optional backend-only research with provenance; response cannot alter constraints directly. |

### Dependency order

1. Contracts and fixtures unblock all backend/UI work.
2. Mission lifecycle + deterministic planner unblock safety validation.
3. Safety certificate/violation behavior unblocks simulator launch.
4. Simulator events unblock replan UX and end-to-end demos.
5. AI/Tavily plugs into suggestions/evidence only after the deterministic loop works.
6. Benchmarks, deployment, and rehearsal consume the integrated loop—not stubs.

---

## 6. Implementation phases, deadlines, and acceptance criteria

| Phase | Deadline | Primary owner | Deliverables | Exit/acceptance criteria |
| --- | --- | --- | --- | --- |
| 0. Kickoff and decision review | T-10 days | A + B | Repo skeleton, issue board, this plan reviewed, decision register | All 11 approvals copied into code/docs; each R1–R16 marked pending/approved/replaced; no unclear blocker hidden. |
| 1. Contract foundation | T-9 days | A | Six Pydantic models, first supporting models, schemas, generated TS types, fixtures | Python/schema/TS parse the same fixtures; invalid waypoint/missing AGL fields fail; B compiles against generated types. |
| 2. Safe plan loop | T-7 days | A | Mission/plan APIs, survey planner, named safety rules, violations/certificates | Valid survey produces ordered route and certificate; restricted/out-of-bounds/unsafe plan produces no certificate and actionable violations. |
| 3. Simulator and live core | T-6 days | A | Single-drone tick engine, mission lifecycle, event stream, five trigger fixtures | Only one mission can be active; identical seed yields identical event trace; invalid/stale certificate blocks launch. |
| 4. Operator dashboard | T-5 days | B | Map, mission form, plan/certificate/violation views, live timeline | Operator completes create → validate → launch → observe without terminal/API tooling; map labels units/AGL accurately. |
| 5. Replanning and intervention | T-4 days | A + B | Five event flows, repair UI, retry accounting, intervention state | Each trigger creates an audit trail and safe replan or visible intervention request; fourth automatic repair is impossible. |
| 6. AI/Tavily enrichment | T-3 days | B | Structured AI suggestion path, Tavily adapter, citations/provenance, offline fixtures | Malformed/model/network response fails closed to deterministic flow; no AI/Tavily output can issue certificate or override restrictions. |
| 7. Verification and benchmark | T-2 days | B + A | Automated tests, seeded benchmarks, performance report, accessibility/error pass | All must-pass tests green; benchmark evidence attached; critical demo flows pass from clean setup. |
| 8. Deploy and rehearse | T-1 day | B + A | Docker Compose/demo deployment, env checklist, runbook, recorded backup demo | Clean-machine startup works; two complete rehearsals; rollback/offline demo path confirmed. |
| 9. Submission | T | B | Final presentation/demo, README links, evidence bundle | Team can demonstrate both success and unsafe-plan rejection, explain limits, and provide reproducible instructions. |

If the real deadline is shorter, preserve phases 1–5 and 8; defer AI/Tavily enrichment rather than weakening safety/certificate behavior.

---

## 7. Safety, simulator, AI, and Tavily requirements

### Mandatory safety behavior

- Treat trusted drone/environment configuration and operator-approved restrictions as the highest v1 authority.
- Validate coordinate shape, survey-area containment, altitude/speed/battery bounds, restricted zones, wind limits, and waypoint ordering before certification. The exact thresholds are an open decision.
- Every failure creates `Violation` records with a rule ID, evidence, severity, remediation, and correlation to a plan attempt.
- Issue `Certificate` only when every mandatory check passes against immutable configuration/restriction snapshots.
- Invalidate/revalidate a certificate when a mission restriction, environment, plan, or relevant drone state changes.
- Enforce at most three automatic repairs for a triggering condition; then stop and request operator intervention.

### Simulator requirements

- Simulate one drone state: position, altitude AGL, speed, heading/route progress, battery, mission state, and environmental inputs needed for safety checks.
- Publish ordered `SimulationEvent`s and retain an audit timeline sufficient to replay the demo scenario.
- Support deterministic seed/reset, pause, speed-up, and injected events for all five approved replan triggers.
- Never characterize simulation output as real telemetry.

### AI requirements

- AI may translate operator intent into a draft/suggestion, explain a violation, summarize evidence, or propose repair options.
- AI output must parse against a constrained schema, be tagged as suggestion/provenance, and pass deterministic planner/safety validation before use.
- On a model timeout, refusal, malformed response, or uncertain result: retain the existing certified state or request operator action; do not improvise a flight command.
- Keep prompts and outputs free of unnecessary personal/sensitive survivor data; redact before persistence where feasible.

### Tavily requirements

- Tavily is optional enrichment, not an authority on restrictions, configuration, or certification.
- Call it from the backend only; API keys are environment secrets and never reach the browser, logs, or repository.
- Store/return source URL, retrieval time, query/provenance, and a clear freshness disclaimer. Treat external content as untrusted.
- Provide a recorded/cached response and a “research unavailable” path so the demo still runs offline or without quota.

---

## 8. Test and benchmark plan

### Test layers

| Layer | Owner | Minimum coverage |
| --- | --- | --- |
| Contract | A | Round-trip Pydantic ↔ JSON Schema ↔ generated TypeScript fixtures; version/error cases. |
| Unit | A | Geometry, planner, tick/battery/wind calculations, every safety rule, certificate issuance/invalidation, retry cap. |
| API/integration | A + B | Mission lifecycle, unsafe rejection, live event order, replayed seed, all five replanning triggers. |
| UI/e2e | B | Operator create/validate/launch, violation remediation, intervention state, live timeline, certificate view. |
| AI/Tavily | B | Schema failure, provider failure, prompt-injection-like retrieved content, missing citation, offline fixture fallback. |
| Regression/demo | A + B | Clean startup and scripted happy, unsafe, and replan scenarios. |

### Benchmarks (targets proposed; pending approval)

Record hardware/environment, commit SHA, scenario seed, fixture versions, and raw results. Do not present a single fast run as a guarantee.

| Measure | Proposed v1 target | Scenario |
| --- | --- | --- |
| Safety-rule correctness | 100% expected pass/fail on the seeded safety corpus | Valid, geofence, altitude, speed, battery, wind, and malformed inputs. |
| Certificate integrity | 0 certificates for any seeded mandatory-check failure | Run all negative fixtures. |
| Replan safety | 100% of accepted replans revalidated/certified; 0 fourth auto-repair | Five trigger cases plus repeated-failure case. |
| Replan responsiveness | p95 under 5 seconds locally, excluding external AI/Tavily calls | Deterministic events on standard demo machine. |
| Event/UI freshness | p95 under 1 second locally | Simulator tick to visible timeline update. |
| Determinism | Identical state/event trace for same seed and inputs | Repeat each core scenario three times. |
| Resilience | Core demo completes with AI/Tavily disabled | Network-denied/cached-fixture run. |

Benchmark results are evidence for a prototype, not proof of operational flight safety.

---

## 9. Deployment, release, and operations

### Environments

1. **Local development:** default deterministic seed, local SQLite (if R4 approved), mock AI/Tavily, sample environment file.
2. **Demo/staging:** containerized frontend/backend, separate environment secret store, seeded scenarios, logs/audit export, network-failure fallback tested.
3. **Production:** explicitly out of v1 scope. Any public deployment requires separate security, privacy, reliability, terms-of-service, map-provider, and aviation review.

### Release checklist

- Pin image/dependency versions and build from a clean checkout.
- Confirm no secrets/API keys are tracked; provide `.env.example` containing names only.
- Run format, lint/type checks, unit/contract/API/e2e tests, and benchmark corpus.
- Confirm source attribution, map attribution, limitations, and prototype disclaimer are visible.
- Create a tagged release/commit hash, archive fixture seeds/results, and test the offline demo path.
- Have both developers sign off: A on safety evidence, B on end-to-end usability and demo narrative.

### Demo sequence

1. Explain one simulated drone and survey area, including WGS84/AGL units.
2. Create a mission and show generated waypoints.
3. Validate it; display the resulting certificate and passed checks.
4. Launch and show live simulated state/events.
5. Inject a survivor detection or wind spike; show audit event, safe replan, and new validation.
6. Demonstrate an unsafe restricted-zone/battery case: no certificate, violations/remediation, and no launch.
7. Disable external research/AI or use a cached response to demonstrate the fail-safe offline path.

---

## 10. Risks, mitigations, and decision gates

| Risk | Signal | Mitigation | Owner |
| --- | --- | --- | --- |
| Contract drift between backend and UI | Type/API mismatch or last-minute manual fields | Python-first schemas, generated types, shared fixtures, contract CI | A |
| Safety rules are incomplete/ambiguous | Team cannot explain why a plan passes | Name rules, fixture each failure, keep thresholds in a reviewed config/decision log | A |
| AI produces unsafe or malformed suggestions | Schema failure, unsupported claim, prompt injection | Constrain/validate output; deterministic rules retain authority; fail closed | B |
| Tavily/network/quota outage | Timeout/no sources at demo | Backend adapter, timeout, cache/recorded fixture, clear unavailable UX | B |
| Replanning exceeds time budget | Slow/unstable event-to-plan loop | Deterministic planner first; defer optimization/AI, benchmark seeded scenarios | A |
| Map/tile service dependency fails | Blank map/rate limit | Attribution-compliant provider selection, local fallback imagery/list view for demo | B |
| Scope creep | Multi-drone/real-flight/extra mission requests | Enforce non-goals; require a documented trade before adding scope | A + B |
| Secret/privacy leakage | Key in client/logs; survivor data persisted | Server-side secrets, redaction, repo scanning, minimal data retention | B |
| Last-minute integration break | Works only on one developer machine | Daily integration run and T-2 release candidate from clean clone | A + B |
| Unconfirmed deadline | Milestones cannot be planned realistically | Replace T-relative schedule as soon as organizer deadline is known | A + B |

### Required decision gates

- **Before phase 1:** approve/replace R1–R6 and the initial supporting contract list.
- **Before phase 2:** approve concrete safety thresholds, rule severities, certificate expiry/invalidation behavior, and precise restriction geometry semantics.
- **Before phase 5:** approve event transport, repair UX, and operator authority/change model.
- **Before phase 6:** approve AI provider/model/budget, Tavily key/usage policy, retention/redaction, and source-display policy.
- **Before phase 8:** approve demo host, secrets handling, public-access scope, and submission calendar date.

---

## 11. Definition of done

SkyWarden v1 is ready when the repository can be cleanly started, the two developers can run the same seeded scenario, and the demo shows all of the following:

- one WGS84/AGL survey mission and one simulated drone;
- validated primary and supporting contracts from the shared Python source of truth;
- a safe plan with a certificate only after mandatory checks pass;
- an unsafe plan rejected with a distinct, actionable violation report;
- live simulated state plus at least one of the five approved replan events;
- three-or-fewer automatic repair attempts followed by visible operator intervention when needed;
- AI/Tavily treated as optional, attributable, fail-safe assistance;
- passing contract, safety, integration, UI, and deterministic-demo tests; and
- a documented prototype limitation statement with no real-world flight claim.

## 12. Immediate next actions

1. Both developers review section 3 and record Approve/Replace/Defer against R1–R16.
2. Developer A opens the contract-foundation task and proposes the initial supporting-model list for joint review.
3. Developer B opens the dashboard flow task using the five-state demo sequence and generated-type dependency.
4. Confirm the hackathon calendar deadline, then replace all `T-n` milestones with actual dates.
5. Do not begin AI/Tavily integration until the safety-certified simulator loop has a deterministic passing demo.
