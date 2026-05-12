from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Role(str, Enum):
    WEREWOLF = "狼人"
    VILLAGER = "村民"
    SEER = "预言家"
    WITCH = "女巫"
    HUNTER = "猎人"
    IDIOT = "白痴"


class Team(str, Enum):
    GOOD = "好人阵营"
    EVIL = "狼人阵营"


class Phase(str, Enum):
    NIGHT_WEREWOLF = "night_werewolf"
    NIGHT_SEER = "night_seer"
    NIGHT_WITCH = "night_witch"
    DAY_DEATH_ANNOUNCE = "day_death_announce"
    DAY_SHERIFF_ELECTION = "day_sheriff_election"
    DAY_SPEECH = "day_speech"
    DAY_VOTE = "day_vote"
    DAY_LAST_WORDS = "day_last_words"
    GAME_OVER = "game_over"


ROLE_TEAM = {
    Role.WEREWOLF: Team.EVIL,
    Role.VILLAGER: Team.GOOD,
    Role.SEER: Team.GOOD,
    Role.WITCH: Team.GOOD,
    Role.HUNTER: Team.GOOD,
    Role.IDIOT: Team.GOOD,
}

STANDARD_12 = [
    Role.WEREWOLF, Role.WEREWOLF, Role.WEREWOLF, Role.WEREWOLF,
    Role.VILLAGER, Role.VILLAGER, Role.VILLAGER, Role.VILLAGER,
    Role.SEER, Role.WITCH, Role.HUNTER, Role.IDIOT,
]

WEREWOLF_COUNT = 4
VILLAGER_COUNT = 4

GAME_RULES = """
## 狼人杀 12 人标准局规则

### 角色配置
- 4 狼人：每晚可以击杀一名玩家
- 4 村民：无特殊能力，通过发言和投票找出狼人
- 1 预言家：每晚可以查验一名玩家的身份（好人/狼人）
- 1 女巫：拥有一瓶解药和一瓶毒药（各只能用一次）
  - 解药：可以救活当晚被狼人击杀的玩家（第一晚通常必救）
  - 毒药：可以毒杀任意一名玩家
- 1 猎人：被投票放逐时可以开枪带走一名玩家，被毒杀则不能开枪
- 1 白痴：被投票放逐时不会立即死亡，可以翻牌免死但失去投票权

### 游戏流程
1. 黑夜阶段（夜晚）
   - 狼人睁眼，协商击杀目标
   - 预言家睁眼，查验一名玩家身份
   - 女巫睁眼，得知今晚谁被刀，决定是否使用解药/毒药
2. 白天阶段
   - 天亮了，宣布昨晚死亡情况
   - 存活玩家按顺序发言
   - 投票放逐一名玩家
   - 被放逐的玩家发表遗言

### 胜负条件
- 狼人阵营胜利：存活狼人数量 >= 存活好人数量
- 好人阵营胜利：所有狼人被放逐或击杀
"""


@dataclass
class GameConfig:
    roles: list[Role] = field(default_factory=lambda: STANDARD_12.copy())
    enable_sheriff: bool = True
    witch_self_save: bool = True
    max_rounds: int = 20
    speech_order_clockwise: bool = True

    @property
    def num_players(self) -> int:
        return len(self.roles)
