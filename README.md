# SkyWarden

SkyWarden is a local, single-drone disaster-survey simulation. The dashboard
connects to a FastAPI backend, a deterministic verifier and a discrete-time
simulator. All flight and telemetry shown here are simulated.

## Run locally

Requirements: Python 3.11, Node.js 22 or newer, and npm. In PowerShell, from the
project root, start both services with one command:

```powershell
.\start.ps1
```

The script installs missing local dependencies, waits for the API and dashboard
proxy, and prints the dashboard URL. Keep the terminal open; Ctrl+C stops both
servers. Logs are written under ignored `results/startup/`. Use `-OpenBrowser`
to open the dashboard automatically, or `-BackendPort` and `-FrontendPort` to
choose different ports. If both services are already healthy on those ports,
the script reports their URL and exits.

For manual setup, install and start the backend:

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

The demo works without provider keys. The optional local image review uses an
installed Ollama `qwen3.5:2b` model on `127.0.0.1:11434`; `start.ps1`
starts Ollama when it finds that model locally. If its model store is custom,
set `SKYWARDEN_OLLAMA_MODELS` to that directory before starting. It never
calls Nebius vision. To enable the separate paid AI route proposal button,
configure the Nebius credentials and model IDs in the ignored
`backend/.env` using `backend/.env.example`. Clicking the button sends a paid
request; provider retries may occur. Automated tests never call paid providers.
Never put provider keys in frontend files or commit them.

## Try the demo

1. Enter an address or six-digit Indian PIN code and select **Find on map**,
   or pan and zoom manually. Choose a result, then select **Lock visible area** or
   **Draw survey polygon**. The locked map shows WGS84 coordinates on hover.
2. Select **Find mapped features** to inspect OSM buildings, water and
   industrial/utility sites. Optionally select **Review map image with local AI**
   to obtain approximate image boxes from Ollama without paid credits.
   Review each suggestion and its source. **Draft zones from suggestions**
   maps buildings to planned zones, water to unknown territory and marked
   utility hazards to restricted zones; each draft can be removed or redrawn.
3. Draw any of the eight zone types. Draw a manual route or use **Auto route**
   for a credit-free route around confirmed exclusion zones. A very large
   area may fail the energy or return-home checks.
4. Select **Verify & start simulation**, or verify and launch separately.
   A passing plan receives a certificate; violations block launch.
5. Inject an event. Pick a survivor coordinate or draw a new restricted
   zone on the map where applicable. The simulation pauses and its
   certificate is invalidated. **Replan & verify** computes a detour around
   confirmed restrictions when possible; review the result before resuming.
6. Select a seeded unsafe scenario to inspect rejection checks.

See [DEMO_SCRIPT.md](DEMO_SCRIPT.md) for details and
[IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) for remaining work.
The current plan-by-plan check is in [STATUS_CHECK_2026-10-30.md](STATUS_CHECK_2026-10-30.md).

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
- The optional Nebius AI route button performs a paid proposal without automatic repairs, to
  limit cost. The operator can replan the remaining route with up to three
  verification attempts; the local replan computes geographic detours around
  confirmed restrictions, but does not resume automatically after an event.
  A live provider end-to-end run remains to be verified.
- Address/PIN search is submitted only by an operator, cached, and uses the
  public Nominatim service. Avoid confidential address queries. Public use
  must respect the [Nominatim usage policy](https://operations.osmfoundation.org/policies/nominatim/);
  `SKYWARDEN_GEOCODER_URL` can point to a supported replacement.
- The interactive map uses MapLibre and live OpenStreetMap tiles with visible
  attribution. Tiles and feature lookup require internet access; mission
  coordinates remain listed if tiles fail. OSM tagged ways are suggestions,
  not complete geographic coverage or authoritative threat detection. Local
  vision boxes are approximate and require operator review. Small-area
  OSM API fallback is for light local demonstration; public use needs a
  supported data service. For another tile service, set `VITE_OSM_TILE_URL`
  and `VITE_OSM_TILE_ATTRIBUTION` at frontend build time and review its terms.
  The deterministic route is a prototype survey sweep, not full coverage
  optimization or a navigation tool.
