"""跨模型/版本排行榜。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class LeaderboardEntry:
    model_name: str
    prompt_version: str
    games_played: int = 0
    werewolf_wins: int = 0
    good_wins: int = 0
    avg_rounds: float = 0.0
    role_scores: dict[str, float] = field(default_factory=dict)

    @property
    def total_wins(self) -> int:
        return self.werewolf_wins + self.good_wins

    @property
    def win_rate(self) -> float:
        return self.total_wins / self.games_played if self.games_played > 0 else 0.0

    @property
    def werewolf_win_rate(self) -> float:
        werewolf_games = self.games_played / 2
        return self.werewolf_wins / werewolf_games if werewolf_games > 0 else 0.0

    @property
    def good_win_rate(self) -> float:
        good_games = self.games_played / 2
        return self.good_wins / good_games if good_games > 0 else 0.0


class Leaderboard:
    def __init__(self, data_dir: str | Path | None = None) -> None:
        self._data_dir = Path(data_dir) if data_dir else Path(__file__).resolve().parent.parent / "data"
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self.entries: dict[str, LeaderboardEntry] = {}
        self._load()

    def _key(self, model: str, version: str) -> str:
        return f"{model}__{version}"

    def _load(self) -> None:
        path = self._data_dir / "leaderboard.json"
        if path.exists():
            data = json.loads(path.read_text())
            for k, v in data.items():
                self.entries[k] = LeaderboardEntry(**v)

    def _save(self) -> None:
        path = self._data_dir / "leaderboard.json"
        data = {}
        for k, entry in self.entries.items():
            data[k] = {
                "model_name": entry.model_name,
                "prompt_version": entry.prompt_version,
                "games_played": entry.games_played,
                "werewolf_wins": entry.werewolf_wins,
                "good_wins": entry.good_wins,
                "avg_rounds": entry.avg_rounds,
                "role_scores": entry.role_scores,
            }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def record_game(
        self,
        model: str,
        version: str,
        winner: str,
        total_rounds: int,
        role_scores: dict[str, float] | None = None,
    ) -> None:
        key = self._key(model, version)
        if key not in self.entries:
            self.entries[key] = LeaderboardEntry(model_name=model, prompt_version=version)

        entry = self.entries[key]
        entry.games_played += 1
        if winner == "狼人阵营":
            entry.werewolf_wins += 1
        else:
            entry.good_wins += 1

        entry.avg_rounds = (entry.avg_rounds * (entry.games_played - 1) + total_rounds) / entry.games_played

        if role_scores:
            for role, score in role_scores.items():
                old = entry.role_scores.get(role, 0.0)
                entry.role_scores[role] = (old * (entry.games_played - 1) + score) / entry.games_played

        self._save()

    def rankings(self) -> list[LeaderboardEntry]:
        return sorted(self.entries.values(), key=lambda e: e.win_rate, reverse=True)

    def report(self) -> str:
        lines = [
            "# 🏆 狼人杀 Agent Leaderboard",
            "",
            "| 排名 | 模型 | 版本 | 场次 | 胜率 | 狼人胜率 | 好人胜率 | 均轮数 |",
            "|------|------|------|------|------|----------|----------|--------|",
        ]
        for i, entry in enumerate(self.rankings(), 1):
            lines.append(
                f"| {i} | {entry.model_name} | {entry.prompt_version} "
                f"| {entry.games_played} | {entry.win_rate:.0%} "
                f"| {entry.werewolf_win_rate:.0%} | {entry.good_win_rate:.0%} "
                f"| {entry.avg_rounds:.1f} |"
            )
        return "\n".join(lines)
