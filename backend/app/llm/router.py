from dataclasses import dataclass

from app.config import Settings
from app.errors import ErrorCode, ServiceError


@dataclass(frozen=True)
class ModelSelection:
    tier: str
    model_id: str
    reason: str


class ModelRouter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def select(self, stage: str, ambiguous: bool = False) -> ModelSelection:
        tier = {"parser": "complex" if ambiguous else "fast", "planner": "planner", "repair": "planner", "replanner": "replanner"}.get(stage)
        if tier is None:
            raise ValueError(f"unknown model stage: {stage}")
        model_id = self.settings.configured_model(tier)
        if not model_id or model_id.startswith("REPLACE_"):
            raise ServiceError(ErrorCode.AI_UNAVAILABLE, f"no verified {tier} model is configured")
        return ModelSelection(tier=tier, model_id=model_id, reason=f"policy:{stage}")
