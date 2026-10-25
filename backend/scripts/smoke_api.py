"""Smoke a running SkyWarden API without hiding readiness failures."""
from __future__ import annotations

import argparse
import json
from uuid import uuid4

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--api-key")
    parser.add_argument("--expect-ready", action="store_true")
    parser.add_argument(
        "--exercise-mock",
        action="store_true",
        help="Submit a fixed survey mission; use only against development/test mode",
    )
    args = parser.parse_args()
    headers = {"X-API-Key": args.api_key} if args.api_key else {}
    report: dict[str, object] = {}
    with httpx.Client(base_url=args.base_url, headers=headers, timeout=15) as client:
        health = client.get("/health")
        health.raise_for_status()
        report["health"] = health.json()
        ready = client.get("/ready")
        ready.raise_for_status()
        report["ready"] = ready.json()
        openapi = client.get("/openapi.json")
        openapi.raise_for_status()
        report["openapi_path_count"] = len(openapi.json().get("paths", {}))
        if args.exercise_mock:
            parsed = client.post(
                "/api/v1/missions/parse",
                json={
                    "operator_instruction": "Survey the approved smoke-test polygon",
                    "approved_area": [
                        {"longitude": 77.58, "latitude": 12.96},
                        {"longitude": 77.60, "latitude": 12.96},
                        {"longitude": 77.60, "latitude": 12.98},
                    ],
                    "approved_location_label": "smoke-test sector",
                    "operator_id": "smoke-test",
                },
            )
            parsed.raise_for_status()
            mission = parsed.json()["mission"]
            planned = client.post(
                f"/api/v1/missions/{mission['mission_id']}/plan",
                headers={**headers, "Idempotency-Key": str(uuid4())},
                json={"mission": mission},
            )
            planned.raise_for_status()
            report["plan"] = {
                "status": planned.json()["status"],
                "handoff_ref_present": bool(planned.json().get("handoff_ref")),
                "context_status": planned.json().get("context_status"),
            }
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.expect_ready and not report["ready"]["ok"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
