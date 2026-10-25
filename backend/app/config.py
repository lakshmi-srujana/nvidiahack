from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_mode: Literal["development", "test", "production"] = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    allowed_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )
    api_auth_mode: Literal["none", "dev-key"] = "none"
    dev_api_key: SecretStr | None = None
    event_api_key: SecretStr | None = None
    nebius_api_key: SecretStr | None = None
    nebius_base_url: str = "https://api.tokenfactory.nebius.com/v1/"
    nebius_model_fast: str | None = None
    nebius_model_planner: str | None = None
    nebius_model_complex: str | None = None
    nebius_model_replanner: str | None = None
    nebius_json_mode_models: Annotated[list[str], NoDecode] = Field(default_factory=list)
    nebius_timeout_s: float = 35.0
    nebius_max_concurrent_calls: int = 2
    nebius_max_provider_retries: int = 2
    tavily_api_key: SecretStr | None = None
    tavily_enabled: bool = False
    tavily_context_char_limit: int = 5000
    tavily_timeout_s: float = 10.0
    tavily_cache_ttl_s: int = 900
    tavily_max_results: int = 4
    max_repair_attempts: int = 3
    max_request_body_bytes: int = 1_000_000
    api_rate_limit_requests: int = 120
    api_rate_limit_window_s: int = 60
    bench_output_root: Path = Path("../results")

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def split_origins(cls, value: object) -> object:
        return [item.strip() for item in value.split(",") if item.strip()] if isinstance(value, str) else value

    @field_validator("nebius_json_mode_models", mode="before")
    @classmethod
    def split_model_ids(cls, value: object) -> object:
        return [item.strip() for item in value.split(",") if item.strip()] if isinstance(value, str) else value

    @field_validator("dev_api_key", "event_api_key", "nebius_api_key", "tavily_api_key", mode="before")
    @classmethod
    def ignore_placeholder_secrets(cls, value: object) -> object:
        if isinstance(value, str) and (not value.strip() or value.startswith("REPLACE_")):
            return None
        return value

    @field_validator(
        "nebius_model_fast",
        "nebius_model_planner",
        "nebius_model_complex",
        "nebius_model_replanner",
        mode="before",
    )
    @classmethod
    def ignore_placeholder_models(cls, value: object) -> object:
        if isinstance(value, str) and (not value.strip() or value.startswith("REPLACE_")):
            return None
        return value

    def configured_model(self, tier: str) -> str | None:
        return getattr(self, f"nebius_model_{tier}")

    def validate_production(self) -> None:
        if self.app_mode == "production":
            if not self.nebius_api_key or not all(
                (self.nebius_model_fast, self.nebius_model_planner, self.nebius_model_replanner)
            ):
                raise RuntimeError(
                    "production requires Nebius credentials and fast/planner/replanner models"
                )
            if self.api_auth_mode == "none":
                raise RuntimeError("production requires API authentication")
            if not self.event_api_key:
                raise RuntimeError("production requires a separate event publisher key")
            if "*" in self.allowed_origins:
                raise RuntimeError("production requires an explicit CORS allowlist")


@lru_cache
def get_settings() -> Settings:
    return Settings()
