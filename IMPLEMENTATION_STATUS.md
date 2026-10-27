# Integrated implementation status

As of 27 October 2026, the developer branches have been combined locally for
the prototype. The source for the verifier, simulator, backend, and dashboard
is in the project root.

The dashboard can select seeded scenarios or create a rectangular survey,
request deterministic verification, inspect a certificate or violations,
launch a simulated mission, watch ticks, and inject any of the five event
families. Events pause the simulation for intervention and invalidate the
current certificate. A bounded remaining-route replan can then be requested and
must pass verification again. A separate explicit button can request a paid AI plan;
the proposal is converted into the verifier's models and must pass before it
can be staged for launch.

The backend and simulator still use different provisional contracts. The demo
adapter bridges them without asserting that the shared contract is frozen.
Demo policy limits, geometry approximations, energy estimates and simulated
environment are assumptions and need team review.

Remaining before the full project plan's definition of done:

- Approve and generate one shared contract and validate Python/TypeScript
  fixtures against it.
- Implement coverage planning, automatic event-to-replan and hazard-detour flows,
  plus a real end-to-end model/replanner trace within an agreed credit budget.
- Connect persistent SQLite/audit history, live weather, Tavily provenance and
  actual benchmark artifacts to the dashboard.
- Run browser end-to-end, clean-machine/container, deployment and rehearsal
  checks; record the team's safety and UX sign-offs.

The earlier offline benchmark and backend APIs remain available. The integrated
dashboard currently uses the separate `/api/v1/demo` endpoints, not the
legacy mock-backed development mission endpoints. The demo state is in memory
and disabled in production mode.
