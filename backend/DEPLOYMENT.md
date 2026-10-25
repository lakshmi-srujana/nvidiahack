# Backend deployment and rollback

## Release prerequisites

- Frozen shared contract package and passing schema compatibility tests.
- Injected non-mock world, verifier, execution, and proposal adapters.
- Exact Nebius fast/planner/replanner IDs present in the authenticated catalog.
- Separate API and event-publisher credentials stored in the host secret store.
- Explicit HTTPS frontend origin; never use `*` with authenticated production.
- Persistent single-worker host with WebSocket support and outbound HTTPS.
- Durable benchmark artifact storage mounted at `BENCH_OUTPUT_ROOT`.

Production startup deliberately fails when credentials are missing, auth is
disabled, origins are wildcarded, or any injected adapter advertises
`is_mock=True`.

## Build and preflight

```powershell
cd backend
.\.venv\Scripts\python.exe scripts/verify_release.py
cd ..
docker build -f backend/Dockerfile -t skywarden-backend:<commit-sha> .
```

Run the image with one worker. Terminate TLS at a managed ingress/reverse proxy,
preserve WebSocket upgrades, apply network rate limits in addition to the
single-process application limiter, and configure health checks against
`/health`. Readiness is `/ready`; it is expected to remain false until mandatory
model IDs are catalog-visible.

## Deployment smoke

1. Confirm `/health`, `/ready`, and `/openapi.json` according to production docs
   policy (interactive docs are disabled in production).
2. Confirm an unauthorized operator request and an unauthorized event both fail.
3. Run one approved live Mission through planner → real verifier → handoff.
4. Run one deliberately rejected candidate through repair or typed exhaustion.
5. Send a newer zone event during planning and verify the stale candidate never
   reaches the execution adapter.
6. Connect/reconnect the frontend WebSocket and fetch REST planning status.
7. Verify provider usage traces contain no prompts, credentials, or private data.

## Rollback

1. Stop new mission submissions at the ingress.
2. Keep the external deterministic runtime/controller authoritative for any
   active simulation; never infer that a disconnected AI service authorizes a
   route.
3. Redeploy the last known-good immutable image digest and its matching secret
   and contract configuration.
4. Discard in-memory operation/lock state after restart; clients must reconnect
   and fetch authoritative simulator/world state. Benchmark artifacts on durable
   storage remain available.
5. Re-run health/readiness, authentication, verifier connectivity, and one safe
   smoke mission before reopening writes.

## Known limitations

- Operation/event idempotency and locks are process-local; use exactly one API
  worker until moved to a transactional shared store.
- WebSocket delivery is best effort, not exactly once; REST is authoritative.
- Provider/model availability and prices can change independently of the image.
- Cost stays `unknown` until `config/model_prices.json` is populated from a
  verified provider source and marked `verified`.
- Tavily is advisory; stale or unavailable context never changes trusted policy.
- No production deployment, public URL, TLS proof, rollback exercise, or Nebius
  Serverless Job is claimed until its real evidence is captured.
