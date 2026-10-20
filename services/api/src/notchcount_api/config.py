"""All configuration is read here, from environment variables prefixed NC_ (or a .env file)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="NC_", env_file=REPO_ROOT / ".env", extra="ignore", frozen=True
    )

    env: Literal["dev", "test", "prod"] = "dev"
    database_url: SecretStr
    db_schema: str = "notchcount"
    session_secret: SecretStr
    blob_signing_secret: SecretStr
    session_days: int = 7
    signed_url_seconds: int = 300
    public_base_url: str = "http://localhost:5173"
    cors_origins: list[str] = Field(default_factory=list)

    auth_provider: Literal["invite", "mojoauth"] = "invite"
    mojoauth_api_key: SecretStr | None = None
    mojoauth_base_url: str = "https://api.mojoauth.com"

    agentboxd_base_url: str = "https://api.agentboxd.com/v1"
    agentboxd_draft_key: SecretStr | None = None
    agentboxd_send_key: SecretStr | None = None
    agentboxd_webhook_secret: SecretStr | None = None

    max_upload_bytes: int = 6 * 1024 * 1024
    upload_rate_per_minute: int = 120
    auth_rate_per_10min: int = 5
    poor_gps_accuracy_m: float = 30.0
    pass_start_tolerance_min: int = 15
    upload_grace_after_end_min: int = 5

    static_dir: Path | None = REPO_ROOT / "apps" / "web" / "build"
    run_worker_inprocess: bool = False

    @field_validator(
        "mojoauth_api_key",
        "agentboxd_draft_key",
        "agentboxd_send_key",
        "agentboxd_webhook_secret",
        mode="before",
    )
    @classmethod
    def _blank_is_unset(cls, v: object) -> object:
        # An empty env var must mean "not configured", never "an empty secret anyone can sign with".
        return None if v in ("", None) else v

    @property
    def secure_cookies(self) -> bool:
        return self.env == "prod"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
