"""短期记忆：单次求解任务内的 Agent 消息总线。

生命周期：一次 solve() 调用内。进程重启后清空。

架构：两段式存储
  [compressed_prefix] ← LLM 压缩的旧消息摘要（可增量合并）
  [recent_window]     ← 最近 N 条原始消息（保留完整细节）
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
    token_count: int = 0

    def format_for_context(self) -> str:
        return f"[{self.role}] (round {self.round_idx}):\n{self.content}"

    @property
    def estimated_tokens(self) -> int:
        return self.token_count or max(len(self.content) // 2, 1)


class SharedMemory:
    """跨 Agent 短期消息总线，支持两段式压缩存储。

    压缩策略：
    - recent_window 保留最近 N 条完整消息
    - 超出的旧消息通过 compress_older() 折叠为 compressed_prefix
    - compressed_prefix 支持增量合并，不会丢失历史脉络
    """

    def __init__(self, max_tokens: int = 50000, recent_window_size: int = 5) -> None:
        self._messages: list[AgentMessage] = []
        self._compressed_prefix: AgentMessage | None = None
        self._round: int = 0
        self._max_tokens = max_tokens
        self._recent_window_size = recent_window_size
        self._total_tokens = 0

    # ─── 属性 ─────────────────────────────────────────────────────────

    @property
    def round_idx(self) -> int:
        return self._round

    @property
    def total_tokens(self) -> int:
        return self._total_tokens

    @property
    def is_full(self) -> bool:
        return self._total_tokens >= self._max_tokens

    @property
    def compressed_prefix(self) -> AgentMessage | None:
        return self._compressed_prefix

    @property
    def recent_window_size(self) -> int:
        return self._recent_window_size

    @property
    def message_count(self) -> int:
        return len(self._messages)

    # ─── 读写 ─────────────────────────────────────────────────────────

    def post(self, role: str, content: str) -> AgentMessage:
        msg = AgentMessage(
            role=role, content=content, round_idx=self._round,
            token_count=len(content) // 2
        )
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

    # ─── 压缩 ─────────────────────────────────────────────────────────

    def set_compressed_prefix(self, content: str) -> None:
        """设置或替换压缩前缀。"""
        old_tokens = self._compressed_prefix.estimated_tokens if self._compressed_prefix else 0
        self._compressed_prefix = AgentMessage(
            role="compressor", content=content, round_idx=-1,
            token_count=len(content) // 2,
        )
        self._total_tokens += self._compressed_prefix.estimated_tokens - old_tokens

    def compress_older(self, keep_recent: int | None = None) -> str | None:
        """将超出 recent_window 的旧消息标记为待压缩，返回这些消息的格式化文本。

        返回 None 表示没有需要压缩的消息。
        """
        keep = keep_recent if keep_recent is not None else self._recent_window_size
        if len(self._messages) <= keep:
            return None

        split_at = len(self._messages) - keep
        old_messages = self._messages[:split_at]

        # 从 total_tokens 中减去将被压缩的消息的 token
        removed_tokens = sum(m.estimated_tokens for m in old_messages)
        self._total_tokens -= removed_tokens

        # 保留 recent window
        self._messages = self._messages[split_at:]

        return "\n\n".join(m.format_for_context() for m in old_messages)

    # ─── 格式化 ───────────────────────────────────────────────────────

    def format_context(self, roles: list[str] | None = None, max_tokens: int = 8000) -> str:
        """格式化消息历史为注入用文本，compressed_prefix 优先，然后是最近消息。

        从最新消息开始累积直到接近 token 上限。
        """
        parts: list[str] = []

        # 压缩前缀始终在最前面（如果存在）
        if self._compressed_prefix:
            parts.append(self._compressed_prefix.format_for_context())
            budget_used = self._compressed_prefix.estimated_tokens
        else:
            budget_used = 0

        # 选取最近消息
        msgs = self._messages
        if roles:
            msgs = [m for m in msgs if m.role in roles]

        selected: list[AgentMessage] = []
        for m in reversed(msgs):
            if budget_used + m.estimated_tokens > max_tokens:
                break
            selected.insert(0, m)
            budget_used += m.estimated_tokens

        if selected:
            parts.append("\n\n".join(m.format_for_context() for m in selected))

        return "\n\n---\n\n".join(parts) if len(parts) > 1 else (parts[0] if parts else "")

    def summary(self) -> str:
        """生成短期记忆摘要。"""
        roles = set(m.role for m in self._messages)
        has_compressed = "有" if self._compressed_prefix else "无"
        return (
            f"短期记忆：{len(self._messages)} 条消息（最近{self._recent_window_size}条保留），"
            f"{self._round} 轮，{self._total_tokens} tokens，角色：{roles}，"
            f"压缩前缀：{has_compressed}"
        )

    def clear(self) -> None:
        self._messages.clear()
        self._compressed_prefix = None
        self._round = 0
        self._total_tokens = 0
