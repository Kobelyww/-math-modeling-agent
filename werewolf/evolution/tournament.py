"""跨代锦标赛：新旧版本 Agent 同台竞技。"""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from ..agents.factory import create_all_agents
from ..config import GameConfig, STANDARD_12
from ..engine import GameEngine
from ..state import GameResult


class EvolutionTournament:
    def __init__(
        self,
        llm: BaseChatModel,
        config: GameConfig | None = None,
        games_per_generation: int = 20,
    ) -> None:
        self.llm = llm
        self.config = config or GameConfig()
        self.games_per_generation = games_per_generation

    def run_generation(
        self,
        prompt_versions: dict[str, str],
        generation_id: int,
    ) -> list[GameResult]:
        """运行一代锦标赛。每个角色使用指定版本的 prompt。"""
        from ..orchestrator import GameOrchestrator

        results: list[GameResult] = []
        for game_idx in range(self.games_per_generation):
            orch = GameOrchestrator(self.llm, config=self.config, verbose=False)

            state = orch.setup()
            for pid, agent in orch.agents.items():
                role = state.get_player(pid).role_name
                if role in prompt_versions:
                    agent.system_prompt = prompt_versions[role]

            result = orch.run_game()
            results.append(result)

        return results
