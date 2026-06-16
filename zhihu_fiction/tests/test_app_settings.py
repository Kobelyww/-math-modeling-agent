"""Tests for web runtime settings."""
from __future__ import annotations

from zhihu_fiction.app.settings import load_web_settings
from zhihu_fiction.config import load_settings


def test_load_web_settings_defaults_to_development(monkeypatch):
    for key in [
        "ZH_APP_ENV",
        "ZH_CORS_ORIGINS",
        "ZH_REQUIRE_AUTH",
        "ZH_WEB_API_TOKEN",
        "ZH_EXPOSE_ERROR_DETAILS",
    ]:
        monkeypatch.delenv(key, raising=False)

    settings = load_web_settings()

    assert settings.app_env == "development"
    assert settings.cors_origins == ["*"]
    assert settings.require_auth is False
    assert settings.web_api_token == ""
    assert settings.expose_error_details is True
    assert settings.is_production is False


def test_load_web_settings_parses_production_env(monkeypatch):
    monkeypatch.setenv("ZH_APP_ENV", "production")
    monkeypatch.setenv("ZH_CORS_ORIGINS", "https://studio.example.com, https://admin.example.com")
    monkeypatch.setenv("ZH_REQUIRE_AUTH", "true")
    monkeypatch.setenv("ZH_WEB_API_TOKEN", "secret-token")
    monkeypatch.setenv("ZH_EXPOSE_ERROR_DETAILS", "false")

    settings = load_web_settings()

    assert settings.app_env == "production"
    assert settings.cors_origins == ["https://studio.example.com", "https://admin.example.com"]
    assert settings.require_auth is True
    assert settings.web_api_token == "secret-token"
    assert settings.expose_error_details is False
    assert settings.is_production is True


def test_load_settings_allows_missing_api_key_for_non_model_startup(monkeypatch, tmp_path):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    settings = load_settings(tmp_path / ".env")

    assert settings.api_key == ""
