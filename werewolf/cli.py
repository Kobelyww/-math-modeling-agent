"""AI 狼人杀 CLI 入口。"""

from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__" and __package__ is None:
    _parent = Path(__file__).resolve().parent.parent
    if str(_parent) not in sys.path:
        sys.path.insert(0, str(_parent))
    __package__ = "werewolf"

from .config import GameConfig, STANDARD_12
from .llm import create_llm
from .orchestrator import GameOrchestrator


def main() -> None:
    print("=" * 60)
    print("  AI 狼人杀 — 多智能体博弈系统")
    print("=" * 60)
    print(f"  12 人标准局：4狼 4民 预言家 女巫 猎人 白痴")
    print(f"  模型：DeepSeek V4")
    print()

    llm = create_llm(temperature=0.7)
    config = GameConfig()
    orch = GameOrchestrator(llm, config=config, verbose=True)
    result = orch.run_game()

    print(f"\n对局日志已保存至 werewolf/output/")


if __name__ == "__main__":
    main()
