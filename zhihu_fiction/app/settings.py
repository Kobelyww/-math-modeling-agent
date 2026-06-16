"""Web runtime settings for the FastAPI application."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


TRUE_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class WebSettings:
    app_env: str = "development"
    cors_origins: list[str] = field(default_factory=lambda: ["*"])
    require_auth: bool = False
    web_api_token: str = ""
    expose_error_details: bool = True

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in TRUE_VALUES


def _cors_origins(value: str | None) -> list[str]:
    if value is None or not value.strip():
        return ["*"]
    return [part.strip() for part in value.split(",") if part.strip()]


def load_web_settings() -> WebSettings:
    app_env = (os.getenv("ZH_APP_ENV") or "development").strip().lower()
    production = app_env == "production"
    return WebSettings(
        app_env=app_env,
        cors_origins=_cors_origins(os.getenv("ZH_CORS_ORIGINS")),
        require_auth=_bool_env("ZH_REQUIRE_AUTH", production),
        web_api_token=os.getenv("ZH_WEB_API_TOKEN", ""),
        expose_error_details=_bool_env("ZH_EXPOSE_ERROR_DETAILS", not production),
    )
