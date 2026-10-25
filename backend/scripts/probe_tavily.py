"""Run one explicit Tavily context probe using credentials from backend/.env."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings
from app.context import TavilyContextClient
from app.contracts import Mission, Point


async def probe(settings: Settings, location: str) -> dict:
    client = TavilyContextClient(settings)
    mission = Mission(
        approved_area=[
            Point(longitude=0.0, latitude=0.0),
            Point(longitude=0.001, latitude=0.0),
            Point(longitude=0.001, latitude=0.001),
        ],
        approved_location_label=location,
        operator_id="context-probe",
    )
    await client.start()
    try:
        return (await client.context_for(mission)).model_dump(mode="json")
    finally:
        await client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--location", required=True, help="Approved descriptive location label")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    settings = Settings()
    if not settings.tavily_enabled or not settings.tavily_api_key:
        parser.error("set TAVILY_ENABLED=true and TAVILY_API_KEY in backend/.env")
    payload = asyncio.run(probe(settings, args.location))
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
