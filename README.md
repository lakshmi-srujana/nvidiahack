# SkyWarden

SkyWarden is a local, single-drone disaster-survey simulation. The dashboard
connects to a FastAPI backend, a deterministic verifier and a discrete-time
simulator. All flight and telemetry shown here are simulated.

## Run locally

Requirements: Python 3.11, Node.js 22 or newer, and npm. In PowerShell, from the
project root, install and start the backend:

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173. The backend provides interactive API documentation at
http://127.0.0.1:8000/docs. Stop each process with Ctrl+C.

The demo works without provider keys. To enable the optional AI proposal button,
configure the Nebius credentials and model IDs in the ignored
`backend/.env` using `backend/.env.example`. Clicking the button sends a paid
request; provider retries may occur. Automated tests never call paid providers.
Never put provider keys in frontend files or commit them.

## Try the demo

1. Choose the nominal flash-flood scenario, or expand **Create a survey area**
   and enter an instruction containing “survey” and rectangle coordinates.
2. Select **Verify plan**. A passing plan receives a certificate; violations
   remain visible when validation fails.
3. Select **Launch simulation**. The route, drone and telemetry are simulated.
4. Inject an event. The simulation pauses and its certificate is invalidated.
   Review the event, then select **Replan & verify** or request an AI proposal
   before launch.
5. Select the dam, high-wind, or low-battery scenario to see a rejected plan.

See [DEMO_SCRIPT.md](DEMO_SCRIPT.md) for details and
[IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) for remaining work.

## Verification

```powershell
cd backend
.\.venv\Scripts\python.exe scripts/verify_release.py
cd ..
.\backend\.venv\Scripts\python.exe -m pytest tests -q
cd frontend
npm run build
```

## Boundaries and limitations

- The verification policy, simulated weather, energy model and scenarios are
  prototype assumptions; the project is not approved for real aircraft.
- The integrated demo is process-local and limited to one active simulation.
  Restarting the backend clears its state. SQLite and the earlier benchmark,
  Tavily and WebSocket modules are present but are not wired into this demo UI.
- The legacy general mission API uses development mocks unless real adapters
  are injected; the integrated demo endpoints use the Python verifier and
  simulator. Demo routes are disabled in production mode.
- The two branches arrived with different provisional Python and TypeScript
  data models. The adapter converts between them; shared field-level contracts
  remain pre-freeze and still require both developers' review.
- The optional AI button performs one proposal without automatic repairs, to
  limit cost. The operator can replan the remaining route with up to three
  verification attempts; this does not automatically compute hazard detours.
  A live provider end-to-end run remains to be verified.
- The route display is a schematic, not a geographic basemap. It is not a
  navigation tool. The custom survey planner follows the rectangle perimeter;
  it does not establish full area coverage.
