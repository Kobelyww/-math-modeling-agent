from agent_app.config import Settings, load_settings


ROUTING_ENV_KEYS = [
    "LLM_PROVIDER",
    "VISION_PROVIDER",
    "TEXT_AGENT_PROVIDER",
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_API_BASE",
    "DEEPSEEK_MODEL",
    "DEEPSEEK_TEMPERATURE",
    "DEEPSEEK_MAX_RETRIES",
    "DEEPSEEK_RETRY_DELAY",
    "DEEPSEEK_MAX_TOKENS",
    "MIMO_API_KEY",
    "MIMO_API_BASE",
    "MIMO_MODEL",
    "MIMO_VISION_MODEL",
    "EMBEDDING_API_KEY",
]


def _clear_routing_env(monkeypatch):
    for key in ROUTING_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_settings_separates_mimo_vision_from_deepseek_text(tmp_path, monkeypatch):
    _clear_routing_env(monkeypatch)

    env = tmp_path / ".env"
    env.write_text(
        "VISION_PROVIDER=mimo\n"
        "MIMO_API_KEY=mimo-key\n"
        "MIMO_API_BASE=https://api.xiaomimimo.com/v1\n"
        "MIMO_VISION_MODEL=mimo-v2.5-pro\n"
        "TEXT_AGENT_PROVIDER=deepseek\n"
        "DEEPSEEK_API_KEY=deepseek-key\n"
        "DEEPSEEK_API_BASE=https://api.deepseek.com\n"
        "DEEPSEEK_MODEL=deepseek-v4-pro\n",
        encoding="utf-8",
    )

    settings = load_settings(env)

    assert settings.vision_provider == "mimo"
    assert settings.vision_model == "mimo-v2.5-pro"
    assert settings.text_agent_provider == "deepseek"
    assert settings.model == "deepseek-v4-pro"
    assert settings.api_key == "deepseek-key"


def test_legacy_mimo_provider_still_loads_for_visual_only_config(tmp_path, monkeypatch):
    _clear_routing_env(monkeypatch)

    env = tmp_path / ".env"
    env.write_text(
        "LLM_PROVIDER=mimo\n"
        "MIMO_API_KEY=mimo-key\n"
        "MIMO_API_BASE=https://api.xiaomimimo.com/v1\n"
        "MIMO_MODEL=mimo-v2.5-pro\n"
        "DEEPSEEK_API_KEY=deepseek-key\n"
        "DEEPSEEK_MODEL=deepseek-v4-pro\n",
        encoding="utf-8",
    )

    settings = load_settings(env)

    assert settings.vision_provider == "mimo"
    assert settings.text_agent_provider == "deepseek"
    assert settings.api_key == "deepseek-key"


def test_legacy_mimo_provider_without_deepseek_key_keeps_text_fallback(tmp_path, monkeypatch):
    _clear_routing_env(monkeypatch)

    env = tmp_path / ".env"
    env.write_text(
        "LLM_PROVIDER=mimo\n"
        "MIMO_API_KEY=mimo-key\n"
        "MIMO_API_BASE=https://api.xiaomimimo.com/v1\n"
        "MIMO_MODEL=mimo-v2.5-pro\n",
        encoding="utf-8",
    )

    settings = load_settings(env)

    assert settings.vision_provider == "mimo"
    assert settings.text_agent_provider == "mimo"
    assert settings.api_key == "mimo-key"
    assert settings.api_base == "https://api.xiaomimimo.com/v1"
    assert settings.model == "mimo-v2.5-pro"


def test_env_file_does_not_override_existing_runtime_env(tmp_path, monkeypatch):
    _clear_routing_env(monkeypatch)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "runtime-key")
    monkeypatch.setenv("DEEPSEEK_MODEL", "runtime-model")

    env = tmp_path / ".env"
    env.write_text(
        "DEEPSEEK_API_KEY=file-key\n"
        "DEEPSEEK_MODEL=file-model\n",
        encoding="utf-8",
    )

    settings = load_settings(env)

    assert settings.api_key == "runtime-key"
    assert settings.model == "runtime-model"


def test_settings_preserves_existing_positional_optional_fields():
    settings = Settings(
        "key",
        "https://api.deepseek.com",
        "deepseek-v4-pro",
        0.3,
        5,
        2.0,
        45,
        1024,
        4096,
    )

    assert settings.max_retries == 5
    assert settings.retry_delay == 2.0
    assert settings.tool_timeout == 45
    assert settings.sandbox_memory_mb == 1024
    assert settings.max_tokens == 4096
    assert settings.vision_provider == "mimo"
    assert settings.text_agent_provider == "deepseek"


def test_mimo_table_vision_config_uses_settings_vision_fields(monkeypatch):
    _clear_routing_env(monkeypatch)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")

    from agent_app.web import routes as routes_module

    _clear_routing_env(monkeypatch)
    settings = Settings(
        api_key="deepseek-key",
        api_base="https://api.deepseek.com",
        model="deepseek-v4-pro",
        temperature=0.3,
        vision_api_key="vision-key",
        vision_api_base="https://vision.example/v1/",
        vision_model="mimo-v2.5-pro",
        text_agent_provider="deepseek",
        llm_provider="deepseek",
    )
    monkeypatch.setattr(routes_module, "_settings", settings)

    config = routes_module._mimo_table_vision_config()

    assert config == {
        "api_key": "vision-key",
        "api_base": "https://vision.example/v1",
        "model": "mimo-v2.5-pro",
    }
