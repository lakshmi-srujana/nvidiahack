# Integrated implementation status

As of 30 October 2026, the developer branches have been combined locally for
the prototype. The source for the verifier, simulator, backend, and dashboard
is in the project root.

The dashboard can select seeded scenarios or lock a map viewport or draw a survey polygon,
request deterministic verification, inspect a certificate or violations,
launch a simulated mission, watch ticks, and inject any of the five event
families. Events pause the simulation for intervention and invalidate the
current certificate. A bounded remaining-route replan can then be requested and
must pass verification again. A separate explicit button can request a paid AI plan;
the proposal is converted into the verifier's models and must pass before it
can be staged for launch.

The active dashboard map uses MapLibre and live OpenStreetMap raster tiles
with on-map attribution. It projects the geofence, all eight zone types,
OSM feature suggestions, route, numbered waypoints and simulated drone in
WGS84. Operators can enter an address or six-digit Indian PIN code, browse
then lock the viewport, draw a polygon, read hover coordinates, draw zones
and manual routes, or generate a deterministic geographic route around
confirmed exclusion zones without model credits. Bounded OSM tagged-way
lookup suggests mapped buildings, water and industrial/utility sites with
source links. Optional local Ollama image review returns approximate boxes
from the captured map; one-click draft zones can turn suggestions into
reviewable planned, unknown or restricted zones. Neither source establishes
that all threats were found. Tile, geocoding and data availability depend
on external services and network.

The backend and simulator still use different provisional contracts. The demo
adapter bridges them without asserting that the shared contract is frozen.
Demo policy limits, geometry approximations, energy estimates and simulated
environment are assumptions and need team review.

Remaining before the full project plan's definition of done:

- Approve and generate one shared contract and validate Python/TypeScript
  fixtures against it.
- Improve coverage planning, automatic event-to-replan flows and detour quality,
  plus a real end-to-end model/replanner trace within an agreed credit budget.
- Connect persistent SQLite/audit history, live weather, Tavily provenance and
  actual benchmark artifacts to the dashboard.
- Validate local vision detection accuracy on labeled maps; it is a
  suggestion source and not flight authority.
- Run clean-machine, production deployment and rehearsal checks; record the
  team's safety and UX sign-offs. The offline browser and container checks are
  recorded in `VERIFICATION_REPORT.md`.

See `STATUS_CHECK_2026-10-30.md` for a phase-by-phase plan comparison, exact
test results and the full incomplete-work list.

The earlier offline benchmark and backend APIs remain available. The integrated
dashboard currently uses the separate `/api/v1/demo` endpoints, not the
legacy mock-backed development mission endpoints. The demo state is in memory
and disabled in production mode.
