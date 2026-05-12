from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek

_AGENT_ROOT = Path(__file__).resolve().parent
_PROJECT_ROOT = _AGENT_ROOT.parent

_env_path = _PROJECT_ROOT / ".env"
if not _env_path.exists():
    _env_path = _AGENT_ROOT / ".env"
load_dotenv(_env_path)


def create_llm(temperature: float = 0.7, model: str | None = None) -> ChatDeepSeek:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("Missing DEEPSEEK_API_KEY in .env")

    kwargs: dict = {
        "model": model or os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro"),
        "temperature": temperature,
        "api_key": api_key,
    }
    api_base = os.getenv("DEEPSEEK_API_BASE")
    if api_base:
        kwargs["api_base"] = api_base

    return ChatDeepSeek(**kwargs)
