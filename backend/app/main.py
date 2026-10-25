from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Callable

from fastapi import Depends, FastAPI, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.config import Settings, get_settings
from app.context import TavilyContextClient
from app.contracts import Mission, Point, SimulationEvent
from app.errors import ErrorCode, ServiceError
from app.infrastructure import FixedWindowRateLimiter, StatusBroker
from app.llm.client import NebiusClient
from app.llm.router import ModelRouter
from app.mission import MissionService, ProposalEngine, StaticProposalEngine
from app.mission.nebius_engine import NebiusProposalEngine
from app.mission.parser import NebiusMissionParser
from app.ports import (
    ExecutionPort,
    MockExecutionPort,
    MockVerifierPort,
    MockWorldPort,
    VerifierPort,
    WorldPort,
)

ServiceFactory = Callable[
    [Settings, StatusBroker], tuple[MissionService, NebiusClient, TavilyContextClient]
]


class ParseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operator_instruction: str = Field(min_length=1, max_length=4000)
    approved_area: list[Point]
    approved_location_label: str = Field(min_length=1, max_length=200)
    operator_id: str = Field(min_length=1, max_length=128)


class PlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mission: Mission


class EventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event: SimulationEvent
    mission: Mission


def envelope(*, status: str, operation_id: str | None = None, mission_id: str | None = None, payload: dict | None = None, error: ServiceError | None = None) -> dict:
    result = {"ok": error is None, "status": status, "operation_id": operation_id, "mission_id": mission_id, "trace_id": str(uuid.uuid4())}
    if payload:
        result.update(payload)
    if error:
        result["error"] = {"code": error.code.value, "message": error.message, "retryable": error.retryable}
    return result


def error_http_status(error: ServiceError) -> int:
    if error.code in {ErrorCode.MISSION_BUSY, ErrorCode.STATE_STALE, ErrorCode.EVENT_OUT_OF_ORDER}:
        return 409
    if error.code in {
        ErrorCode.AI_UNAVAILABLE,
        ErrorCode.AI_TIMEOUT,
        ErrorCode.PROVIDER_RATE_LIMIT,
        ErrorCode.VERIFIER_UNAVAILABLE,
    }:
        return 503
    return 422


def build_service(
    settings: Settings,
    broker: StatusBroker,
    *,
    world: WorldPort | None = None,
    verifier: VerifierPort | None = None,
    execution: ExecutionPort | None = None,
    engine: ProposalEngine | None = None,
) -> tuple[MissionService, NebiusClient, TavilyContextClient]:
    # Defaults are development fixtures; production callers inject external adapters.
    world = world or MockWorldPort()
    verifier = verifier or MockVerifierPort()
    execution = execution or MockExecutionPort()
    client = NebiusClient(settings)
    context = TavilyContextClient(settings)
    parser = (
        NebiusMissionParser(client, ModelRouter(settings))
        if settings.nebius_api_key and settings.nebius_model_fast
        else None
    )
    if engine is None:
        engine = (
            NebiusProposalEngine(client, ModelRouter(settings))
            if settings.nebius_api_key and settings.nebius_model_planner
            else StaticProposalEngine()
        )
    if settings.app_mode == "production" and any(getattr(x, "is_mock", False) for x in (world, verifier, execution, engine)):
        raise RuntimeError("production refuses mock world, verifier, executor, or proposal adapters")
    return (
        MissionService(
            world,
            verifier,
            execution,
            engine,
            settings.max_repair_attempts,
            context_provider=context,
            status_publisher=broker,
            mission_parser=parser,
        ),
        client,
        context,
    )


def create_app(
    settings: Settings | None = None, service_factory: ServiceFactory | None = None
) -> FastAPI:
    config = settings or get_settings()
    broker = StatusBroker()
    rate_limiter = FixedWindowRateLimiter(
        config.api_rate_limit_requests, config.api_rate_limit_window_s
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        config.validate_production()
        factory = service_factory or build_service
        service, client, context = factory(config, broker)
        app.state.service, app.state.nebius, app.state.context = service, client, context
        await client.start()
        await context.start()
        yield
        await context.close()
        await client.close()

    app = FastAPI(
        title="SkyWarden mission intelligence",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None if config.app_mode == "production" else "/docs",
        redoc_url=None if config.app_mode == "production" else "/redoc",
    )
    app.state.status_broker = broker
    app.add_middleware(CORSMiddleware, allow_origins=config.allowed_origins, allow_credentials=config.api_auth_mode != "none", allow_methods=["GET", "POST"], allow_headers=["Content-Type", "X-API-Key", "Idempotency-Key"])

    @app.middleware("http")
    async def inbound_limits(request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                too_large = int(content_length) > config.max_request_body_bytes
            except ValueError:
                too_large = True
            if too_large:
                return JSONResponse(status_code=413, content={"detail": "request body too large"})
        if request.url.path.startswith("/api/"):
            identity = request.headers.get("x-api-key") or (
                request.client.host if request.client else "unknown"
            )
            if not await rate_limiter.allow(identity):
                return JSONResponse(
                    status_code=429,
                    content={"detail": "request rate limit exceeded"},
                    headers={"Retry-After": str(config.api_rate_limit_window_s)},
                )
        return await call_next(request)

    async def authorized(x_api_key: Annotated[str | None, Header()] = None) -> None:
        if config.api_auth_mode == "dev-key":
            expected = config.dev_api_key.get_secret_value() if config.dev_api_key else None
            if not expected or x_api_key != expected:
                raise HTTPException(401, "invalid API key")

    async def event_authorized(x_api_key: Annotated[str | None, Header()] = None) -> None:
        if config.app_mode == "production" or config.event_api_key:
            expected = (
                config.event_api_key.get_secret_value() if config.event_api_key else None
            )
            if not expected or x_api_key != expected:
                raise HTTPException(401, "invalid event publisher key")

    @app.exception_handler(ServiceError)
    async def service_error(_: Request, exc: ServiceError):
        return JSONResponse(status_code=error_http_status(exc), content=envelope(status="REJECTED", error=exc))

    @app.get("/health")
    async def health() -> dict:
        return {"ok": True, "service": "skywarden-backend"}

    @app.get("/ready")
    async def ready(request: Request) -> dict:
        try:
            catalog = await request.app.state.nebius.catalog()
            provider_error = None
        except ServiceError as exc:
            catalog = []
            provider_error = exc.code.value
        mandatory = {
            "fast": config.nebius_model_fast,
            "planner": config.nebius_model_planner,
            "replanner": config.nebius_model_replanner,
        }
        missing = [tier for tier, model_id in mandatory.items() if not model_id or model_id not in catalog]
        return {"ok": not missing, "mode": config.app_mode, "mock_adapters": config.app_mode != "production", "configured_models": catalog, "missing_mandatory_tiers": missing, "provider_error": provider_error, "tavily_enabled": config.tavily_enabled, "tavily_configured": bool(config.tavily_api_key)}

    @app.get("/api/v1/ai/models", dependencies=[Depends(authorized)])
    async def models(request: Request) -> dict:
        return {"models": await request.app.state.nebius.catalog(), "configured": {tier: config.configured_model(tier) for tier in ("fast", "planner", "complex", "replanner")}}

    @app.post("/api/v1/missions/parse", dependencies=[Depends(authorized)])
    async def parse_mission(body: ParseRequest, request: Request) -> dict:
        mission = await request.app.state.service.parse(body.operator_instruction, body.approved_area, body.approved_location_label, body.operator_id)
        return envelope(status="PARSED", mission_id=mission.mission_id, payload={"mission": mission.model_dump(mode="json")})

    @app.post("/api/v1/missions/{mission_id}/plan", dependencies=[Depends(authorized)])
    async def plan_mission(
        mission_id: str,
        body: PlanRequest,
        request: Request,
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ):
        if body.mission.mission_id != mission_id:
            raise ServiceError(ErrorCode.VALIDATION_FAILED, "path mission id differs from payload")
        operation_id = str(uuid.uuid4())
        stable_key = idempotency_key or f"mission-revision:{body.mission.revision}"
        operation = await request.app.state.service.plan(
            body.mission, operation_id, idempotency_key=stable_key
        )
        payload = {"attempt": operation.attempt, "plans": [p.model_dump(mode="json") for p in operation.plans], "verdicts": [v.model_dump(mode="json") for v in operation.verdicts], "handoff_ref": operation.handoff_ref, "context_status": operation.context_status, "context_latency_ms": operation.context_latency_ms, "context_warnings": operation.context_warnings}
        response = envelope(status=operation.status, operation_id=operation.operation_id, mission_id=mission_id, payload=payload, error=operation.error)
        if operation.error:
            return JSONResponse(status_code=error_http_status(operation.error), content=response)
        return response

    @app.get("/api/v1/missions/{mission_id}/planning-status", dependencies=[Depends(authorized)])
    async def planning_status(mission_id: str, request: Request) -> dict:
        operation = request.app.state.service.operations.get(mission_id)
        if not operation:
            raise HTTPException(404, "mission operation not found")
        return envelope(status=operation.status, operation_id=operation.operation_id, mission_id=mission_id, payload={"attempt": operation.attempt, "handoff_ref": operation.handoff_ref}, error=operation.error)

    @app.get("/api/v1/missions/{mission_id}/ai-traces", dependencies=[Depends(authorized)])
    async def ai_traces(mission_id: str, request: Request) -> dict:
        traces = [
            trace
            for trace in request.app.state.nebius.sanitized_traces()
            if trace.get("mission_id") == mission_id
        ]
        return {"mission_id": mission_id, "traces": traces}

    @app.post("/api/v1/events", dependencies=[Depends(event_authorized)])
    async def event(body: EventRequest, request: Request) -> dict:
        receipt = await request.app.state.service.receive_event(body.event, body.mission, str(uuid.uuid4()))
        return envelope(status=str(receipt["status"]), mission_id=body.event.mission_id, payload={"receipt": receipt})

    @app.get("/api/v1/benchmarks", dependencies=[Depends(authorized)])
    async def list_benchmarks() -> dict:
        root = config.bench_output_root
        if not root.exists():
            return {"runs": []}
        runs = []
        for path in sorted(root.glob("*/scoreboard.json")):
            import json

            manifest_path = path.parent / "run_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
            runs.append({"run_id": path.parent.name, **manifest})
        return {"runs": runs}

    def benchmark_path(run_id: str, filename: str) -> Path:
        if Path(run_id).name != run_id:
            raise HTTPException(404, "benchmark not found")
        path = config.bench_output_root / run_id / filename
        if not path.is_file():
            raise HTTPException(404, "benchmark not found")
        return path

    @app.get("/api/v1/benchmarks/{run_id}", dependencies=[Depends(authorized)])
    async def benchmark_summary(run_id: str) -> dict:
        import json

        scoreboard = json.loads(benchmark_path(run_id, "scoreboard.json").read_text(encoding="utf-8"))
        manifest = json.loads(benchmark_path(run_id, "run_manifest.json").read_text(encoding="utf-8"))
        return {"run_id": run_id, "manifest": manifest, "scoreboard": scoreboard}

    @app.get("/api/v1/benchmarks/{run_id}/scoreboard", dependencies=[Depends(authorized)])
    async def scoreboard(run_id: str) -> dict:
        import json

        return json.loads(benchmark_path(run_id, "scoreboard.json").read_text(encoding="utf-8"))

    @app.get("/api/v1/benchmarks/{run_id}/cases/{case_id}", dependencies=[Depends(authorized)])
    async def benchmark_case(run_id: str, case_id: str) -> dict:
        import json

        if Path(case_id).name != case_id or len(case_id) > 128:
            raise HTTPException(404, "benchmark case not found")
        results = json.loads(benchmark_path(run_id, "results.json").read_text(encoding="utf-8"))
        records = [record for record in results.get("records", []) if record.get("case_id") == case_id]
        if not records:
            raise HTTPException(404, "benchmark case not found")
        return {"run_id": run_id, "case_id": case_id, "records": records}

    @app.websocket("/ws/mission/{mission_id}")
    async def ws_mission(websocket: WebSocket, mission_id: str) -> None:
        if config.api_auth_mode == "dev-key":
            supplied = websocket.query_params.get("api_key")
            expected = config.dev_api_key.get_secret_value() if config.dev_api_key else None
            if not expected or supplied != expected:
                await websocket.close(code=4401)
                return
        await websocket.accept()
        try:
            operation = getattr(websocket.app.state, "service", None) and websocket.app.state.service.operations.get(mission_id)
            await websocket.send_json({"type": "STATUS_SNAPSHOT", "mission_id": mission_id, "status": operation.status if operation else "UNKNOWN"})
            async with broker.subscribe(mission_id) as queue:
                while True:
                    receive = asyncio.create_task(websocket.receive_text())
                    update = asyncio.create_task(queue.get())
                    done, pending = await asyncio.wait(
                        {receive, update}, return_when=asyncio.FIRST_COMPLETED
                    )
                    for task in pending:
                        task.cancel()
                    if update in done:
                        await websocket.send_json(update.result())
                    else:
                        receive.result()
        except WebSocketDisconnect:
            return

    return app


app = create_app()
