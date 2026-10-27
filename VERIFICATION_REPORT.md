# SkyWarden local verification report

**Date:** 27 October 2026

**Scope:** Integrated repository at `d9a0174` plus the verification changes committed with this report. Windows local development environment and Linux Docker images.

**Result:** The offline prototype gates below passed. This is not a production or real-flight acceptance claim.

## Checks performed

| Area | Evidence | Result |
| --- | --- | --- |
| Backend release gate | `backend/scripts/verify_release.py`: dependency integrity, Ruff, schema drift, 58 backend tests | Pass |
| Verifier, simulator, contracts | `python -m pytest tests -q` | 31 passed |
| Demo API lifecycle | Tests cover certification, launch, unsafe rejection, bounded replan, and all five approved event families pausing the mission and invalidating its certificate | Pass |
| Frontend | `npm run lint` and `npm run build` | Pass, no lint warnings |
| Browser end-to-end | `npm run test:e2e` against isolated API/Vite ports 8772/5174: nominal verify/launch, survivor event and replan, dam/wind/battery rejection, custom survey, desktop and 375 px mobile width, no page errors | Pass |
| Backend Docker image | Built `backend/Dockerfile`; container answered `/health` and `/api/v1/demo/state` and ran as UID 10001 | Pass |
| Benchmark Docker worker | Built `jobs/Dockerfile.bench`; mock smoke suite produced six attempt records, manifest and scoreboard in a bind mount | Pass |
| Offline benchmark | Fixed 30-case suite across RAW, GATED and FULL modes, 90 records; resume completed without duplication. Local jobs worker produced six records | Pass |
| Repository hygiene | `git diff --check`; verified `backend/.env`, `frontend/node_modules`, and generated `results/*` are ignored | Pass |
| Existing dashboard | `http://127.0.0.1:8000/health` and `http://127.0.0.1:5173/` returned HTTP 200 after testing | Pass |

The browser test used a separate backend process so its mission-state changes did not disturb the dashboard already running on ports 8000 and 5173. Its screenshots and benchmark output are local, ignored artifacts under `results/`. The browser test is repeatable through `frontend/scripts/browser-smoke.mjs` when a fresh API and Vite server are started; it is not yet part of CI.

## Defect found and fixed

The benchmark worker image lacks the `git` executable. Its first smoke run completed attempts but failed during aggregation when collecting Git metadata. `bench.cli.git_metadata()` now tolerates an unavailable executable and accepts `SKYWARDEN_COMMIT_SHA` supplied by the container runtime. A regression test and a rebuilt, successful worker container run verified the fix.

The frontend's initial state request also triggered a lint warning; its effect now handles completion and unmount safely. CI now runs frontend lint in addition to the build. `.gitignore` covers additional generated caches, SQLite files and browser test output while this report remains tracked.

## Limits and remaining project work

- No live Nebius, Tavily, model-catalog, provider-cost, or cloud-job calls were made. Keys in the ignored environment file were not committed. Mock benchmark numbers are functional test evidence, **not** real model performance or safety rates.
- The shared backend/simulator contracts remain provisional. One frozen, generated Python/TypeScript contract and cross-language fixture tests still require team agreement.
- The demo uses in-memory state and deterministic local inputs. Persistent mission/audit history, live weather and research provenance in the UI, automatic event-to-replan flows, and production adapters remain open against `projectplan.md` and `IMPLEMENTATION_STATUS.md`.
- No clean-machine installation, production deployment, real provider trace, public TLS/authentication smoke, rollback exercise, safety sign-off or UX sign-off was performed. Those require external services, decisions, or a separate target environment.

The verified offline dashboard and backend are suitable for local prototype demonstration. The complete project-plan definition of done is **not yet satisfied**.
