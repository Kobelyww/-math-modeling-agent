"""短期记忆：单次求解任务内的 Agent 消息总线。

生命周期：一次 solve() 调用内。进程重启后清空。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class AgentMessage:
    role: str
    content: str
    round_idx: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    token_count: int = 0  # 估算 token 数（粗略：字符数/2）

    def format_for_context(self) -> str:
        return f"[{self.role}] (round {self.round_idx}):\n{self.content}"

    @property
    def estimated_tokens(self) -> int:
        return self.token_count or len(self.content) // 2


class SharedMemory:
    """跨 Agent 短期消息总线，支持多轮协作。"""

    def __init__(self, max_tokens: int = 50000) -> None:
        self._messages: list[AgentMessage] = []
        self._round: int = 0
        self._max_tokens = max_tokens
        self._total_tokens = 0

    @property
    def round_idx(self) -> int:
        return self._round

    @property
    def total_tokens(self) -> int:
        return self._total_tokens

    @property
    def is_full(self) -> bool:
        return self._total_tokens >= self._max_tokens

    def post(self, role: str, content: str) -> AgentMessage:
        msg = AgentMessage(role=role, content=content, round_idx=self._round, token_count=len(content) // 2)
        self._messages.append(msg)
        self._total_tokens += msg.estimated_tokens
        return msg

    def advance_round(self) -> int:
        self._round += 1
        return self._round

    def get_by_role(self, role: str) -> list[AgentMessage]:
        return [m for m in self._messages if m.role == role]

    def latest_by_role(self, role: str) -> AgentMessage | None:
        matches = self.get_by_role(role)
        return matches[-1] if matches else None

    def recent(self, n: int = 10) -> list[AgentMessage]:
        return self._messages[-n:]

    def format_context(self, roles: list[str] | None = None, max_tokens: int = 8000) -> str:
        """格式化消息历史为注入用文本，不超过 max_tokens。"""
        msgs = self._messages
        if roles:
            msgs = [m for m in msgs if m.role in roles]

        if not msgs:
            return ""

        # 从最新开始累积，直到接近 token 上限
        selected: list[AgentMessage] = []
        token_budget = 0
        for m in reversed(msgs):
            if token_budget + m.estimated_tokens > max_tokens:
                break
            selected.insert(0, m)
            token_budget += m.estimated_tokens

        return "\n\n".join(m.format_for_context() for m in selected)

    def summary(self) -> str:
        """生成短期记忆摘要。"""
        roles = set(m.role for m in self._messages)
        return (
            f"短期记忆：{len(self._messages)} 条消息，{self._round} 轮，"
            f"{self._total_tokens} tokens，角色：{roles}"
        )

    def clear(self) -> None:
        self._messages.clear()
        self._round = 0
        self._total_tokens = 0
