from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

APP_ROOT = Path(__file__).resolve().parent

MODEL_ALIASES = {
    "deepseek-v4": "deepseek-v4-pro",
}


@dataclass(frozen=True)
class AgentConfig:
    role: str
    temperature: float = 0.3
    max_tokens: int = 0  # 0 表示不限制，使用模型默认值


@dataclass(frozen=True)
class Settings:
    api_key: str
    api_base: str | None
    model: str
    temperature: float
    max_retries: int = 3
    retry_delay: float = 1.0
    tool_timeout: int = 30
    sandbox_memory_mb: int = 512
    max_tokens: int = 0
    agent_configs: dict[str, AgentConfig] = field(default_factory=dict)
    embedding_api_key: str | None = None

    def get_agent_config(self, role: str) -> AgentConfig:
        return self.agent_configs.get(role, AgentConfig(role=role, temperature=self.temperature))


def load_settings(env_path: str | Path | None = None) -> Settings:
    if env_path is None:
        candidates = [APP_ROOT / ".env", APP_ROOT.parent / ".env"]
        env_path = next((p for p in candidates if p.exists()), candidates[0])

    load_dotenv(env_path)

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("Missing DEEPSEEK_API_KEY in .env")

    temperature = float(os.getenv("DEEPSEEK_TEMPERATURE", "0.3"))
    raw_model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro")
    model = MODEL_ALIASES.get(raw_model, raw_model)
    max_retries = int(os.getenv("DEEPSEEK_MAX_RETRIES", "3"))
    retry_delay = float(os.getenv("DEEPSEEK_RETRY_DELAY", "1.0"))
    tool_timeout = int(os.getenv("TOOL_TIMEOUT", "30"))
    sandbox_memory_mb = int(os.getenv("SANDBOX_MEMORY_MB", "512"))
    max_tokens = int(os.getenv("DEEPSEEK_MAX_TOKENS", "0"))

    agent_configs: dict[str, AgentConfig] = {}
    for role in ["data_engineer", "modeler", "programmer", "code_debugger", "writer", "reviewer", "synthesizer"]:
        temp_key = f"DEEPSEEK_{role.upper()}_TEMPERATURE"
        tokens_key = f"DEEPSEEK_{role.upper()}_MAX_TOKENS"
        if temp_key in os.environ or tokens_key in os.environ:
            agent_configs[role] = AgentConfig(
                role=role,
                temperature=float(os.getenv(temp_key, "0.3")),
                max_tokens=int(os.getenv(tokens_key, "0")),
            )

    embedding_api_key = os.getenv("EMBEDDING_API_KEY", api_key)

    return Settings(
        api_key=api_key,
        api_base=os.getenv("DEEPSEEK_API_BASE") or None,
        model=model,
        temperature=temperature,
        max_retries=max_retries,
        retry_delay=retry_delay,
        tool_timeout=tool_timeout,
        sandbox_memory_mb=sandbox_memory_mb,
        max_tokens=max_tokens,
        agent_configs=agent_configs,
        embedding_api_key=embedding_api_key,
    )