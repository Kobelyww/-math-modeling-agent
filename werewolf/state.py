from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .config import Phase, Role, Team, ROLE_TEAM


@dataclass
class PlayerState:
    player_id: int
    role: Role
    alive: bool = True
    sheriff: bool = False
    can_vote: bool = True
    witch_antidote_used: bool = False
    witch_poison_used: bool = False
    hunter_can_shoot: bool = True
    idiot_revealed: bool = False
    seer_checks: list[dict] = field(default_factory=list)

    @property
    def team(self) -> Team:
        return ROLE_TEAM[self.role]

    @property
    def role_name(self) -> str:
        return self.role.value

    @property
    def is_werewolf(self) -> bool:
        return self.role == Role.WEREWOLF

    @property
    def is_good(self) -> bool:
        return self.team == Team.GOOD


@dataclass
class NightAction:
    action_type: str
    actor_id: int
    target_id: int | None = None
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class Speech:
    player_id: int
    content: str
    round_idx: int
    phase: str = "day_speech"


@dataclass
class Vote:
    voter_id: int
    target_id: int
    reason: str = ""
    round_idx: int = 0


@dataclass
class GameResult:
    winner: Team | None
    total_rounds: int
    survivors: list[PlayerState]
    eliminated: list[PlayerState]
    reason: str = ""


@dataclass
class GameState:
    players: list[PlayerState]
    phase: Phase = Phase.NIGHT_WEREWOLF
    round_idx: int = 0
    sheriff_id: int | None = None
    night_actions: list[NightAction] = field(default_factory=list)
    speeches: list[Speech] = field(default_factory=list)
    votes: list[Vote] = field(default_factory=list)
    death_announcements: list[dict] = field(default_factory=list)
    game_over: bool = False
    winner: Team | None = None

    @property
    def alive_players(self) -> list[PlayerState]:
        return [p for p in self.players if p.alive]

    @property
    def alive_werewolves(self) -> list[PlayerState]:
        return [p for p in self.alive_players if p.is_werewolf]

    @property
    def alive_good(self) -> list[PlayerState]:
        return [p for p in self.alive_players if p.is_good]

    @property
    def alive_ids(self) -> list[int]:
        return [p.player_id for p in self.alive_players]

    def get_player(self, player_id: int) -> PlayerState:
        for p in self.players:
            if p.player_id == player_id:
                return p
        raise ValueError(f"Player {player_id} not found")

    def kill(self, player_id: int, cause: str = "killed") -> None:
        p = self.get_player(player_id)
        p.alive = False
        if p.role == Role.HUNTER:
            p.hunter_can_shoot = (cause != "poison")

    def current_actions(self) -> list[NightAction]:
        return [a for a in self.night_actions if True]

    def add_speech(self, player_id: int, content: str) -> None:
        self.speeches.append(Speech(
            player_id=player_id, content=content, round_idx=self.round_idx
        ))

    def add_vote(self, voter_id: int, target_id: int, reason: str = "") -> None:
        self.votes.append(Vote(
            voter_id=voter_id, target_id=target_id, reason=reason, round_idx=self.round_idx
        ))

    def public_info(self, player_id: int) -> str:
        """生成指定玩家有权看到的公开信息摘要。"""
        player = self.get_player(player_id)
        lines = [
            f"当前轮次：第 {self.round_idx} 天",
            f"存活玩家（{len(self.alive_players)}人）：{[p.player_id for p in self.alive_players]}",
        ]
        if self.sheriff_id is not None:
            lines.append(f"警长：{self.sheriff_id} 号")
        if self.death_announcements:
            lines.append("死亡公告：")
            for d in self.death_announcements:
                lines.append(f"  - 第 {d['round']} 天：{d['player_id']} 号死亡")
        if self.speeches:
            recent = [s for s in self.speeches if s.round_idx >= self.round_idx - 1]
            if recent:
                lines.append(f"近两轮发言（共 {len(recent)} 条）：")
                for s in recent[-20:]:
                    role_hint = f"[{player.role_name}]" if s.player_id == player_id else ""
                    lines.append(f"  {s.player_id}号{role_hint}：{s.content[:200]}")
        if self.votes:
            recent_votes = [v for v in self.votes if v.round_idx == self.round_idx]
            if recent_votes:
                lines.append(f"本轮投票：")
                for v in recent_votes:
                    lines.append(f"  {v.voter_id}号 → {v.target_id}号")
        return "\n".join(lines)

    def werewolf_context(self, werewolf_id: int) -> str:
        """狼人夜晚可见信息。"""
        player = self.get_player(werewolf_id)
        if not player.is_werewolf:
            return ""
        mates = [p.player_id for p in self.alive_players if p.is_werewolf and p.player_id != werewolf_id]
        return (
            f"你的狼同伴：{mates}\n"
            f"存活玩家：{self.alive_ids}\n"
            f"请与同伴协商击杀目标。"
        )

    def seer_context(self, seer_id: int) -> str:
        """预言家可见信息（查验历史）。"""
        player = self.get_player(seer_id)
        checks = player.seer_checks
        if not checks:
            return "你尚未进行过查验。\n存活玩家：" + str(self.alive_ids)
        history = "\n".join(
            f"  第{c['round']}天：{c['target']}号 → {c['result']}"
            for c in checks
        )
        return f"查验历史：\n{history}\n存活玩家：{self.alive_ids}"

    def witch_context(self, witch_id: int, attacked_id: int | None) -> str:
        """女巫可见信息。"""
        player = self.get_player(witch_id)
        lines = []
        if attacked_id is not None:
            lines.append(f"今晚 {attacked_id} 号被狼人击杀。")
        else:
            lines.append("今晚无人被刀（可能是平安夜）。")
        lines.append(f"解药：{'已使用' if player.witch_antidote_used else '可用'}")
        lines.append(f"毒药：{'已使用' if player.witch_poison_used else '可用'}")
        return "\n".join(lines)
