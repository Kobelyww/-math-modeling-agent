from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

_AGENT_APP = Path(__file__).resolve().parent.parent.parent / "agent_app"
if str(_AGENT_APP) not in sys.path:
    sys.path.insert(0, str(_AGENT_APP))

from agent_app.base import BaseAgent as _BaseAgent


class WerewolfAgent(_BaseAgent):
    """狼人杀游戏 Agent 基类，继承通用的 LLM 调用、重试、错误分类。"""

    role: str = "未分配"
    team: str = "未分配"
    system_prompt: str = ""

    def __init__(self, llm, player_id: int, max_retries: int = 3) -> None:
        super().__init__(llm, max_retries=max_retries)
        self.player_id = player_id
        self._game_history: list[str] = []

    def observe(self, event: str) -> None:
        self._game_history.append(event)

    def _history_summary(self, max_items: int = 30) -> str:
        return "\n".join(self._game_history[-max_items:])

    def decide(self, prompt: str) -> str:
        full_prompt = f"游戏历史：\n{self._history_summary()}\n\n{prompt}"
        return self.invoke(full_prompt)

    @staticmethod
    def extract_number(text: str, max_n: int = 11) -> int | None:
        match = re.search(r"(\d+)\s*号", text)
        if match:
            num = int(match.group(1))
            if 0 <= num <= max_n:
                return num
        return None

    @staticmethod
    def extract_yes_no(text: str) -> bool | None:
        if re.search(r"是|使用|救|毒|开枪|翻牌|跳|报", text):
            return True
        if re.search(r"否|不|不用|放弃|跳过|隐藏", text):
            return False
        return None
