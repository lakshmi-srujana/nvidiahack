"""Probe configured Nebius models and write a credential-free capability report."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings
from app.errors import ServiceError
from app.llm.client import NebiusClient
from app.llm.router import ModelSelection

DEFAULT_OUTPUT = Path(__file__).resolve().parents[2] / "artifacts" / "model_capabilities.json"


async def probe(
    settings: Settings,
    run_completion: bool,
    json_mode: bool,
    selected_tiers: set[str] | None = None,
) -> dict:
    client = NebiusClient(settings)
    await client.start()
    try:
        catalog = await client.catalog()
        tiers = {
            tier: settings.configured_model(tier)
            for tier in ("fast", "planner", "complex", "replanner")
        }
        capabilities: list[dict] = []
        for tier, model_id in tiers.items():
            if not model_id:
                capabilities.append(
                    {"tier": tier, "model_id": None, "in_catalog": False, "status": "NOT_CONFIGURED"}
                )
                continue
            item = {
                "tier": tier,
                "model_id": model_id,
                "in_catalog": model_id in catalog,
                "status": "CATALOG_ONLY",
                "json_mode_tested": False,
                "structured_completion_ok": None,
            }
            should_probe = selected_tiers is None or tier in selected_tiers
            if run_completion and item["in_catalog"] and should_probe:
                item["json_mode_tested"] = json_mode
                try:
                    payload, trace = await client.json_completion(
                        ModelSelection(tier=tier, model_id=model_id, reason="capability-probe"),
                        "capability_probe",
                        [
                            {
                                "role": "system",
                                "content": "Return only a JSON object with probe_ok set to true.",
                            },
                            {"role": "user", "content": "Capability probe."},
                        ],
                        json_mode=json_mode,
                    )
                    item["structured_completion_ok"] = payload.get("probe_ok") is True
                    item["status"] = "PASS" if item["structured_completion_ok"] else "BAD_PAYLOAD"
                    item["trace"] = {
                        "latency_ms": trace.latency_ms,
                        "input_tokens": trace.input_tokens,
                        "output_tokens": trace.output_tokens,
                        "total_tokens": trace.total_tokens,
                        "response_truncated": trace.response_truncated,
                    }
                except ServiceError as exc:
                    item["structured_completion_ok"] = False
                    item["status"] = exc.code.value
            capabilities.append(item)
        return {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "endpoint": settings.nebius_base_url,
            "catalog_model_count": len(catalog),
            "catalog_models": sorted(catalog),
            "completion_probe_requested": run_completion,
            "capabilities": capabilities,
        }
    finally:
        await client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--run-completion",
        action="store_true",
        help="Make one potentially billable structured completion per configured model",
    )
    parser.add_argument(
        "--json-mode",
        action="store_true",
        help="Probe response_format=json_object; use only with --run-completion",
    )
    parser.add_argument(
        "--tier",
        action="append",
        choices=("fast", "planner", "complex", "replanner"),
        help="Limit completion probes to one or more tiers; catalog lookup still covers all tiers",
    )
    args = parser.parse_args()
    settings = Settings()
    if not settings.nebius_api_key:
        parser.error("NEBIUS_API_KEY must be configured in backend/.env")
    report = asyncio.run(
        probe(
            settings,
            args.run_completion,
            args.json_mode,
            set(args.tier) if args.tier else None,
        )
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
