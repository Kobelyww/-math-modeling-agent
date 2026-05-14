"""上下文压缩器：当 STM 超过 token 预算时，用 LLM 压缩旧消息为摘要。"""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel

COMPRESS_PROMPT = """请将以下 Agent 协作记录压缩为一条简洁的摘要，保留关键信息。

要求：
- 保留每个 Agent 的核心输出要点（1-2 句）
- 保留关键的数值结果和模型名称
- 去掉重复内容和过渡语
- 总字数不超过 300 字

原始记录：
{messages}

摘要："""


class ContextCompressor:
    def __init__(self, llm: BaseChatModel, trigger_tokens: int = 30000) -> None:
        self.llm = llm
        self.trigger_tokens = trigger_tokens
        self._compressed_count = 0

    def should_compress(self, current_tokens: int) -> bool:
        return current_tokens > self.trigger_tokens

    def compress(self, messages_text: str) -> str:
        """调用 LLM 压缩消息历史为摘要。"""
        prompt = COMPRESS_PROMPT.format(messages=messages_text[:8000])
        result = self.llm.invoke(prompt)
        content = result.content if hasattr(result, "content") else str(result)
        if isinstance(content, list):
            content = "".join(
                str(item.get("text", item)) if isinstance(item, dict) else str(item)
                for item in content
            )
        self._compressed_count += 1
        return f"[已压缩 {self._compressed_count} 次] {content.strip()}"

    @property
    def compress_count(self) -> int:
        return self._compressed_count

    def reset(self) -> None:
        self._compressed_count = 0
