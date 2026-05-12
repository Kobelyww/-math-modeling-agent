"""沙箱验证器：在隔离环境中测试修改后的 Agent 代码。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class SandboxResult:
    passed: bool
    win_rate: float
    games_played: int
    error_message: str = ""
    improvement: float = 0.0  # 相对原版的胜率变化


class Sandbox:
    def __init__(self, test_games: int = 5, improvement_threshold: float = -0.05) -> None:
        self.test_games = test_games
        self.improvement_threshold = improvement_threshold

    def test(
        self,
        original_code: str,
        modified_code: str,
        role: str,
        original_win_rate: float,
        run_game_fn: callable,
    ) -> SandboxResult:
        """在沙箱中测试修改后的代码。

        Args:
            original_code: 原始 Agent 源码
            modified_code: 修改后的 Agent 源码
            role: 角色名
            original_win_rate: 原始胜率
            run_game_fn: 对局运行函数，签名为 fn(code: str) -> float (胜率)

        Returns:
            沙箱测试结果
        """
        try:
            modified_win_rate = run_game_fn(modified_code)

            improvement = modified_win_rate - original_win_rate
            passed = improvement >= self.improvement_threshold

            return SandboxResult(
                passed=passed,
                win_rate=modified_win_rate,
                games_played=self.test_games,
                improvement=improvement,
                error_message="" if passed else f"胜率下降 {abs(improvement):.0%}，拒绝应用修改",
            )
        except Exception as exc:
            return SandboxResult(
                passed=False,
                win_rate=0.0,
                games_played=0,
                error_message=str(exc),
            )
