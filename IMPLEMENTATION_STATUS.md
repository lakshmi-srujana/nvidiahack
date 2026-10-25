# SkyWarden backend implementation status

Status date: 26 October 2026 (IST)

This status tracks `SkyWarden_My_Backend_Implementation.md`. It describes the
AI/backend owner's work only; externally owned simulator, safety verifier,
certificate issuer, execution gate, canonical shared contracts, frontend, and
deployment account are not reimplemented here.

## Completion assessment

- **Locally developable backend work: 100% complete.** Every remaining item that
  can be implemented without the shared production components, a human approval,
  or a cloud account has been implemented and locally exercised.
- **Full owner release checklist: approximately 80% complete.** It is not honest
  to call the complete backend release 100% until the frozen shared contracts,
  real verifier/world/execution adapters, human-reviewed benchmark suite,
  production hosting, and cloud evidence exist.
- **No paid provider calls were made in the final implementation pass.** The
  earlier deliberately limited Nebius and Tavily evidence remains the only live
  provider usage.

## Verified locally

- Python 3.11 pinned installation and dependency-integrity check.
- Ruff, 47 Pytest tests, and provisional schema-drift checks.
- FastAPI health, readiness, mission parse/plan/status, event, trace, benchmark,
  and WebSocket surfaces.
- A separate Uvicorn process smoke: health, readiness, OpenAPI (14 paths),
  parse, verified mock plan, and guarded handoff; provider credentials were
  explicitly disabled for this smoke.
- Development mission → proposal → mock external verification → guarded handoff.
- Repair budget, stale-state checks, event ordering/deduplication, mission
  revision checks, plan-request idempotency, typed replan event context, and
  in-flight proposal invalidation when safety-relevant state changes.
- Bounded Nebius retries/concurrency, exact tier routing, opt-in JSON mode,
  typed model failures, versioned prompt files, prompt revision traces, and
  sanitized inference usage traces.
- A provider-price catalog that produces cost only from explicitly verified
  rates; the checked-in unverified catalog reports cost as unknown.
- Bounded Tavily search, provenance normalization, injection redaction, cache,
  timeout/failure degradation, explicit stale-cache fallback, and separated
  untrusted planner evidence.
- Thirty-case fixed adversarial/control suite, paired RAW/GATED/FULL evaluator,
  bounded/resumable concurrent batch runner, preserved initial candidates,
  Wilson intervals, deterministic JSON/JSONL/CSV artifacts, immutable input and
  source manifests, artifact/scoreboard APIs, and an unreviewed attack candidate
  generation workflow.
- A human-review command that creates an approval manifest. Real scored runs
  require that manifest; the included fixture adapter is explicitly mock-only.
- Non-root API and finite benchmark-worker Dockerfiles. Both images were built
  successfully before this final pass; the latest image rebuild is pending only
  because Docker Desktop is currently stopped.
- Request-size limit, in-process rate limit, CORS allowlist, API authentication,
  separate event-publisher key, and production mock refusal.
- Deployment prerequisites, smoke procedure, single-worker limitation, and
  rollback procedure.

Run all local release gates:

```powershell
cd backend
.\.venv\Scripts\python.exe scripts/verify_release.py
```

## Live provider evidence

- Authenticated Nebius catalog returned 30 accessible models.
- Exact configured tiers were found in the authenticated catalog: Nemotron Nano
  for fast/replanner, Nemotron Super for planner, and Nemotron Ultra for complex.
- One deliberately small planner-tier structured completion passed without JSON
  response mode: 32 input tokens, 25 output tokens, approximately 1.25 seconds.
- One Tavily search returned four normalized attributed results in approximately
  4.37 seconds. The sanitized artifact is stored under ignored `results/live/`.
- Live JSON response mode, full Plan generation, fast/replanner/complex
  completions, and repair calls were not run to conserve the owner's credits.
- Provider pricing metadata is not verified; estimated cost remains explicitly
  unknown rather than fabricated.

Credentials remain only in ignored `backend/.env`. JSON response mode stays
disabled until a future explicit `--run-completion --json-mode` probe succeeds
for each exact ID.

## Awaiting externally owned components

- Approved `CONTRACTS.md` or shared schema package.
- Real `WorldPort`, `VerifierPort`, and `ExecutionPort` implementations.
- Final certificate and event-source authentication conventions.
- Production event policy thresholds and controller permission semantics.
- A human reviewer to approve/freeze the red-team and benign-control suite.

These components plug in through `create_app(..., service_factory=...)` or
`build_service(..., world=..., verifier=..., execution=..., engine=...)`.
Production startup rejects mocks.

## Awaiting deployment/cloud decisions

- Persistent HTTPS/WSS hosting target and secret store.
- Frontend production origin for CORS.
- Nebius registry/project/storage/quota plus installed cloud CLI for a real Job.
- Public smoke, restart/reconnect test, immutable image reference, and rollback.
- Docker Desktop must be running to rebuild and re-smoke the final local images.

The repository contains deployable images and probes, but no live deployment or
cloud Job is represented as completed until real endpoint/job evidence exists.

## Remaining release evidence, not missing application code

1. Freeze the shared contract and connect the real world, verifier, certificate,
   execution, and event-source adapters supplied by their owners.
2. Have a human reviewer approve the fixed evaluation suite and record the
   generated review manifest.
3. Run one intentionally bounded live plan/repair/replan trace if credits permit.
4. Start Docker Desktop and repeat the two image builds and container smoke.
5. Supply the chosen host, TLS/secret-store configuration, production frontend
   origin, and Nebius Jobs project details; then deploy and capture endpoint/job
   evidence.
