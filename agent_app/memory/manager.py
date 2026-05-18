"""记忆管理器：协调短期记忆、长期记忆和上下文压缩。

整个系统的记忆中枢——Orchestrator 通过它管理所有记忆操作。
支持两种后端：SQLite（默认）和 Redis Stack（生产/持久化）。

LLM 驱动的记忆分析（受 CrewAI 启发）：
  - 归档时自动提取 scope、importance、model_types
  - 无需用户手动标记标签
"""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from .compressor import CompressStrategy, ContextCompressor
from .long_term import EntryType, KnowledgeEntry, LongTermMemory
from .short_term import AgentMessage, SharedMemory
from .redis_backends import RedisLongTermMemory, RedisSharedMemory

# 归档分析提示词（LLM 自动提取 scope + importance + model_types）
ARCHIVE_ANALYSIS_PROMPT = """分析以下数学建模求解结果，提取元数据。

要求：
1. scope: 最匹配的知识领域路径（如 /optimization/linear-programming, /differential-equations/ode, /statistics/regression）
2. importance: 这个解法的可复用价值 (0.0-1.0)，创新的建模方法 > 0.7，常规应用 0.3-0.5
3. model_types: 使用的模型/方法名称列表（如 ["线性规划", "NSGA-II", "蒙特卡洛"]）

任务: {question}

建模方案摘要: {summary}

请严格按 JSON 格式输出（不要其他文字）：
{{"scope": "/领域/子领域", "importance": 0.X, "model_types": ["方法1", "方法2"]}}"""


class MemoryManager:
    """协调 STM、LTM 和压缩器的记忆中枢。

    use_redis=True 时使用 Redis Stack 后端。
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
        self._llm = llm  # 保留 LLM 引用用于归档分析

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
        msg = self.stm.post(role, content)

        if self.compressor and self.compressor.should_compress(
            self.stm.total_tokens, current_round=self.stm.round_idx
        ):
            self._run_compression()

        return msg

    def _run_compression(self) -> None:
        existing_summary = (
            self.stm.compressed_prefix.content if self.stm.compressed_prefix else None
        )
        old_text = self.stm.compress_older()
        if not old_text:
            return
        compressed = self.compressor.compress(old_text, existing_summary=existing_summary)
        self.stm.set_compressed_prefix(compressed)

    def get_context(self, roles: list[str] | None = None, max_tokens: int = 8000,
                    compressed_only: bool = False) -> str:
        """compressed_only=True 时只返回压缩前缀，避免与显式阶段输出重复。"""
        return self.stm.format_context(roles=roles, max_tokens=max_tokens,
                                       compressed_only=compressed_only)

    def force_compress(self) -> str | None:
        if not self.compressor:
            return None
        self._run_compression()
        return self.stm.compressed_prefix.content if self.stm.compressed_prefix else None

    # ─── 长期记忆 ─────────────────────────────────────────────────────

    def learn(self, entry_type: EntryType, title: str, content: str, tags: list[str] | None = None,
              importance: float = 0.5, scope: str = "/") -> int:
        """将知识存入长期记忆（支持 importance 和 scope）。"""
        return self.ltm.add(entry_type, title, content, tags, importance=importance, scope=scope)

    def recall(self, query: str, top_k: int = 5) -> str:
        """从长期记忆搜索相关知识（复合重排序）。"""
        return self.ltm.recall(query, top_k=top_k)

    def search(self, query: str, top_k: int = 5, entry_type: EntryType | None = None) -> list[KnowledgeEntry]:
        return self.ltm.search(query, top_k=top_k, entry_type=entry_type)

    def adaptive_recall(self, query: str, top_k: int = 5) -> str:
        """自适应召回（受 CrewAI RecallFlow 启发）。

        1. FTS5 粗筛（oversample * 2）
        2. 复合评分重排序
        3. 如果最高分 < 阈值，降低阈值再搜一次
        """
        entries = self.ltm.search(query, top_k=top_k, oversample=True)

        if not entries:
            return ""

        # 置信度检查：最高分是否足够
        best_score = max(e.relevance_score for e in entries) if entries else 0
        if best_score < 0.3 and top_k < 8:
            # 扩大搜索，降低阈值
            entries = self.ltm.search(query, top_k=min(top_k + 3, 10), oversample=True)

        if not entries:
            return ""

        lines = ["## 长期记忆（历史相关知识）"]
        for e in entries:
            type_label = {"problem": "历史题目", "pattern": "成功模式", "mistake": "踩坑记录"}.get(e.type, e.type)
            scope_hint = f" [{e.scope}]" if e.scope and e.scope != "/" else ""
            conf = f" (置信度:{e.relevance_score:.2f})" if e.relevance_score else ""
            lines.append(f"\n### [{type_label}]{scope_hint} {e.title}{conf}")
            lines.append(e.content[:500])
        return "\n".join(lines)

    def search_by_scope(self, scope: str, top_k: int = 10) -> list[KnowledgeEntry]:
        """按层级 scope 路径搜索相关记忆。"""
        return self.ltm.search_by_scope(scope, top_k=top_k)

    # ─── LLM 驱动的归档分析 ──────────────────────────────────────────

    def _analyze_for_archive(self, question: str, result_summary: str) -> dict:
        """使用 LLM 分析求解结果，提取 scope + importance + model_types。

        受 CrewAI 启发：在保存记忆前用 LLM 自动提取元数据。
        """
        if not self._llm:
            return {"scope": "/", "importance": 0.5, "model_types": []}

        try:
            prompt = ARCHIVE_ANALYSIS_PROMPT.format(
                question=question[:500], summary=result_summary[:2000],
            )
            result = self._llm.invoke(prompt)
            content = result.content if hasattr(result, "content") else str(result)

            import re
            json_match = re.search(r'\{[^}]+\}', content)
            if json_match:
                import json as _json
                data = _json.loads(json_match.group())
                return {
                    "scope": data.get("scope", "/"),
                    "importance": float(data.get("importance", 0.5)),
                    "model_types": data.get("model_types", []),
                }
        except Exception:
            pass

        return {"scope": "/", "importance": 0.5, "model_types": []}

    # ─── 求解归档（升级版）────────────────────────────────────────────

    def archive_solve(self, question: str, result_summary: str, model_types: list[str] | None = None) -> None:
        """求解完成后，LLM 分析 + 自动归档到长期记忆。"""
        # LLM 分析提取元数据
        analysis = self._analyze_for_archive(question, result_summary)
        scope = analysis.get("scope", "/")
        importance = analysis.get("importance", 0.5)
        inferred_models = analysis.get("model_types", [])
        all_tags = list(set((model_types or []) + inferred_models))

        # 归档问题
        self.ltm.add("problem", question[:120], result_summary[:2000],
                     tags=all_tags, importance=importance, scope=scope)

        # 归档建模模式
        modeler_output = self.stm.latest_by_role("modeling")
        if modeler_output:
            self.ltm.add(
                "pattern",
                f"建模模式 - {question[:60]}",
                modeler_output.content[:1500],
                tags=all_tags,
                importance=max(importance, 0.6),
                scope=scope,
            )

        # 归档代码问题
        debugger_output = self.stm.latest_by_role("code_debugger")
        if debugger_output and self._has_code_issues(debugger_output.content):
            self.ltm.add(
                "mistake",
                f"代码问题 - {question[:60]}",
                debugger_output.content[:800],
                tags=all_tags + ["code"],
                importance=0.7,
                scope=scope,
            )

        # 归档评审意见中的问题
        for reviewer_role in ["reviewer(modeling)", "reviewer(programming)", "reviewer(writing)"]:
            review = self.stm.latest_by_role(reviewer_role)
            if review and self._has_review_issues(review.content):
                self.ltm.add(
                    "mistake",
                    f"评审意见 - {reviewer_role} - {question[:50]}",
                    review.content[:800],
                    tags=all_tags + ["review"],
                    importance=0.5,
                    scope=scope,
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
        ltm_stats = self.ltm.stats()
        return {
            "stm_messages": self.stm.message_count,
            "stm_tokens": self.stm.total_tokens,
            "stm_has_compressed_prefix": self.stm.compressed_prefix is not None,
            "compressions": self.compressor.compress_count if self.compressor else 0,
            "ltm_total": ltm_stats["total"],
            "ltm_by_type": ltm_stats.get("by_type", {}),
            "ltm_by_scope": ltm_stats.get("by_scope", {}),
        }
