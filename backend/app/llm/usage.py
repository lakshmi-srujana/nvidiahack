from __future__ import annotations

import json
from pathlib import Path


class PriceCatalog:
    """Uses price data only when the file explicitly declares it verified."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.document: dict = {}
        if path.is_file():
            try:
                self.document = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                self.document = {}

    def estimate(
        self, model_id: str, input_tokens: int | None, output_tokens: int | None
    ) -> tuple[float | None, str]:
        if input_tokens is None or output_tokens is None:
            return None, "unknown_usage"
        if self.document.get("status") != "verified":
            return None, "unknown_unverified_price"
        rates = self.document.get("models", {}).get(model_id)
        if not isinstance(rates, dict):
            return None, "unknown_model_price"
        input_rate = rates.get("input_usd_per_million")
        output_rate = rates.get("output_usd_per_million")
        if not isinstance(input_rate, (int, float)) or not isinstance(
            output_rate, (int, float)
        ):
            return None, "unknown_model_price"
        value = input_tokens / 1_000_000 * input_rate + output_tokens / 1_000_000 * output_rate
        return value, "estimated_from_verified_price"
