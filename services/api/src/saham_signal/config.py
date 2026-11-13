import re
from typing import Self
from urllib.parse import unquote, urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from saham_signal.domain.mode import Mode


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", frozen=True, hide_input_in_errors=True)

    app_mode: Mode = "research"
    database_url: SecretStr = SecretStr(
        "postgresql://saham_signal_research:local_only_research@127.0.0.1:5432/saham_signal_research"
    )
    redis_url: SecretStr = SecretStr("redis://:local_redis_research@127.0.0.1:6379/0")
    redis_namespace: str = "saham-signal:research:"
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    readiness_timeout_seconds: float = Field(default=3, ge=0.1, le=10)
    session_secret: SecretStr | None = None
    pilot_account_id: str | None = None
    market_fixture_enabled: bool = False
    market_fixture_token: SecretStr | None = None
    market_nominal_idr: str = Field(
        default="1000000.00",
        pattern=r"^(?:0\.(?:0[1-9]|[1-9][0-9])|[1-9][0-9]{0,15}\.[0-9]{2})$",
    )
    market_horizon_minutes: int = Field(default=30)

    @model_validator(mode="after")
    def validate_market_fixture(self) -> Self:
        if (
            self.market_fixture_enabled
            and self.pilot_account_id
            and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", self.pilot_account_id)
        ):
            raise ValueError("Invalid fixture account identifier")
        if self.market_horizon_minutes not in {15, 30, 60, 240}:
            raise ValueError("Unsupported market horizon")
        if self.market_fixture_enabled and (
            self.app_mode != "research"
            or not self.market_fixture_token
            or len(self.market_fixture_token.get_secret_value()) < 32
        ):
            raise ValueError("Market fixtures require research mode and a 32+ character token")
        return self

    @field_validator("cors_origins")
    @classmethod
    def validate_origins(cls, origins: list[str]) -> list[str]:
        for origin in origins:
            parts = urlsplit(origin)
            if (
                parts.scheme not in {"http", "https"}
                or not parts.hostname
                or "*" in origin
                or parts.username is not None
                or parts.password is not None
                or parts.path
                or parts.query
                or parts.fragment
                or not parts.port
                and parts.netloc.endswith(":")
            ):
                raise ValueError("CORS_ORIGINS must contain explicit HTTP(S) origins without paths")
        return origins

    @model_validator(mode="after")
    def validate_isolation(self) -> Self:
        database = urlsplit(self.database_url.get_secret_value())
        redis = urlsplit(self.redis_url.get_secret_value())
        if (
            database.scheme not in {"postgresql", "postgres"}
            or not database.hostname
            or unquote(database.path) != f"/saham_signal_{self.app_mode}"
            or database.query
            or database.fragment
        ):
            raise ValueError(
                "DATABASE_URL must target saham_signal_<APP_MODE>, without query overrides"
            )
        if (
            redis.scheme not in {"redis", "rediss"}
            or not redis.hostname
            or redis.query
            or redis.fragment
        ):
            raise ValueError("REDIS_URL must be a Redis URL without query overrides")
        if self.redis_namespace != f"saham-signal:{self.app_mode}:":
            raise ValueError("REDIS_NAMESPACE must match APP_MODE")
        if self.app_mode != "research" and (
            not self.session_secret
            or len(self.session_secret.get_secret_value()) < 32
            or not self.pilot_account_id
        ):
            raise ValueError(
                "Paper/live require SESSION_SECRET (32+ characters) and PILOT_ACCOUNT_ID"
            )
        return self


def load_settings() -> Settings:
    try:
        return Settings()
    except ValueError:
        # A settings parser error may include raw environment values, including secrets.
        raise RuntimeError(
            "Invalid backend configuration; check API README and environment"
        ) from None
