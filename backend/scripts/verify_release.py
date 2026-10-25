"""Run local release gates and emit a machine-readable result."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(name: str, command: list[str]) -> dict:
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    return {
        "name": name,
        "ok": completed.returncode == 0,
        "exit_code": completed.returncode,
        "output": (completed.stdout + completed.stderr)[-4000:],
    }


def main() -> int:
    checks = [
        run("dependency_integrity", [sys.executable, "-m", "pip", "check"]),
        run("lint", [sys.executable, "-m", "ruff", "check", "app", "bench", "tests", "scripts"]),
        run("tests", [sys.executable, "-m", "pytest", "-q"]),
        run("schema_drift", [sys.executable, "scripts/export_contracts.py", "--check"]),
    ]
    payload = {"ok": all(check["ok"] for check in checks), "checks": checks}
    print(json.dumps(payload, indent=2))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
