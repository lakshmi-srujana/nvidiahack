"""Export/check temporary JSON Schema until the shared schema package replaces it."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.contracts import Mission, Plan, SimulationEvent, VerificationResult

OUTPUT = Path(__file__).resolve().parents[2] / "contracts" / "generated" / "provisional-adapter-schemas.json"


def document() -> dict:
    return {
        "$comment": "PROVISIONAL adapter schemas; replace after shared contract freeze.",
        "models": {
            "Mission": Mission.model_json_schema(),
            "Plan": Plan.model_json_schema(),
            "SimulationEvent": SimulationEvent.model_json_schema(),
            "VerificationResult": VerificationResult.model_json_schema(),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = json.dumps(document(), indent=2, sort_keys=True) + "\n"
    if args.check:
        return 0 if OUTPUT.is_file() and OUTPUT.read_text(encoding="utf-8") == expected else 1
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(expected, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
