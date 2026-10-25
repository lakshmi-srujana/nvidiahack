# SkyWarden backend

This repository contains the mission-intelligence backend described in
[`SkyWarden_My_Backend_Implementation.md`](./SkyWarden_My_Backend_Implementation.md).
It intentionally ships **provisional adapter DTOs** because no shared frozen
contract package was present when this scaffold was built.

## Safety boundary

The backend creates *unverified* survey-plan proposals. Only an externally
owned verifier may return a matching certificate; only an external execution
gate may receive the plan. The production startup path rejects the included
mock world, verifier, execution, and static-planner adapters.

## Run locally

Requirements: Python 3.11 and PowerShell. The first run installs the pinned
backend and development dependencies.

```powershell
cd E:\projects\nvidiahack\backend
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000/docs> for interactive API documentation or
<http://127.0.0.1:8000/health> to confirm the service is running. Stop the
development server with `Ctrl+C`.

The copied `.env` starts in `APP_MODE=development`, which uses test adapters
only. Configure a verified Nebius model and token to enable the strict Nebius
proposal engine; do not mark the backend production-ready until real shared
world/verifier/execution adapters replace the mocks.

External components can be connected without modifying orchestration by calling
`create_app(settings, service_factory=...)` or `build_service(..., world=...,
verifier=..., execution=..., engine=...)`. Production startup rejects any
adapter or proposal engine whose `is_mock` attribute is true.

## Verify

```powershell
cd backend
.\.venv\Scripts\ruff.exe check app bench tests scripts
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/export_contracts.py --check
```

The OpenAPI server exposes `/health`, `/ready`, mission parse/plan/status,
event receipt, a mission-status WebSocket, and read-only benchmark scoreboard
artifacts. Provider APIs are never called by tests or CI.

## Live provider probes

Put real values in the ignored `backend/.env`; never paste or commit provider
keys. First verify exact model IDs from the authenticated catalog. Completion
probing can incur provider cost and is only run when explicitly requested.

```powershell
cd backend
.\.venv\Scripts\python.exe scripts/probe_nebius.py
.\.venv\Scripts\python.exe scripts/probe_nebius.py --run-completion --json-mode
.\.venv\Scripts\python.exe scripts/probe_tavily.py --location "approved district"
```

Only add exact model IDs that pass JSON-mode probing to
`NEBIUS_JSON_MODE_MODELS`. The generated capability report contains no API key.

For a running local test service:

```powershell
.\.venv\Scripts\python.exe scripts/smoke_api.py --exercise-mock
.\.venv\Scripts\python.exe scripts/verify_release.py
```
