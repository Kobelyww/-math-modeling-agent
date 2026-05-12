"""狼人杀对局协调器：驱动回合流转、协调 Agent 调用、信息隔离。"""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from .agents.base import WerewolfAgent
from .agents.factory import create_all_agents
from .config import GAME_RULES, Phase, Role, Team, GameConfig, ROLE_TEAM
from .engine import GameEngine
from .logger import GameLogger
from .state import GameResult, GameState, PlayerState


class GameOrchestrator:
    def __init__(
        self,
        llm: BaseChatModel,
        config: GameConfig | None = None,
        logger: GameLogger | None = None,
        verbose: bool = True,
    ) -> None:
        self.llm = llm
        self.config = config or GameConfig()
        self.engine = GameEngine(self.config)
        self.logger = logger or GameLogger()
        self.verbose = verbose
        self.agents: dict[int, WerewolfAgent] = {}
        self.state: GameState | None = None

    def _log(self, **kwargs) -> None:
        self.logger.log(kwargs)

    def _print(self, msg: str) -> None:
        if self.verbose:
            print(msg)

    def setup(self) -> GameState:
        self.state = self.engine.init_game()
        assignments = [(p.player_id, p.role) for p in self.state.players]
        self.agents = create_all_agents(assignments, self.llm)

        for pid, agent in self.agents.items():
            agent.observe(f"[系统] 你是 {pid} 号玩家，身份是：{agent.role}")
            agent.observe(f"[系统] 你的阵营是：{agent.team}")
            agent.observe(f"[系统] 游戏规则：{GAME_RULES[:500]}")

        self._print(f"\n{'='*60}")
        self._print(f"  狼人杀 — 12 人标准局")
        self._print(f"{'='*60}")
        self._print(f"\n身份已随机分配。暗中通知各玩家...\n")
        for p in self.state.players:
            self._print(f"  {p.player_id} 号玩家 → 暗中获知身份")

        return self.state

    # ========== 夜晚阶段 ==========

    def night_werewolf_phase(self) -> int | None:
        """狼人夜晚阶段：收集提名 → 达成共识 → 返回击杀目标。"""
        s = self.state
        wolves = [p for p in s.alive_players if p.is_werewolf]
        if not wolves:
            return None

        self._print(f"\n  {'─'*40}")
        self._print(f"  第 {s.round_idx} 天 · 黑夜 — 狼人行动")
        self._print(f"  {'─'*40}")

        nominations: dict[int, list[int]] = {}
        for wolf in wolves:
            agent = self.agents[wolf.player_id]
            ctx = s.werewolf_context(wolf.player_id)
            prompt = (
                f"{ctx}\n\n"
                f"请与其他狼人协商，提名今晚的击杀目标。\n"
                f"回复格式：「我提名 X 号，理由：...」"
            )
            response = agent.decide(prompt)
            target = agent.extract_number(response)
            if target is not None and target in s.alive_ids and not s.get_player(target).is_werewolf:
                nominations.setdefault(target, []).append(wolf.player_id)
                self._print(f"  狼人 {wolf.player_id} 号提名 {target} 号")
                agent.observe(f"[狼人行动] 你提名了 {target} 号")
                self._log(round_idx=s.round_idx, phase="night_werewolf", actor_id=wolf.player_id,
                          actor_role="狼人", action_type="nominate", action_detail={"target": target}, public_visible=False)

        if not nominations:
            fallback = [p.player_id for p in s.alive_good]
            target = fallback[0] if fallback else s.alive_ids[0]
            self._print(f"  狼人未达成共识，随机击杀 {target} 号")
            return target

        best_target = max(nominations, key=lambda t: len(nominations[t]))
        self._print(f"  狼人达成共识：击杀 {best_target} 号（{len(nominations[best_target])}/{len(wolves)} 票）")
        return best_target

    def night_seer_phase(self) -> tuple[int | None, str]:
        """预言家查验阶段。"""
        s = self.state
        seers = [p for p in s.alive_players if p.role == Role.SEER]
        if not seers:
            return None, "无预言家存活"

        seer = seers[0]
        agent = self.agents[seer.player_id]
        ctx = s.seer_context(seer.player_id)
        prompt = f"{ctx}\n\n请选择今晚要查验的玩家编号。\n回复格式：「我查验 X 号」"
        response = agent.decide(prompt)
        target = agent.extract_number(response)

        if target is not None and target in s.alive_ids:
            target_player = s.get_player(target)
            result = "狼人" if target_player.is_werewolf else "好人"
            seer.seer_checks.append({"round": s.round_idx, "target": target, "result": result})
            agent.observe(f"[查验结果] {target} 号是 {result}")
            self._print(f"  预言家查验 {target} 号 → {result}")
            self._log(round_idx=s.round_idx, phase="night_seer", actor_id=seer.player_id,
                      actor_role="预言家", action_type="check", action_detail={"target": target, "result": result}, public_visible=False)
            return target, result

        self._print(f"  预言家未做出有效查验")
        return None, "查验失败"

    def night_witch_phase(self, attacked_id: int | None) -> tuple[bool, int | None]:
        """女巫阶段：通报被刀玩家 → 选择救/毒/不用。"""
        s = self.state
        witches = [p for p in s.alive_players if p.role == Role.WITCH]
        if not witches:
            return False, None

        witch = witches[0]
        agent = self.agents[witch.player_id]
        ctx = s.witch_context(witch.player_id, attacked_id)
        prompt = (
            f"{ctx}\n\n"
            f"请做出决定：\n"
            f"1. 是否使用解药？（回复：使用解药 或 不使用解药）\n"
            f"2. 是否使用毒药？毒谁？（回复：使用毒药毒 X 号 或 不使用毒药）\n"
            f"注意：同一晚不能同时使用两种药。"
        )
        response = agent.decide(prompt)

        use_save = False
        use_poison = False
        poison_target = None

        if attacked_id is not None and ("使用解药" in response or "救" in response):
            if not witch.witch_antidote_used:
                use_save = True
                witch.witch_antidote_used = True
                agent.observe(f"[女巫行动] 你使用了了解药，救了 {attacked_id} 号")
                self._print(f"  女巫使用解药救了 {attacked_id} 号")
                self._log(round_idx=s.round_idx, phase="night_witch", actor_id=witch.player_id,
                          actor_role="女巫", action_type="save", action_detail={"target": attacked_id}, public_visible=False)

        if "使用毒药" in response or "毒" in response:
            if not witch.witch_poison_used and not use_save:
                target = agent.extract_number(response)
                if target is not None and target in s.alive_ids and target != witch.player_id:
                    use_poison = True
                    poison_target = target
                    witch.witch_poison_used = True
                    agent.observe(f"[女巫行动] 你使用了毒药，毒杀了 {target} 号")
                    self._print(f"  女巫使用毒药毒杀 {target} 号")
                    self._log(round_idx=s.round_idx, phase="night_witch", actor_id=witch.player_id,
                              actor_role="女巫", action_type="poison", action_detail={"target": target}, public_visible=False)

        if not use_save and not use_poison:
            self._print(f"  女巫今晚未使用药")
            agent.observe("[女巫行动] 你今晚未使用任何药")

        return use_save, poison_target

    # ========== 白天阶段 ==========

    def day_death_announce(self, deaths: list[dict]) -> None:
        """白天死讯公告。"""
        self._print(f"\n  {'─'*40}")
        self._print(f"  第 {self.state.round_idx} 天 · 白天")
        self._print(f"  {'─'*40}")

        if not deaths:
            self._print(f"\n  天亮了，昨晚是平安夜，无人死亡。")
            for agent in self.agents.values():
                agent.observe("[白天] 昨晚是平安夜，无人死亡")
            return

        for d in deaths:
            msg = f"  {d['player_id']} 号玩家死亡（{d['cause']}）"
            self._print(msg)
            for agent in self.agents.values():
                agent.observe(f"[白天] {msg}")

        for d in deaths:
            if d.get("saved"):
                self._print(f"  （{d['player_id']} 号被女巫救活）")

    def day_sheriff_election(self) -> None:
        """警长竞选（仅首轮）。"""
        s = self.state
        if s.sheriff_id is not None:
            return

        self._print(f"\n  🗳 警长竞选")
        candidates = list(s.alive_ids)
        votes: dict[int, int] = {}
        for pid in candidates:
            agent = self.agents[pid]
            prompt = (
                f"警长竞选。存活玩家：{s.alive_ids}\n"
                f"请投票选出警长。回复：「我投 X 号当警长」"
            )
            response = agent.decide(prompt)
            target = agent.extract_number(response)
            if target is not None and target in s.alive_ids:
                votes[pid] = target
                self._print(f"  {pid} 号 → 投 {target} 号")

        tally: dict[int, int] = {}
        for v in votes.values():
            tally[v] = tally.get(v, 0) + 1
        if tally:
            sheriff = max(tally, key=tally.get)
            s.sheriff_id = sheriff
            s.get_player(sheriff).sheriff = True
            self._print(f"  → {sheriff} 号当选警长！")
            for agent in self.agents.values():
                agent.observe(f"[警长] {sheriff} 号当选警长")

    def day_speech_phase(self) -> None:
        """发言阶段：所有存活玩家按顺序发言。"""
        s = self.state
        self._print(f"\n  💬 发言阶段")

        order = list(s.alive_ids)
        for pid in order:
            player = s.get_player(pid)
            agent = self.agents[pid]
            ctx = s.public_info(pid)
            prompt = (
                f"{ctx}\n\n"
                f"你是 {pid} 号玩家。请发表你的分析和判断。\n"
                f"你目前{'是' if player.alive else '已出局'}。\n"
                f"请给出你的逻辑推理和怀疑对象。"
            )
            response = agent.decide(prompt)
            s.add_speech(pid, response)
            agent.observe(f"[发言] 你（{pid}号）说：{response[:200]}")
            self._print(f"  {pid} 号：{response[:150]}...")
            self._log(round_idx=s.round_idx, phase="day_speech", actor_id=pid,
                      actor_role=player.role_name, action_type="speech",
                      action_detail={"content": response[:300]}, public_visible=True)

    def day_vote_phase(self) -> tuple[int | None, dict[int, int]]:
        """投票放逐阶段。"""
        s = self.state
        self._print(f"\n  🗳 投票放逐阶段")

        vote_map: dict[int, int] = {}
        for pid in s.alive_ids:
            player = s.get_player(pid)
            if not player.can_vote:
                continue
            agent = self.agents[pid]
            prompt = (
                f"投票阶段。存活玩家：{s.alive_ids}\n"
                f"请投票选出你要放逐的玩家。\n"
                f"回复：「我投 X 号，理由：...」\n"
                f"如果不想投任何人，回复：「弃权」"
            )
            response = agent.decide(prompt)
            target = agent.extract_number(response)
            if target is not None and target in s.alive_ids:
                vote_map[pid] = target
                agent.observe(f"[投票] 你投了 {target} 号")
                self._print(f"  {pid} 号 → 投 {target} 号")
                self._log(round_idx=s.round_idx, phase="day_vote", actor_id=pid,
                          actor_role=player.role_name, action_type="vote",
                          action_detail={"target": target, "reason": response[:100]}, public_visible=True)
            else:
                vote_map[pid] = -1
                self._print(f"  {pid} 号 → 弃权")

        eliminated, tally = self.engine.process_vote(vote_map)

        if eliminated is not None:
            self._print(f"\n  → {eliminated} 号被放逐（{tally.get(eliminated, 0)} 票）")
            return eliminated, tally

        self._print(f"\n  → 平票，无人被放逐")
        return None, tally

    def handle_elimination(self, player_id: int | None) -> None:
        """处理放逐结果：遗言、猎人开枪、白痴翻牌。"""
        if player_id is None:
            return

        s = self.state
        player = s.get_player(player_id)

        if player.role == Role.IDIOT and not player.idiot_revealed:
            player.idiot_revealed = True
            player.can_vote = False
            self._print(f"  {player_id} 号翻牌！身份：白痴。免于放逐但失去投票权。")
            for agent in self.agents.values():
                agent.observe(f"[翻牌] {player_id} 号是白痴，免于放逐")
            return

        self.engine.apply_kill(player_id, "vote")

        agent = self.agents[player_id]
        prompt = f"你（{player_id}号）被投票放逐。请发表遗言。"
        last_words = agent.decide(prompt)
        self._print(f"  {player_id} 号遗言：{last_words[:150]}...")
        self._log(round_idx=s.round_idx, phase="day_last_words", actor_id=player_id,
                  actor_role=player.role_name, action_type="last_words",
                  action_detail={"content": last_words[:300]}, public_visible=True)
        for a in self.agents.values():
            a.observe(f"[遗言] {player_id}号（{player.role_name}）：{last_words[:150]}")

        if player.role == Role.HUNTER and player.hunter_can_shoot:
            self._print(f"  {player_id} 号是猎人！请选择开枪目标。")
            shoot_prompt = f"你是猎人。请选择开枪带走的目标。回复：「我开枪带走 X 号」"
            shoot_response = agent.decide(shoot_prompt)
            shoot_target = agent.extract_number(shoot_response)
            if shoot_target is not None and shoot_target in s.alive_ids and shoot_target != player_id:
                result = self.engine.hunter_shoot(player_id, shoot_target)
                self._print(f"  {result}")
                for a in self.agents.values():
                    a.observe(f"[猎人开枪] {result}")

    def run_game(self) -> GameResult:
        self.setup()
        s = self.state

        while s.round_idx < self.config.max_rounds:
            # 夜晚
            werewolf_target = self.night_werewolf_phase()
            self.night_seer_phase()
            witch_save, witch_poison = self.night_witch_phase(werewolf_target)

            deaths = self.engine.process_night_actions(werewolf_target, witch_save, witch_poison)

            winner = self.engine.check_win()
            if winner:
                break

            # 白天
            self.day_death_announce(deaths)

            winner = self.engine.check_win()
            if winner:
                break

            self.day_sheriff_election()
            self.day_speech_phase()

            eliminated, _ = self.day_vote_phase()
            self.handle_elimination(eliminated)

            winner = self.engine.check_win()
            if winner:
                break

            self.engine.advance_round()

        result = self.engine.get_result()
        self._print(f"\n{'='*60}")
        self._print(f"  游戏结束：{result.winner.value if result.winner else '平局'} 胜利！")
        self._print(f"  总轮数：{result.total_rounds} 天")
        self._print(f"  存活玩家：{[p.player_id for p in result.survivors]}")
        self._print(f"{'='*60}")

        self.logger.save_summary(
            winner=result.winner.value if result.winner else "平局",
            reason=result.reason,
            players=s.players,
        )
        self.logger.save()

        for p in s.players:
            self._print(f"  {p.player_id}号：{p.role_name} {'存活' if p.alive else '出局'}")

        return result
