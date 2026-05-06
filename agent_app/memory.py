from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class AgentMessage:
    role: str
    content: str
    round_idx: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def format_for_context(self) -> str:
        return f"[{self.role}] (round {self.round_idx}):\n{self.content}"


class SharedMemory:
    """跨 Agent 共享的消息总线，支持多轮协作"""

    def __init__(self) -> None:
        self._messages: list[AgentMessage] = []
        self._round: int = 0

    @property
    def round_idx(self) -> int:
        return self._round

    def post(self, role: str, content: str) -> AgentMessage:
        msg = AgentMessage(role=role, content=content, round_idx=self._round)
        self._messages.append(msg)
        return msg

    def advance_round(self) -> int:
        self._round += 1
        return self._round

    def get_by_role(self, role: str) -> list[AgentMessage]:
        return [m for m in self._messages if m.role == role]

    def latest_by_role(self, role: str) -> AgentMessage | None:
        matches = self.get_by_role(role)
        return matches[-1] if matches else None

    def format_context(self, roles: list[str] | None = None) -> str:
        if roles is None:
            msgs = self._messages
        else:
            msgs = [m for m in self._messages if m.role in roles]
        return "\n\n".join(m.format_for_context() for m in msgs) if msgs else ""

    def clear(self) -> None:
        self._messages.clear()
        self._round = 0