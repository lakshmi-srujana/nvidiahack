from __future__ import annotations

from pathlib import Path

_PROMPTS = {
    "parser": ("parser_v1.md", "parser_v1"),
    "planner": ("planner_v1.md", "planner_v1"),
    "repair": ("repair_v1.md", "repair_v1"),
    "replanner": ("replanner_v1.md", "replanner_v1"),
    "redteam": ("redteam_v1.md", "redteam_v1"),
}


def load_prompt(stage: str) -> tuple[str, str]:
    try:
        filename, revision = _PROMPTS[stage]
    except KeyError as exc:
        raise ValueError(f"unknown prompt stage: {stage}") from exc
    text = Path(__file__).with_name(filename).read_text(encoding="utf-8").strip()
    return text, revision


__all__ = ["load_prompt"]
