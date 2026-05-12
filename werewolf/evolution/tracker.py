"""进化追踪器：记录每代的表现变化。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class GenerationMetrics:
    generation: int
    games_played: int
    werewolf_wins: int
    good_wins: int
    avg_rounds: float
    role_prompts: dict[str, str] = field(default_factory=dict)

    @property
    def werewolf_win_rate(self) -> float:
        return self.werewolf_wins / self.games_played if self.games_played > 0 else 0.0

    @property
    def good_win_rate(self) -> float:
        return self.good_wins / self.games_played if self.games_played > 0 else 0.0


class EvolutionTracker:
    def __init__(self, data_dir: str | Path | None = None) -> None:
        self._data_dir = Path(data_dir) if data_dir else Path(__file__).resolve().parent.parent / "data"
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self.history: list[GenerationMetrics] = []
        self._load()

    def _load(self) -> None:
        path = self._data_dir / "evolution_history.json"
        if path.exists():
            data = json.loads(path.read_text())
            self.history = [GenerationMetrics(**m) for m in data]

    def _save(self) -> None:
        path = self._data_dir / "evolution_history.json"
        data = [
            {
                "generation": m.generation,
                "games_played": m.games_played,
                "werewolf_wins": m.werewolf_wins,
                "good_wins": m.good_wins,
                "avg_rounds": m.avg_rounds,
                "role_prompts": m.role_prompts,
            }
            for m in self.history
        ]
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def record_generation(self, metrics: GenerationMetrics) -> None:
        self.history.append(metrics)
        self._save()

    def improvement_summary(self) -> str:
        if len(self.history) < 2:
            return "需要至少两代数据才能对比。"

        first = self.history[0]
        last = self.history[-1]

        lines = [
            "# 进化对比",
            f"Gen {first.generation} → Gen {last.generation}",
            f"",
            f"| 指标 | Gen{first.generation} | Gen{last.generation} | 变化 |",
            f"|------|----------|----------|------|",
            f"| 狼人胜率 | {first.werewolf_win_rate:.0%} | {last.werewolf_win_rate:.0%} | {last.werewolf_win_rate - first.werewolf_win_rate:+.0%} |",
            f"| 好人胜率 | {first.good_win_rate:.0%} | {last.good_win_rate:.0%} | {last.good_win_rate - first.good_win_rate:+.0%} |",
            f"| 均轮数 | {first.avg_rounds:.1f} | {last.avg_rounds:.1f} | {last.avg_rounds - first.avg_rounds:+.1f} |",
        ]
        return "\n".join(lines)
