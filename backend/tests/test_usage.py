import json
from pathlib import Path

from app.llm.prompts import load_prompt
from app.llm.usage import PriceCatalog


def test_prompt_store_returns_versioned_content() -> None:
    content, revision = load_prompt("planner")
    assert revision == "planner_v1"
    assert "external verifier" in content.lower()


def test_unverified_or_missing_prices_never_invent_cost(tmp_path: Path) -> None:
    path = tmp_path / "prices.json"
    path.write_text(
        json.dumps(
            {
                "status": "unverified",
                "models": {
                    "model": {
                        "input_usd_per_million": 1,
                        "output_usd_per_million": 2,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    assert PriceCatalog(path).estimate("model", 100, 50) == (
        None,
        "unknown_unverified_price",
    )
    assert PriceCatalog(tmp_path / "missing.json").estimate("model", 100, 50) == (
        None,
        "unknown_unverified_price",
    )


def test_verified_price_uses_per_million_token_arithmetic(tmp_path: Path) -> None:
    path = tmp_path / "prices.json"
    path.write_text(
        json.dumps(
            {
                "status": "verified",
                "source": "provider-price-sheet",
                "snapshot_date": "2026-10-26",
                "models": {
                    "model": {
                        "input_usd_per_million": 2,
                        "output_usd_per_million": 4,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    cost, status = PriceCatalog(path).estimate("model", 1_000_000, 500_000)
    assert cost == 4
    assert status == "estimated_from_verified_price"
