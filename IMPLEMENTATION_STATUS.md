# SkyWarden backend implementation status

Status date: 26 October 2026 (IST)

This status tracks `SkyWarden_My_Backend_Implementation.md`. It describes the
AI/backend owner's work only; externally owned simulator, safety verifier,
certificate issuer, execution gate, canonical shared contracts, frontend, and
deployment account are not reimplemented here.

## Verified locally

- Python 3.11 pinned installation and dependency-integrity check.
- Ruff, Pytest, and provisional schema-drift checks.
- FastAPI health, readiness, mission parse/plan/status, event, trace, benchmark,
  and WebSocket surfaces.
- Development mission → proposal → mock external verification → guarded handoff.
- Repair budget, stale-state checks, event ordering/deduplication, mission
  revision checks, and plan-request idempotency.
- Bounded Nebius retries/concurrency, exact tier routing, opt-in JSON mode,
  typed model failures, and sanitized inference usage traces.
- Bounded Tavily search, provenance normalization, injection redaction, cache,
  timeout/failure degradation, and separated untrusted planner evidence.
- Thirty-case fixed adversarial/control suite, paired RAW/GATED/FULL evaluator,
  deterministic metrics/manifests, scoreboard/case APIs, and unreviewed attack
  candidate generation workflow.
- Non-root API and finite benchmark-worker container images.
- Request-size limit, in-process rate limit, CORS allowlist, API authentication,
  separate event-publisher key, and production mock refusal.

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

These components plug in through `create_app(..., service_factory=...)` or
`build_service(..., world=..., verifier=..., execution=..., engine=...)`.
Production startup rejects mocks.

## Awaiting deployment/cloud decisions

- Persistent HTTPS/WSS hosting target and secret store.
- Frontend production origin for CORS.
- Nebius registry/project/storage/quota plus installed cloud CLI for a real Job.
- Public smoke, restart/reconnect test, immutable image reference, and rollback.

The repository contains deployable images and probes, but no live deployment or
cloud Job is represented as completed until real endpoint/job evidence exists.
