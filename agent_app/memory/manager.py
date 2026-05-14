"""记忆管理器：协调短期记忆、长期记忆和上下文压缩。

整个系统的记忆中枢——Orchestrator 通过它管理所有记忆操作。
"""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from .compressor import ContextCompressor
from .long_term import EntryType, KnowledgeEntry, LongTermMemory
from .short_term import AgentMessage, SharedMemory


class MemoryManager:
    """协调 STM、LTM 和压缩器的记忆中枢。"""

    def __init__(
        self,
        llm: BaseChatModel | None = None,
        stm_max_tokens: int = 50000,
        ltm_db_path: str | None = None,
        compress_trigger: int = 30000,
    ) -> None:
        self.stm = SharedMemory(max_tokens=stm_max_tokens)
        self.ltm = LongTermMemory(db_path=ltm_db_path)
        self.compressor = ContextCompressor(llm, trigger_tokens=compress_trigger) if llm else None

    # ========= 短期记忆操作 =========

    def remember(self, role: str, content: str) -> AgentMessage:
        """记录一条短期记忆，自动检测是否需要压缩。"""
        msg = self.stm.post(role, content)
        if self.compressor and self.compressor.should_compress(self.stm.total_tokens):
            compressed = self.compressor.compress(self.stm.format_context(max_tokens=8000))
            self.stm.clear()
            self.stm.post("compressor", compressed)
            self.stm.post(role, content)  # 重新记录当前这条
        return msg

    def get_context(self, roles: list[str] | None = None, max_tokens: int = 8000) -> str:
        """获取当前短期记忆的格式化文本（供 Agent prompt 使用）。"""
        return self.stm.format_context(roles=roles, max_tokens=max_tokens)

    # ========= 长期记忆操作 =========

    def learn(self, entry_type: EntryType, title: str, content: str, tags: list[str] | None = None) -> int:
        """将知识存入长期记忆。"""
        return self.ltm.add(entry_type, title, content, tags)

    def recall(self, query: str, top_k: int = 5) -> str:
        """从长期记忆搜索相关知识，返回格式化文本。"""
        return self.ltm.recall(query, top_k=top_k)

    def search(self, query: str, top_k: int = 5, entry_type: EntryType | None = None) -> list[KnowledgeEntry]:
        return self.ltm.search(query, top_k=top_k, entry_type=entry_type)

    # ========= 求解完成后自动归档到 LTM =========

    def archive_solve(self, question: str, result_summary: str, model_types: list[str] | None = None):
        """求解完成后，自动归档到长期记忆。"""
        self.learn("problem", question[:120], result_summary[:2000], tags=model_types or [])

        # 从 STM 中提取成功模式
        modeler_output = self.stm.latest_by_role("modeling")
        if modeler_output:
            self.learn(
                "pattern",
                f"建模模式 - {question[:60]}",
                modeler_output.content[:1500],
                tags=model_types or [],
            )

    def stats(self) -> dict:
        """记忆系统统计。"""
        return {
            "stm_messages": len(self.stm._messages),
            "stm_tokens": self.stm.total_tokens,
            "compressions": self.compressor.compress_count if self.compressor else 0,
            "ltm_total": self.ltm.stats()["total"],
            "ltm_by_type": self.ltm.stats()["by_type"],
        }
