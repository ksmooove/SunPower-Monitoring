from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    site_name: str = "Home"
    site_timezone: str = "America/Los_Angeles"

    pvs_host: str = "192.168.1.96"
    pvs_port: int = 443
    pvs_scheme: str = "https"
    pvs_verify_tls: bool = False
    pvs_username: str = "ssm_owner"
    pvs_password: SecretStr = SecretStr("")

    pvs_poll_interval_seconds: int = Field(default=300, ge=60)
    pvs_request_timeout_seconds: float = Field(default=30.0, gt=0)
    pvs_max_concurrency: int = Field(default=1, ge=1, le=1)
    pvs_circuit_breaker_failures: int = Field(default=3, ge=1)
    pvs_circuit_breaker_reset_seconds: float = Field(default=900.0, gt=0)

    log_level: str = "INFO"
    log_redact: bool = True

    @property
    def pvs_base_url(self) -> str:
        return f"{self.pvs_scheme}://{self.pvs_host}:{self.pvs_port}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
