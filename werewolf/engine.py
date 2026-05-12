"""狼人杀游戏引擎：阶段流转、行动处理、胜负裁决。"""

from __future__ import annotations

import random

from .config import GAME_RULES, Phase, Role, Team, GameConfig, ROLE_TEAM
from .state import GameResult, GameState, NightAction, PlayerState


class GameEngine:
    def __init__(self, config: GameConfig | None = None) -> None:
        self.config = config or GameConfig()
        self.state: GameState | None = None

    def init_game(self) -> GameState:
        roles = self.config.roles.copy()
        random.shuffle(roles)
        players = [
            PlayerState(player_id=i, role=role)
            for i, role in enumerate(roles)
        ]
        self.state = GameState(players=players, phase=Phase.NIGHT_WEREWOLF, round_idx=0)
        return self.state

    def check_win(self) -> Team | None:
        s = self.state
        alive_wolves = len(s.alive_werewolves)
        alive_good = len(s.alive_good)
        if alive_wolves == 0:
            return Team.GOOD
        if alive_wolves >= alive_good:
            return Team.EVIL
        return None

    def apply_kill(self, target_id: int, cause: str = "killed") -> None:
        self.state.kill(target_id, cause)

    def process_night_actions(
        self,
        werewolf_target: int | None,
        witch_save: bool,
        witch_poison_target: int | None,
    ) -> list[dict]:
        """处理夜间行动结果，返回死亡公告列表。"""
        deaths: list[dict] = []
        saved = False

        if werewolf_target is not None:
            if witch_save:
                saved = True
            else:
                self.apply_kill(werewolf_target, "werewolf")
                deaths.append({"player_id": werewolf_target, "cause": "被杀", "round": self.state.round_idx})

        if witch_poison_target is not None:
            self.apply_kill(witch_poison_target, "poison")
            deaths.append({"player_id": witch_poison_target, "cause": "被毒杀", "round": self.state.round_idx})

        self.state.death_announcements.extend(deaths)
        if saved:
            self.state.death_announcements.append({
                "player_id": werewolf_target, "cause": "平安夜（被女巫救活）", "round": self.state.round_idx, "saved": True
            })

        return deaths

    def process_vote(self, vote_map: dict[int, int]) -> tuple[int | None, dict[int, int]]:
        """处理投票结果，返回被放逐者 ID 和得票统计。"""
        tally: dict[int, int] = {}
        for voter, target in vote_map.items():
            if target >= 0:
                tally[target] = tally.get(target, 0) + 1

        if not tally:
            return None, tally

        max_votes = max(tally.values())
        top_candidates = [pid for pid, count in tally.items() if count == max_votes]

        if len(top_candidates) == 1:
            eliminated = top_candidates[0]
        else:
            if self.state.sheriff_id is not None and self.state.sheriff_id in [v for v in vote_map]:
                eliminated = self.state.sheriff_id if self.state.sheriff_id in top_candidates else top_candidates[0]
            else:
                eliminated = None  # 平票，无人被放逐

        return eliminated, tally

    def hunter_shoot(self, hunter_id: int, target_id: int) -> str:
        """猎人开枪带走一名玩家。"""
        player = self.state.get_player(hunter_id)
        if player.role != Role.HUNTER or not player.hunter_can_shoot:
            return "猎人无法开枪"
        self.apply_kill(target_id, "hunter_shot")
        return f"猎人 {hunter_id} 号开枪带走了 {target_id} 号"

    def advance_round(self) -> None:
        self.state.round_idx += 1

    def get_result(self) -> GameResult:
        winner = self.check_win()
        self.state.winner = winner
        self.state.game_over = (winner is not None)
        return GameResult(
            winner=winner,
            total_rounds=self.state.round_idx,
            survivors=self.state.alive_players,
            eliminated=[p for p in self.state.players if not p.alive],
            reason=f"{'狼人' if winner == Team.EVIL else '好人'}阵营胜利",
        )
