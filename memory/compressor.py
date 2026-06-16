"""上下文压缩器：当 STM 超过 token 预算时压缩旧消息。

策略：
  sliding_window — 仅保留最近 N 条，丢弃旧消息（无 LLM 成本）
  summarize      — LLM 一次性摘要所有消息
  hierarchical   — 增量合并：旧摘要 + 新消息 → 新摘要（默认，推荐）
"""

from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel


class CompressStrategy(Enum):
    sliding_window = auto()
    summarize = auto()
    hierarchical = auto()


# 首次压缩提示词：从零开始摘要
COMPRESS_PROMPT_FIRST = """请将以下 Agent 协作记录压缩为结构化摘要，保留关键信息以便后续 Agent 理解上下文。

要求：
- 每个参与 Agent 保留 1-2 条核心要点（模型选择、关键参数、数值结果、重要决策）
- 保留发现的错误及修复方案（对后续 Debugger 至关重要）
- 去掉重复内容、过渡语和已废弃的中间版本
- 总字数不超过 400 字
- 使用中文

原始记录：
{messages}

结构化摘要："""

# 增量压缩提示词：合并已有摘要与新消息
COMPRESS_PROMPT_INCREMENTAL = """请将以下「已有摘要」与「新增协作记录」合并为一份更新后的结构化摘要。

要求：
- 保留历史摘要中的所有关键决策、模型选择和数值结果
- 提取新增记录中每个 Agent 的核心要点（1-2 条）
- 如有新的错误修复记录，追加到摘要末尾
- 如果新增内容与已有摘要重复或是对旧内容的修正，用新内容替换旧内容
- 总字数不超过 500 字
- 使用中文

已有摘要：
{existing_summary}

新增记录：
{new_messages}

更新后的结构化摘要："""

# 判断是否需要压缩的决策提示词
COMPRESS_DECISION_PROMPT = """以下是 Agent 协作中新增的消息。请判断这些消息中是否包含需要长期保留的关键信息。

关键信息包括：
- 建模决策（模型选择、变量定义、约束条件）
- 数值结果（最优值、参数、误差）
- 错误修复（bug 类型、修复方案）
- 评审意见（实质性的修改建议）

新增消息：
{messages}

请只回复一个词：保留 或 可丢弃。"""


class ContextCompressor:
    """支持多种策略的上下文压缩器。

    默认使用 hierarchical 策略：
    1. 首次触发：将旧消息 LLM 摘要为 compressed_prefix
    2. 再次触发：将 compressed_prefix + 新积累的消息合并摘要
    3. 始终保留 recent_window 中的最新消息不做压缩
    """

    def __init__(
        self,
        llm: BaseChatModel,
        trigger_tokens: int = 30000,
        trigger_rounds: int = 3,
        strategy: CompressStrategy = CompressStrategy.hierarchical,
    ) -> None:
        self.llm = llm
        self.trigger_tokens = trigger_tokens
        self.trigger_rounds = trigger_rounds
        self.strategy = strategy
        self._compressed_count = 0
        self._rounds_since_compress = 0

    # ─── 触发判断 ─────────────────────────────────────────────────────

    def should_compress(self, current_tokens: int, current_round: int | None = None) -> bool:
        """判断是否需要触发压缩（token 阈值或轮次阈值）。"""
        token_trigger = current_tokens > self.trigger_tokens

        round_trigger = False
        if current_round is not None:
            self._rounds_since_compress += 1
            round_trigger = self._rounds_since_compress >= self.trigger_rounds

        return token_trigger or round_trigger

    # ─── 压缩入口 ─────────────────────────────────────────────────────

    def compress(
        self,
        messages_text: str,
        existing_summary: str | None = None,
    ) -> str:
        """根据策略压缩消息文本。

        Args:
            messages_text: 待压缩的消息文本
            existing_summary: 已有的压缩摘要（hierarchical 策略下用于增量合并）

        Returns:
            压缩后的文本
        """
        if self.strategy == CompressStrategy.sliding_window:
            return self._compress_sliding_window(messages_text)

        if self.strategy == CompressStrategy.hierarchical and existing_summary:
            result = self._compress_incremental(existing_summary, messages_text)
        else:
            result = self._compress_summarize(messages_text)

        self._compressed_count += 1
        self._rounds_since_compress = 0
        return result

    # ─── 具体策略实现 ─────────────────────────────────────────────────

    def _compress_sliding_window(self, messages_text: str) -> str:
        """滑动窗口：不做 LLM 摘要，返回空表示旧消息已被丢弃。"""
        return "[滑动窗口：旧消息已丢弃，仅保留最近消息]"

    def _compress_summarize(self, messages_text: str) -> str:
        """LLM 一次性摘要。"""
        prompt = COMPRESS_PROMPT_FIRST.format(messages=messages_text[:8000])
        content = self._invoke_llm(prompt)
        return f"[已压缩 {self._compressed_count + 1} 次] {content}"

    def _compress_incremental(self, existing_summary: str, new_messages: str) -> str:
        """增量压缩：合并已有摘要和新消息。"""
        prompt = COMPRESS_PROMPT_INCREMENTAL.format(
            existing_summary=existing_summary,
            new_messages=new_messages[:6000],
        )
        content = self._invoke_llm(prompt)
        return f"[已压缩 {self._compressed_count + 1} 次] {content}"

    # ─── 辅助 ─────────────────────────────────────────────────────────

    def _invoke_llm(self, prompt: str) -> str:
        """调用 LLM 并规范化输出。"""
        from ..base import normalize_llm_content

        result = self.llm.invoke(prompt)
        content = result.content if hasattr(result, "content") else str(result)
        return normalize_llm_content(content).strip()

    # ─── 属性 ─────────────────────────────────────────────────────────

    @property
    def compress_count(self) -> int:
        return self._compressed_count

    def reset(self) -> None:
        self._compressed_count = 0
        self._rounds_since_compress = 0
