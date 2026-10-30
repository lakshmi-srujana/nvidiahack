# SkyWarden status check — 30 October 2026

## Result

The local single-drone demo uses an interactive OpenStreetMap basemap. An operator can search an address or Indian PIN code, pan and zoom, lock the visible WGS84 area or draw a survey polygon, inspect cursor coordinates, review mapped and local image suggestions, draft zones, draw or generate a route without model credits, verify it, and run the simulation. Event injection pauses the run and invalidates its certificate. The full v1 definition of done in `projectplan.md` is **not met**.

This implementation uses tagged OpenStreetMap geometry and optional local Ollama `qwen3.5:2b` vision on the captured map image. Image boxes are approximate suggestions, clipped to the locked WGS84 area; they are not authoritative threat detections. Nebius vision was not called and no paid model credits were used for map analysis. A separate paid AI route proposal remains an explicit opt-in button; it was not called in verification.

## Checks run on this checkout

| Check | Result |
| --- | --- |
| Backend `scripts/verify_release.py` | Passed: dependency integrity, Ruff, schema drift, 66 tests |
| Root `pytest tests -q` | 31 passed |
| Frontend `npm run lint` | Passed |
| Frontend `npm run build` | Passed; MapLibre produces a bundle size warning |
| Isolated browser flow, ports 8772/5174 | Passed: seeded verification/launch, survivor event and replan, three rejected scenarios, address/PIN result selection, map area lock, hand drawn safe zone, credit-free auto route, verification and simulation, drawn restricted event, 375 px layout, no page errors |
| Local image review | Live local Ollama run returned an image suggestion and drafted a reviewable zone; no Nebius call |
| Address/PIN lookup | Live `560001` lookup returned provider coordinates near Bengaluru; UI selection covered in browser flow |
| Map service | Official OSM raster tiles loaded with visible attribution; bounded lookup in a small San Francisco area returned 14 mapped features via the OSM API fallback, including linked buildings and an industrial/utility site |
| `git diff --check` | Passed |

The browser and backend checks use the local simulator. They do not establish a clean-machine install, public deployment, sustained OSM service availability, live paid model behavior, or real-flight suitability.

## Requested map workflow

| Requested capability | Status | Evidence or limit |
| --- | --- | --- |
| OpenStreetMap browse and area lock | Implemented | MapLibre raster tiles; pan/zoom, lock viewport, or draw polygon. |
| Genuine latitude/longitude and hover picker | Implemented | MapLibre click and hover WGS84 coordinates feed the server; backend validates ranges and geometry. Seeded scenarios remain simulated example coordinates. |
| Buildings, water and possible threats | Partial | Bounded OSM way lookup plus local image boxes, clipped to survey. OSM coverage and model detections may be incomplete or wrong; operator review required. |
| Eight customizable zone types | Implemented for local demo | Restricted, planned, no-man, no-fly, destination/drop, pickup, safe and unknown. Draw by hand or accept a mapped polygon. Operator must choose its meaning. |
| Automatic zone creation | Partial | One-click draft zones from OSM/local image suggestions; default types are editable by removal/redrawing. Arbitrary terrain and all eight semantic classes are not reliably inferred. |
| Manual address/PIN search | Implemented | Submit-only Nominatim lookup, one request per second, process cache, actual provider coordinates, selectable map marker. Pure six-digit PINs are treated as Indian postcodes. |
| Manual and automatic route | Implemented for local demo | Hand drawn map waypoints or deterministic geographic route around confirmed blocking zones. Optional paid AI route is separate and unverified. |
| Verification before simulation | Implemented | Route and world revisions invalidate certificates; verifier gates launch. Large or unsafe areas are rejected. |
| Simulation and updating metrics | Implemented | Local ticks update battery, altitude, time and drone position while ACTIVE. |
| Event injection | Implemented for local demo | Five event families; survivor uses picked position or actual drone position; new restricted event requires a drawn polygon. Events pause and revoke certificate; operator-triggered replan can detour around confirmed restrictions. |

The free auto route uses geographic geometry and zone avoidance. It is a prototype survey sweep, not comprehensive coverage optimization. A large selected area can be rejected for energy or return-home feasibility, as it should be.

## Project plan phase comparison

| Phase in `projectplan.md` | Status | Remaining work |
| --- | --- | --- |
| 0. Kickoff and decisions | Partial | R1–R16 remain pending in the plan; confirm deadline and team decisions. |
| 1. Contract foundation | Partial | Integrated demo bridges provisional models; freeze one generated shared contract and cross-language fixture gate. |
| 2. Safe plan loop | Partial | Deterministic verification and geographic auto routing work locally; review policy thresholds, coverage assumptions and real terrain constraints. |
| 3. Simulator and live core | Partial | Process-local drone, ticks and five events work; persistent replay/audit and general live event transport remain. |
| 4. Operator dashboard | Partial | Map drawing, zones, routes, gate and metrics work; dashboard polls demo state rather than consuming the general event stream. |
| 5. Replanning and intervention | Partial | Events pause and invalidate certification; bounded operator-triggered replan now computes exclusion-zone detours. Automatic trigger-to-replan and persistent audit remain. |
| 6. AI/Tavily enrichment | Partial | Credit-free OSM feature extraction and local map-image review work; validated detection accuracy, integrated provenance UX, Tavily and verified model repair remain. |
| 7. Verification and benchmark | Partial | Local automated gates pass; live provider performance, accessibility and realistic coverage benchmarks remain. |
| 8. Deploy and rehearse | Incomplete | No recorded clean-machine start, public deployment, two rehearsals, rollback/offline imagery demonstration or sign-offs. |
| 9. Submission | Incomplete | Presentation, evidence bundle and acceptance remain. |

## Definition-of-done check

| Required outcome | Status |
| --- | --- |
| One WGS84/AGL mission and simulated drone | Demonstrated locally |
| Shared validated contract from one source of truth | Incomplete |
| Safe certificate and unsafe rejection with violations | Demonstrated locally with prototype policy |
| Live simulated state and approved event | Demonstrated locally through polling |
| Up to three automatic repairs then intervention | Partial; bounded manual replan exists |
| AI/Tavily attributable, fail-safe assistance | Partial; no paid route/vision trace in this check |
| Contract, safety, integration, UI and deterministic demo tests | Local gates pass; clean setup/live service coverage incomplete |
| Prototype limitations and no real-flight claim | Documented in README and UI |

## Incomplete work, prioritized

1. Freeze the shared contract, team decisions R1–R16, and reviewed safety/coverage thresholds.
2. Add automatic event-triggered replanning, stronger survey coverage and persistent audit/replay. Operator-triggered replans already calculate geographic detours.
3. Evaluate local vision accuracy against labeled map imagery. Current local image boxes and OSM tags can miss or misclassify buildings, water and threats.
4. Connect Tavily/weather provenance, actual benchmark evidence and dashboard event transport.
5. Prepare supported map, geocoding and tile providers for public use. Public OSM/Nominatim services have usage limits; current integrations suit light local demonstration. Add offline imagery if required.
6. Perform clean-machine/deployment, accessibility and rehearsal checks, and record safety/UX sign-offs and submission evidence.

The map depicts real OSM geography with simulated mission geometry. It is not authority for aircraft navigation or emergency operations.
