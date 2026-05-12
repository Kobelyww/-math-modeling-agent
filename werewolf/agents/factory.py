"""Agent 工厂函数。"""

from langchain_core.language_models import BaseChatModel

from ..config import Role
from .base import WerewolfAgent
from .hunter import HunterAgent
from .idiot import IdiotAgent
from .seer import SeerAgent
from .villager import VillagerAgent
from .werewolf import WerewolfRoleAgent
from .witch import WitchAgent

_ROLE_MAP = {
    Role.WEREWOLF: WerewolfRoleAgent,
    Role.VILLAGER: VillagerAgent,
    Role.SEER: SeerAgent,
    Role.WITCH: WitchAgent,
    Role.HUNTER: HunterAgent,
    Role.IDIOT: IdiotAgent,
}


def create_agent(role: Role, llm: BaseChatModel, player_id: int) -> WerewolfAgent:
    cls = _ROLE_MAP.get(role)
    if cls is None:
        raise ValueError(f"Unknown role: {role}")
    return cls(llm, player_id=player_id)


def create_all_agents(
    role_assignments: list[tuple[int, Role]],
    llm: BaseChatModel,
    werewolf_llm: BaseChatModel | None = None,
) -> dict[int, WerewolfAgent]:
    """按角色分配创建所有 Agent。

    Args:
        role_assignments: [(player_id, Role), ...]
        llm: 默认 LLM
        werewolf_llm: 狼人专用 LLM（可选，用于测试不同模型）

    Returns:
        {player_id: WerewolfAgent}
    """
    agents: dict[int, WerewolfAgent] = {}
    for pid, role in role_assignments:
        if role == Role.WEREWOLF and werewolf_llm is not None:
            agents[pid] = create_agent(role, werewolf_llm, pid)
        else:
            agents[pid] = create_agent(role, llm, pid)
    return agents
