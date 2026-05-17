"""记忆管理器：协调短期记忆、长期记忆和上下文压缩。

整个系统的记忆中枢——Orchestrator 通过它管理所有记忆操作。
支持两种后端：SQLite（默认）和 Redis Stack（生产/持久化）。
"""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from .compressor import CompressStrategy, ContextCompressor
from .long_term import EntryType, KnowledgeEntry, LongTermMemory
from .short_term import AgentMessage, SharedMemory
from .redis_backends import RedisLongTermMemory, RedisSharedMemory


class MemoryManager:
    """协调 STM、LTM 和压缩器的记忆中枢。

    STM 采用两段式结构：
    - compressed_prefix：LLM 摘要的旧消息（增量合并）
    - recent_window：最近 N 条完整消息

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
        compress_rounds: int = 3,
        recent_window_size: int = 5,
        compress_strategy: CompressStrategy = CompressStrategy.hierarchical,
        use_redis: bool = False,
    ) -> None:
        self.use_redis = use_redis

        if use_redis:
            self.stm = RedisSharedMemory(max_tokens=stm_max_tokens, recent_window_size=recent_window_size)
            self.ltm = RedisLongTermMemory()
        else:
            self.stm = SharedMemory(max_tokens=stm_max_tokens, recent_window_size=recent_window_size)
            self.ltm = LongTermMemory(db_path=ltm_db_path)

        self.compressor = (
            ContextCompressor(
                llm,
                trigger_tokens=compress_trigger,
                trigger_rounds=compress_rounds,
                strategy=compress_strategy,
            )
            if llm else None
        )

    # ─── 短期记忆 ─────────────────────────────────────────────────────

    def remember(self, role: str, content: str) -> AgentMessage:
        """记录一条短期记忆，自动检测是否需要压缩。

        压缩流程（hierarchical 策略）：
        1. post 新消息到 STM
        2. 检查 token/round 阈值
        3. 从 STM 中提取超出 recent_window 的旧消息
        4. LLM 增量合并：已有 compressed_prefix + 旧消息 → 新 compressed_prefix
        5. STM 保留 compressed_prefix + recent_window
        """
        msg = self.stm.post(role, content)

        if self.compressor and self.compressor.should_compress(
            self.stm.total_tokens, current_round=self.stm.round_idx
        ):
            self._run_compression()

        return msg

    def _run_compression(self) -> None:
        """执行一次压缩周期。"""
        existing_summary = (
            self.stm.compressed_prefix.content if self.stm.compressed_prefix else None
        )

        # 提取超出 recent_window 的旧消息
        old_text = self.stm.compress_older()
        if not old_text:
            return  # 没有需要压缩的消息

        # LLM 压缩（增量或首次）
        compressed = self.compressor.compress(old_text, existing_summary=existing_summary)

        # 设置新的压缩前缀
        self.stm.set_compressed_prefix(compressed)

    def get_context(self, roles: list[str] | None = None, max_tokens: int = 8000) -> str:
        """获取当前短期记忆的格式化文本（供 Agent prompt 使用）。

        返回结构：
        - compressed_prefix（压缩摘要，如存在）
        - recent_window 中的最近消息
        """
        return self.stm.format_context(roles=roles, max_tokens=max_tokens)

    def force_compress(self) -> str | None:
        """手动触发一次压缩（无视阈值），返回压缩后的文本。"""
        if not self.compressor:
            return None
        self._run_compression()
        return self.stm.compressed_prefix.content if self.stm.compressed_prefix else None

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
        self.learn("problem", question[:120], result_summary[:2000], tags=model_types or [])

        modeler_output = self.stm.latest_by_role("modeling")
        if modeler_output:
            self.learn(
                "pattern",
                f"建模模式 - {question[:60]}",
                modeler_output.content[:1500],
                tags=model_types or [],
            )

        debugger_output = self.stm.latest_by_role("code_debugger")
        if debugger_output and self._has_code_issues(debugger_output.content):
            self.learn(
                "mistake",
                f"代码问题 - {question[:60]}",
                debugger_output.content[:800],
                tags=(model_types or []) + ["code"],
            )

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
        indicators = ["bug", "错误", "修复", "性能问题", "边界条件", "未处理", "溢出", "死循环"]
        return any(w in content for w in indicators)

    @staticmethod
    def _has_review_issues(content: str) -> bool:
        indicators = ["需要修改", "问题", "不足", "建议改进", "错误", "遗漏", "不完整"]
        return any(w in content for w in indicators)

    def stats(self) -> dict:
        """记忆系统统计。"""
        return {
            "stm_messages": self.stm.message_count,
            "stm_tokens": self.stm.total_tokens,
            "stm_has_compressed_prefix": self.stm.compressed_prefix is not None,
            "compressions": self.compressor.compress_count if self.compressor else 0,
            "ltm_total": self.ltm.stats()["total"],
            "ltm_by_type": self.ltm.stats()["by_type"],
        }
