"""多维评测指标计算。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RoleMetrics:
    role: str
    player_id: int
    survived: bool
    speeches_count: int = 0
    votes_against_wolves: int = 0
    votes_against_good: int = 0
    total_votes: int = 0
    speech_quality_scores: list[float] = field(default_factory=list)

    @property
    def vote_accuracy(self) -> float:
        total = self.votes_against_wolves + self.votes_against_good
        return self.votes_against_wolves / total if total > 0 else 0.5


@dataclass
class GameMetrics:
    winner: str
    total_rounds: int
    werewolf_metrics: list[RoleMetrics] = field(default_factory=list)
    good_metrics: list[RoleMetrics] = field(default_factory=list)

    @property
    def werewolf_win_rate(self) -> float:
        return 1.0 if self.winner == "狼人阵营" else 0.0

    @property
    def good_win_rate(self) -> float:
        return 1.0 if self.winner == "好人阵营" else 0.0

    def seer_efficiency(self) -> float:
        for m in self.good_metrics:
            if m.role == "预言家":
                return sum(m.speech_quality_scores) / len(m.speech_quality_scores) if m.speech_quality_scores else 0.5
        return 0.0

    def summary(self) -> str:
        lines = [
            f"# 对局评测",
            f"结果：{self.winner} 胜利（{self.total_rounds} 天）",
            f"",
            f"## 阵营统计",
            f"| 阵营 | 存活率 | 投票准确率 |",
            f"|------|--------|-----------|",
        ]
        for label, metrics in [("狼人", self.werewolf_metrics), ("好人", self.good_metrics)]:
            for m in metrics:
                surv = "存活" if m.survived else "出局"
                lines.append(f"| {m.player_id}号 {m.role} | {surv} | {m.vote_accuracy:.0%} |")
        return "\n".join(lines)


def evaluate_game(game_log: dict, players: list) -> GameMetrics:
    """从游戏日志中提取评测指标。"""
    events = game_log.get("events", [])
    werewolf_metrics: list[RoleMetrics] = []
    good_metrics: list[RoleMetrics] = []

    role_map: dict[int, str] = {}
    alive_map: dict[int, bool] = {}
    for p in players:
        role_map[p.player_id] = p.role_name
        alive_map[p.player_id] = p.alive

    vote_history: dict[int, list[tuple[int, bool]]] = {}

    for e in events:
        pid = e.get("actor")
        detail = e.get("detail", {})
        role = e.get("role", "")

        if e.get("action") == "vote" and pid is not None:
            target = detail.get("target")
            if target is not None and pid is not None:
                target_is_wolf = role_map.get(target, "") == "狼人"
                vote_history.setdefault(pid, []).append((target, target_is_wolf))

        if e.get("action") == "last_words" and pid is not None:
            alive_map[pid] = False

    for pid, role in role_map.items():
        votes = vote_history.get(pid, [])
        votes_vs_wolves = sum(1 for _, is_wolf in votes if is_wolf)
        votes_vs_good = sum(1 for _, is_wolf in votes if not is_wolf)

        rm = RoleMetrics(
            role=role,
            player_id=pid,
            survived=alive_map.get(pid, True),
            speeches_count=sum(1 for e in events if e.get("actor") == pid and e.get("action") == "speech"),
            votes_against_wolves=votes_vs_wolves,
            votes_against_good=votes_vs_good,
            total_votes=len(votes),
        )

        if role == "狼人":
            werewolf_metrics.append(rm)
        else:
            good_metrics.append(rm)

    return GameMetrics(
        winner=game_log.get("winner", "未知"),
        total_rounds=game_log.get("total_rounds", 0),
        werewolf_metrics=werewolf_metrics,
        good_metrics=good_metrics,
    )
