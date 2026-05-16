"""记忆管理器：协调短期记忆、长期记忆和上下文压缩。

整个系统的记忆中枢——Orchestrator 通过它管理所有记忆操作。
支持两种后端：SQLite（默认）和 Redis Stack（生产/持久化）。
"""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from .compressor import ContextCompressor
from .long_term import EntryType, KnowledgeEntry, LongTermMemory
from .short_term import AgentMessage, SharedMemory
from .redis_backends import RedisLongTermMemory, RedisSharedMemory


class MemoryManager:
    """协调 STM、LTM 和压缩器的记忆中枢。

    use_redis=True 时使用 Redis Stack 后端：
    - STM：Redis JSON 持久化（TTL 1小时，task_id 恢复）
    - LTM：RedisJSON + RediSearch 全文搜索
    """

    def __init__(
        self,
        llm: BaseChatModel | None = None,
        stm_max_tokens: int = 50000,
        ltm_db_path: str | None = None,
        compress_trigger: int = 30000,
        use_redis: bool = False,
    ) -> None:
        self.use_redis = use_redis

        if use_redis:
            self.stm = RedisSharedMemory(max_tokens=stm_max_tokens)
            self.ltm = RedisLongTermMemory()
        else:
            self.stm = SharedMemory(max_tokens=stm_max_tokens)
            self.ltm = LongTermMemory(db_path=ltm_db_path)

        self.compressor = ContextCompressor(llm, trigger_tokens=compress_trigger) if llm else None

    # ─── 短期记忆 ─────────────────────────────────────────────────────

    def remember(self, role: str, content: str) -> AgentMessage:
        """记录一条短期记忆，自动检测是否需要压缩。"""
        msg = self.stm.post(role, content)
        if self.compressor and self.compressor.should_compress(self.stm.total_tokens):
            compressed = self.compressor.compress(self.stm.format_context(max_tokens=8000))
            self.stm.clear()
            self.stm.post("compressor", compressed)
            self.stm.post(role, content)
        return msg

    def get_context(self, roles: list[str] | None = None, max_tokens: int = 8000) -> str:
        """获取当前短期记忆的格式化文本（供 Agent prompt 使用）。"""
        return self.stm.format_context(roles=roles, max_tokens=max_tokens)

    # ─── 长期记忆 ─────────────────────────────────────────────────────

    def learn(self, entry_type: EntryType, title: str, content: str, tags: list[str] | None = None) -> int:
        """将知识存入长期记忆。"""
        return self.ltm.add(entry_type, title, content, tags)

    def recall(self, query: str, top_k: int = 5) -> str:
        """从长期记忆搜索相关知识，返回格式化文本。"""
        return self.ltm.recall(query, top_k=top_k)

    def search(self, query: str, top_k: int = 5, entry_type: EntryType | None = None) -> list[KnowledgeEntry]:
        return self.ltm.search(query, top_k=top_k, entry_type=entry_type)

    # ─── 求解归档 ─────────────────────────────────────────────────────

    def archive_solve(self, question: str, result_summary: str, model_types: list[str] | None = None) -> None:
        """求解完成后，自动归档到长期记忆（problem + pattern + mistake）。"""
        # 归档问题
        self.learn("problem", question[:120], result_summary[:2000], tags=model_types or [])

        # 归档成功模式（建模方案）
        modeler_output = self.stm.latest_by_role("modeling")
        if modeler_output:
            self.learn(
                "pattern",
                f"建模模式 - {question[:60]}",
                modeler_output.content[:1500],
                tags=model_types or [],
            )

        # 自动从代码审查输出中提取错误记录
        debugger_output = self.stm.latest_by_role("code_debugger")
        if debugger_output and self._has_code_issues(debugger_output.content):
            self.learn(
                "mistake",
                f"代码问题 - {question[:60]}",
                debugger_output.content[:800],
                tags=(model_types or []) + ["code"],
            )

        # 检查评审反馈中是否有值得记录的问题
        for reviewer_role in ["reviewer(modeling)", "reviewer(programming)", "reviewer(writing)"]:
            review = self.stm.latest_by_role(reviewer_role)
            if review and self._has_review_issues(review.content):
                self.learn(
                    "mistake",
                    f"评审意见 - {reviewer_role} - {question[:50]}",
                    review.content[:800],
                    tags=(model_types or []) + ["review"],
                )

    @staticmethod
    def _has_code_issues(content: str) -> bool:
        """检测代码审查是否发现了实质问题。"""
        indicators = ["bug", "错误", "修复", "性能问题", "边界条件", "未处理", "溢出", "死循环"]
        return any(w in content for w in indicators)

    @staticmethod
    def _has_review_issues(content: str) -> bool:
        """检测评审意见是否指出了实质问题。"""
        indicators = ["需要修改", "问题", "不足", "建议改进", "错误", "遗漏", "不完整"]
        return any(w in content for w in indicators)

    def stats(self) -> dict:
        """记忆系统统计。"""
        return {
            "stm_messages": len(self.stm._messages),
            "stm_tokens": self.stm.total_tokens,
            "compressions": self.compressor.compress_count if self.compressor else 0,
            "ltm_total": self.ltm.stats()["total"],
            "ltm_by_type": self.ltm.stats()["by_type"],
        }