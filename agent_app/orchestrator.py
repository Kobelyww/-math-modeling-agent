from __future__ import annotations

import json
import logging
import time as time_module
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .agents import (
    CodeDebuggerAgent,
    DataEngineerAgent,
    ModelerAgent,
    ProgrammerAgent,
    ReviewerAgent,
    SynthesizerAgent,
    WriterAgent,
    create_agents,
)
from .base import BaseAgent
from .conditions import (
    BaseCondition,
    CompoundCondition,
    ExternalCondition,
    MaxRoundCondition,
    QualityThresholdCondition,
    TimeoutCondition,
    TokenBudgetCondition,
)
from .config import Settings
from .llm import create_llm
from .memory import MemoryManager, SharedMemory
from .rag import Chunk, PaperRAG

logger = logging.getLogger(__name__)


# ─── 数据类 ─────────────────────────────────────────────────────────

@dataclass
class StageResult:
    role: str
    content: str
    review_feedback: str | None = None
    round_idx: int = 0


@dataclass
class WorkflowResult:
    question: str
    modeling: StageResult
    programming: StageResult
    writing: StageResult
    synthesis: str
    memory: SharedMemory = field(default_factory=SharedMemory)
    errors: list[str] = field(default_factory=list)
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    elapsed_seconds: float = 0.0

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    @property
    def total_tokens(self) -> int:
        return self.total_prompt_tokens + self.total_completion_tokens

    @property
    def estimated_cost_usd(self) -> float:
        """估算费用（DeepSeek V4 定价：prompt $0.27/1M, completion $1.10/1M tokens）。"""
        return (
            self.total_prompt_tokens / 1_000_000 * 0.27
            + self.total_completion_tokens / 1_000_000 * 1.10
        )

    def to_dict(self) -> dict:
        return {
            "modeling": self.modeling,
            "programming": self.programming,
            "writing": self.writing,
            "synthesis": self.synthesis,
            "errors": self.errors,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": round(self.estimated_cost_usd, 6),
            "elapsed_seconds": round(self.elapsed_seconds, 1),
        }

    def format_overview(self) -> str:
        lines = [
            "=" * 60,
            f"  任务：{self.question}",
            "=" * 60,
            "",
            f"【建模智能体】({self.modeling.round_idx} 轮)"
            f"{' (已评审)' if self.modeling.review_feedback else ''}",
            self.modeling.content[:300] + "..." if len(self.modeling.content) > 300 else self.modeling.content,
            "",
            f"【编程智能体】({self.programming.round_idx} 轮)"
            f"{' (已评审)' if self.programming.review_feedback else ''}",
            self.programming.content[:300] + "..." if len(self.programming.content) > 300 else self.programming.content,
            "",
            f"【写作智能体】({self.writing.round_idx} 轮)"
            f"{' (已评审)' if self.writing.review_feedback else ''}",
            self.writing.content[:300] + "..." if len(self.writing.content) > 300 else self.writing.content,
            "",
            "【总控整合方案】",
            self.synthesis,
            "",
            f"── 统计 ──",
            f"Token：{self.total_prompt_tokens:,} prompt + {self.total_completion_tokens:,} completion "
            f"= {self.total_tokens:,} total",
            f"费用估算：${self.estimated_cost_usd:.4f}",
            f"耗时：{self.elapsed_seconds:.1f}s",
        ]
        if self.errors:
            lines.append("")
            lines.append("【错误】")
            for e in self.errors:
                lines.append(f"  ⚠ {e}")
        return "\n".join(lines)

    # ─── 检查点 ─────────────────────────────────────────────────────

    def save_state(self, path: str | Path) -> None:
        """序列化 WorkflowResult 到 JSON 文件，用于中断恢复。"""
        state = {
            "question": self.question,
            "modeling": {
                "role": self.modeling.role, "content": self.modeling.content,
                "round_idx": self.modeling.round_idx,
                "review_feedback": self.modeling.review_feedback,
            },
            "programming": {
                "role": self.programming.role, "content": self.programming.content,
                "round_idx": self.programming.round_idx,
                "review_feedback": self.programming.review_feedback,
            },
            "writing": {
                "role": self.writing.role, "content": self.writing.content,
                "round_idx": self.writing.round_idx,
                "review_feedback": self.writing.review_feedback,
            },
            "synthesis": self.synthesis,
            "errors": self.errors,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "elapsed_seconds": self.elapsed_seconds,
        }
        Path(path).write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load_state(cls, path: str | Path) -> WorkflowResult:
        """从 JSON 文件恢复 WorkflowResult。"""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            question=data["question"],
            modeling=StageResult(**data["modeling"]),
            programming=StageResult(**data["programming"]),
            writing=StageResult(**data["writing"]),
            synthesis=data["synthesis"],
            errors=data.get("errors", []),
            total_prompt_tokens=data.get("total_prompt_tokens", 0),
            total_completion_tokens=data.get("total_completion_tokens", 0),
            elapsed_seconds=data.get("elapsed_seconds", 0.0),
        )


def _format_rag_context(chunks: list[Chunk]) -> str:
    if not chunks:
        return "暂无检索上下文。"
    lines = [f"[来源: {c.source} | 片段: {c.chunk_id}] {c.content}" for c in chunks]
    return "\n\n".join(lines)


# ─── 编排器 ─────────────────────────────────────────────────────────

class Orchestrator:
    """多智能体编排器，支持多种协作策略 + 终止条件 + 检查点。"""

    def __init__(self, settings: Settings, rag: PaperRAG | None = None,
                 memory_manager: MemoryManager | None = None) -> None:
        base_llm = create_llm(settings)
        reviewer_temp = settings.get_agent_config("reviewer").temperature
        reviewer_llm = create_llm(settings, temperature=reviewer_temp)

        agents = create_agents(base_llm, reviewer_llm=reviewer_llm, max_retries=settings.max_retries)
        self.memory = memory_manager
        self.data_engineer: DataEngineerAgent = agents["data_engineer"]
        self.modeler: ModelerAgent = agents["modeler"]
        self.programmer: ProgrammerAgent = agents["programmer"]
        self.code_debugger: CodeDebuggerAgent = agents["code_debugger"]
        self.writer: WriterAgent = agents["writer"]
        self.reviewer: ReviewerAgent = agents["reviewer"]
        self.synthesizer: SynthesizerAgent = agents["synthesizer"]
        self.rag = rag

        # 默认终止条件
        self._default_conditions = CompoundCondition(
            TokenBudgetCondition(max_total_tokens=200000),
            TimeoutCondition(timeout_seconds=600.0),
        )

    # ─── 记忆辅助 ─────────────────────────────────────────────────────

    def _get_stm(self, memory: SharedMemory | None = None) -> SharedMemory:
        if self.memory:
            return self.memory.stm
        return memory or SharedMemory()

    def _post(self, stm: SharedMemory, role: str, content: str,
              triggered_by: str = "", usage: dict[str, int] | None = None) -> None:
        """记录一条消息，支持因果追溯和 token 统计。"""
        pt = usage.get("prompt_tokens", 0) if usage else 0
        ct = usage.get("completion_tokens", 0) if usage else 0
        if self.memory:
            self.memory.remember(role, content)
        else:
            stm.post(role, content, triggered_by=triggered_by,
                     prompt_tokens=pt, completion_tokens=ct)

    def _safe_invoke(self, agent: BaseAgent, prompt: str, role_label: str,
                     stm: SharedMemory, errors: list[str],
                     triggered_by: str = "",
                     token_budget: TokenBudgetCondition | None = None) -> str:
        """安全调用 agent.invoke()，自动捕获 token 使用量。"""
        try:
            result = agent.invoke(prompt)
            usage = agent.last_usage
            self._post(stm, role_label, result, triggered_by=triggered_by, usage=usage)
            if token_budget:
                token_budget.add_usage(usage.get("prompt_tokens", 0),
                                       usage.get("completion_tokens", 0))
            return result
        except Exception as exc:
            err_msg = f"[{role_label}] 执行失败: {exc}"
            logger.warning(err_msg)
            errors.append(err_msg)
            fallback = f"[{role_label} 因错误未能完成: {exc}]"
            self._post(stm, role_label, fallback, triggered_by=triggered_by)
            return fallback

    def _safe_stream(self, agent: BaseAgent, prompt: str, role_label: str,
                     stm: SharedMemory, errors: list[str],
                     triggered_by: str = "",
                     token_budget: TokenBudgetCondition | None = None,
                     on_token: Callable[[str], None] | None = None) -> str:
        """安全调用 agent.stream()，自动捕获 token 使用量。"""
        try:
            result = agent.stream(prompt, on_token=on_token)
            usage = agent.last_usage
            self._post(stm, role_label, result, triggered_by=triggered_by, usage=usage)
            if token_budget:
                token_budget.add_usage(usage.get("prompt_tokens", 0),
                                       usage.get("completion_tokens", 0))
            return result
        except Exception as exc:
            err_msg = f"[{role_label}] 执行失败: {exc}"
            logger.warning(err_msg)
            errors.append(err_msg)
            fallback = f"[{role_label} 因错误未能完成: {exc}]"
            self._post(stm, role_label, fallback, triggered_by=triggered_by)
            return fallback

    def _get_stm_context(self, stm: SharedMemory, max_tokens: int = 3000) -> str:
        if self.memory:
            ctx = self.memory.get_context(max_tokens=max_tokens)
        else:
            ctx = stm.format_context(max_tokens=max_tokens)
        return ctx

    def _maybe_archive(self, question: str, result_summary: str) -> None:
        if self.memory:
            self.memory.archive_solve(question, result_summary)

    def _rag_context(self, question: str, top_k: int = 6) -> str:
        parts: list[str] = []

        if self.memory:
            ltm_context = self.memory.recall(question, top_k=3)
            if ltm_context:
                parts.append(ltm_context)

        if self.rag:
            if self.rag.has_embeddings:
                chunks = self.rag.query_hybrid(question, top_k=top_k, alpha=0.6)
            else:
                chunks = self.rag.query(question, top_k=top_k)
            if chunks:
                parts.append(_format_rag_context(chunks))

        return "\n\n---\n\n".join(parts) if parts else "暂无检索上下文。"

    # ─── 提示词构建 ───────────────────────────────────────────────────

    def _build_prompt(self, question: str, stm_ctx: str, rag_ctx: str,
                      extra_contexts: dict[str, str] | None = None) -> str:
        parts = [f"任务：{question}"]

        if stm_ctx:
            parts.append(f"协作历史（压缩）：\n{stm_ctx}")

        if rag_ctx and rag_ctx != "暂无检索上下文。":
            parts.append(f"参考资料：\n{rag_ctx}")

        if extra_contexts:
            for label, content in extra_contexts.items():
                parts.append(f"{label}：\n{content}")

        return "\n\n".join(parts)

    # ─── 终止条件辅助 ─────────────────────────────────────────────────

    def _check_conditions(self, conditions: list[BaseCondition], stm: SharedMemory,
                          current_round: int, elapsed: float) -> str | None:
        """检查终止条件，返回 StopMessage.content 或 None。"""
        msgs = stm._messages[-5:] if stm._messages else []
        for cond in conditions:
            result = cond(msgs, current_round, elapsed)
            if result is not None:
                return result.content
        return None

    @staticmethod
    def _reset_conditions(conditions: list[BaseCondition]) -> None:
        for cond in conditions:
            cond.reset()

    # ═════════════════════════════════════════════════════════════════
    # 策略一：串行流水线
    # ═════════════════════════════════════════════════════════════════

    def solve_sequential(
        self,
        question: str,
        top_k: int = 6,
        memory: SharedMemory | None = None,
        enable_data_engineer: bool = False,
    ) -> WorkflowResult:
        mem = self._get_stm(memory)
        rag_ctx = self._rag_context(question, top_k)
        errors: list[str] = []
        token_budget = TokenBudgetCondition(max_total_tokens=200000)
        started_at = time_module.monotonic()

        data_ctx, data_out = "", ""
        if enable_data_engineer:
            data_out = self._safe_invoke(
                self.data_engineer,
                f"任务：{question}\n\nRAG参考：\n{rag_ctx}",
                "data_engineer", mem, errors, token_budget=token_budget,
            )
            data_ctx = f"\n\n数据预处理结果：\n{data_out}"

        model_in = self._build_prompt(question, "", rag_ctx,
                                      {"数据预处理结果": data_out} if data_ctx else None)
        model_out = self._safe_invoke(self.modeler, model_in, "modeling", mem, errors,
                                      token_budget=token_budget)
        mem.advance_round()

        stm_ctx = self._get_stm_context(mem)
        prog_in = self._build_prompt(question, stm_ctx, rag_ctx, {"建模方案": model_out})
        prog_out = self._safe_invoke(self.programmer, prog_in, "programming", mem, errors,
                                     triggered_by="modeling", token_budget=token_budget)

        debug_out = self._safe_invoke(
            self.code_debugger,
            self._build_prompt(question, self._get_stm_context(mem), "",
                               {"编程输出": prog_out[:4000]}),
            "code_debugger", mem, errors, triggered_by="programming", token_budget=token_budget,
        )
        mem.advance_round()

        stm_ctx = self._get_stm_context(mem)
        write_in = self._build_prompt(question, stm_ctx, rag_ctx, {
            "建模方案": model_out, "编程方案": prog_out, "代码审查": debug_out,
        })
        write_out = self._safe_invoke(self.writer, write_in, "writing", mem, errors,
                                      triggered_by="code_debugger", token_budget=token_budget)
        mem.advance_round()

        stm_ctx = self._get_stm_context(mem)
        synth_in = self._build_prompt(question, stm_ctx, "", {
            "建模方案": model_out, "编程方案": prog_out, "写作方案": write_out,
        })
        synth_out = self._safe_invoke(self.synthesizer, synth_in, "synthesizer", mem, errors,
                                      triggered_by="writing", token_budget=token_budget)

        self._maybe_archive(question, synth_out)

        return WorkflowResult(
            question=question,
            modeling=StageResult("建模智能体", model_out),
            programming=StageResult("编程智能体", prog_out),
            writing=StageResult("写作智能体", write_out),
            synthesis=synth_out,
            memory=mem,
            errors=errors,
            total_prompt_tokens=token_budget.accumulated,
            total_completion_tokens=0,
            elapsed_seconds=time_module.monotonic() - started_at,
        )

    # ═════════════════════════════════════════════════════════════════
    # 策略二：带评审反思的深度协作（集成终止条件）
    # ═════════════════════════════════════════════════════════════════

    def solve_with_review(
        self,
        question: str,
        top_k: int = 6,
        max_review_rounds: int = 1,
        memory: SharedMemory | None = None,
        enable_data_engineer: bool = False,
        conditions: list[BaseCondition] | None = None,
    ) -> WorkflowResult:
        mem = self._get_stm(memory)
        rag_ctx = self._rag_context(question, top_k)
        errors: list[str] = []
        token_budget = TokenBudgetCondition(max_total_tokens=200000)
        timeout = TimeoutCondition(timeout_seconds=600.0)
        timeout.start()
        started_at = time_module.monotonic()

        # 组合默认条件 + 外部传入条件
        active_conditions: list[BaseCondition] = [
            MaxRoundCondition(max_review_rounds),
            token_budget,
            timeout,
        ]
        if conditions:
            active_conditions.extend(conditions)

        data_ctx, data_out = "", ""
        if enable_data_engineer:
            data_out = self._safe_invoke(
                self.data_engineer,
                f"任务：{question}\n\nRAG参考：\n{rag_ctx}",
                "data_engineer", mem, errors, token_budget=token_budget,
            )
            data_ctx = f"\n\n数据预处理结果：\n{data_out}"

        # --- 建模 + 评审循环（每轮检查终止条件） ---
        model_in = self._build_prompt(question, "", rag_ctx,
                                      {"数据预处理结果": data_out} if data_ctx else None)
        model_out = self._safe_invoke(self.modeler, model_in, "modeling", mem, errors,
                                      token_budget=token_budget)
        model_review = ""
        for rnd in range(max_review_rounds):
            # 检查终止条件
            stop_reason = self._check_conditions(active_conditions, mem, rnd, timeout.elapsed)
            if stop_reason:
                logger.info("建模评审循环终止: %s", stop_reason)
                break

            review = self.reviewer.review("建模智能体", model_out, question)
            self._post(mem, "reviewer(modeling)", review, triggered_by="modeling")
            if rnd > 0 and not self._review_needs_revision(review, "建模"):
                break
            refine_prompt = self._build_prompt(question, self._get_stm_context(mem), rag_ctx, {
                "你的上一版输出": model_out, "评审反馈": review,
            })
            model_out = self._safe_invoke(self.modeler, refine_prompt, "modeling", mem, errors,
                                          triggered_by="reviewer(modeling)", token_budget=token_budget)
            model_review = review
        mem.advance_round()

        # --- 编程 + 评审循环 ---
        stm_ctx = self._get_stm_context(mem)
        prog_in = self._build_prompt(question, stm_ctx, rag_ctx, {"建模方案": model_out})
        prog_out = self._safe_invoke(self.programmer, prog_in, "programming", mem, errors,
                                     triggered_by="modeling", token_budget=token_budget)
        prog_review = ""
        for rnd in range(max_review_rounds):
            stop_reason = self._check_conditions(active_conditions, mem, rnd, timeout.elapsed)
            if stop_reason:
                logger.info("编程评审循环终止: %s", stop_reason)
                break

            review = self.reviewer.review("编程智能体", prog_out, question)
            self._post(mem, "reviewer(programming)", review, triggered_by="programming")
            if rnd > 0 and not self._review_needs_revision(review, "编程"):
                break
            refine_prompt = self._build_prompt(question, self._get_stm_context(mem), rag_ctx, {
                "建模方案": model_out, "你的上一版输出": prog_out, "评审反馈": review,
            })
            prog_out = self._safe_invoke(self.programmer, refine_prompt, "programming", mem, errors,
                                         triggered_by="reviewer(programming)", token_budget=token_budget)
            prog_review = review

        debug_out = self._safe_invoke(
            self.code_debugger,
            self._build_prompt(question, self._get_stm_context(mem), "",
                               {"编程输出（已评审修改）": prog_out[:4000]}),
            "code_debugger", mem, errors, triggered_by="programming", token_budget=token_budget,
        )
        mem.advance_round()

        # --- 写作 + 评审循环 ---
        stm_ctx = self._get_stm_context(mem)
        write_in = self._build_prompt(question, stm_ctx, rag_ctx, {
            "建模方案": model_out, "编程方案": prog_out, "代码审查": debug_out,
        })
        write_out = self._safe_invoke(self.writer, write_in, "writing", mem, errors,
                                      triggered_by="code_debugger", token_budget=token_budget)
        write_review = ""
        for rnd in range(max_review_rounds):
            stop_reason = self._check_conditions(active_conditions, mem, rnd, timeout.elapsed)
            if stop_reason:
                logger.info("写作评审循环终止: %s", stop_reason)
                break

            review = self.reviewer.review("写作智能体", write_out, question)
            self._post(mem, "reviewer(writing)", review, triggered_by="writing")
            if rnd > 0 and not self._review_needs_revision(review, "写作"):
                break
            refine_prompt = self._build_prompt(question, self._get_stm_context(mem), rag_ctx, {
                "建模方案": model_out, "编程方案": prog_out,
                "你的上一版输出": write_out, "评审反馈": review,
            })
            write_out = self._safe_invoke(self.writer, refine_prompt, "writing", mem, errors,
                                          triggered_by="reviewer(writing)", token_budget=token_budget)
            write_review = review
        mem.advance_round()

        # --- 总控整合 ---
        stm_ctx = self._get_stm_context(mem)
        synth_in = self._build_prompt(question, stm_ctx, "", {
            "建模方案（已评审）": model_out,
            "编程方案（已评审）": prog_out,
            "写作方案（已评审）": write_out,
        })
        synth_out = self._safe_invoke(self.synthesizer, synth_in, "synthesizer", mem, errors,
                                      triggered_by="writing", token_budget=token_budget)

        self._maybe_archive(question, synth_out)
        self._reset_conditions(active_conditions)

        return WorkflowResult(
            question=question,
            modeling=StageResult("建模智能体", model_out, model_review, mem.round_idx),
            programming=StageResult("编程智能体", prog_out, prog_review, mem.round_idx),
            writing=StageResult("写作智能体", write_out, write_review, mem.round_idx),
            synthesis=synth_out,
            memory=mem,
            errors=errors,
            total_prompt_tokens=token_budget.accumulated,
            total_completion_tokens=0,
            elapsed_seconds=time_module.monotonic() - started_at,
        )

    # ---- 评审辅助 ----

    def _review_needs_revision(self, review_text: str, stage_name: str) -> bool:
        prompt = (
            f"以下是评审专家对 {stage_name} 输出的评审意见。\n\n"
            f"{review_text[:1500]}\n\n"
            f"请判断：这份评审意见是否认为输出存在需要修复的实质性问题？\n"
            f"只需回复一个词：需要修改 或 无需修改。"
        )
        result = self.synthesizer.invoke(prompt).strip()
        return "无需修改" not in result

    # ═════════════════════════════════════════════════════════════════
    # 策略三：快速并行
    # ═════════════════════════════════════════════════════════════════

    def solve_parallel(
        self,
        question: str,
        top_k: int = 6,
        memory: SharedMemory | None = None,
        enable_data_engineer: bool = False,
    ) -> WorkflowResult:
        mem = self._get_stm(memory)
        rag_ctx = self._rag_context(question, top_k)
        errors: list[str] = []
        token_budget = TokenBudgetCondition(max_total_tokens=200000)
        started_at = time_module.monotonic()

        data_ctx, data_out = "", ""
        if enable_data_engineer:
            data_out = self._safe_invoke(
                self.data_engineer,
                f"任务：{question}\n\nRAG参考：\n{rag_ctx}",
                "data_engineer", mem, errors, token_budget=token_budget,
            )
            data_ctx = f"\n\n数据预处理结果：\n{data_out}"

        model_in = self._build_prompt(question, "", rag_ctx,
                                      {"数据预处理结果": data_out} if data_ctx else None)
        model_out = self._safe_invoke(self.modeler, model_in, "modeling", mem, errors,
                                      token_budget=token_budget)

        stm_ctx = self._get_stm_context(mem)

        def run_programmer() -> str:
            return self.programmer.invoke(
                self._build_prompt(question, stm_ctx, rag_ctx, {"建模方案": model_out})
            )

        def run_writer() -> str:
            return self.writer.invoke(
                self._build_prompt(question, stm_ctx, rag_ctx, {"建模方案": model_out})
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            prog_future = executor.submit(run_programmer)
            write_future = executor.submit(run_writer)
            try:
                prog_out = prog_future.result()
            except Exception as exc:
                prog_out = f"[编程智能体 执行失败: {exc}]"
                errors.append(f"[programming] {exc}")
            try:
                write_out = write_future.result()
            except Exception as exc:
                write_out = f"[写作智能体 执行失败: {exc}]"
                errors.append(f"[writing] {exc}")

        self._post(mem, "programming", prog_out, triggered_by="modeling")
        self._post(mem, "writing", write_out, triggered_by="modeling")

        debug_out = self._safe_invoke(
            self.code_debugger,
            self._build_prompt(question, self._get_stm_context(mem), "",
                               {"编程输出": prog_out[:4000]}),
            "code_debugger", mem, errors, triggered_by="programming", token_budget=token_budget,
        )
        mem.advance_round()

        stm_ctx = self._get_stm_context(mem)
        synth_in = self._build_prompt(question, stm_ctx, "", {
            "建模方案": model_out, "编程方案": prog_out,
            "代码审查": debug_out, "写作方案": write_out,
        })
        synth_out = self._safe_invoke(self.synthesizer, synth_in, "synthesizer", mem, errors,
                                      triggered_by="writing", token_budget=token_budget)

        self._maybe_archive(question, synth_out)

        return WorkflowResult(
            question=question,
            modeling=StageResult("建模智能体", model_out),
            programming=StageResult("编程智能体", prog_out),
            writing=StageResult("写作智能体", write_out),
            synthesis=synth_out,
            memory=mem,
            errors=errors,
            total_prompt_tokens=token_budget.accumulated,
            total_completion_tokens=0,
            elapsed_seconds=time_module.monotonic() - started_at,
        )

    # ═════════════════════════════════════════════════════════════════
    # 策略四：流式串行
    # ═════════════════════════════════════════════════════════════════

    def solve_stream(
        self,
        question: str,
        top_k: int = 6,
        on_modeling_token: Callable[[str], None] | None = None,
        on_programming_token: Callable[[str], None] | None = None,
        on_writing_token: Callable[[str], None] | None = None,
        on_synthesis_token: Callable[[str], None] | None = None,
        enable_data_engineer: bool = False,
    ) -> WorkflowResult:
        mem = self._get_stm()
        rag_ctx = self._rag_context(question, top_k)
        errors: list[str] = []
        token_budget = TokenBudgetCondition(max_total_tokens=200000)
        started_at = time_module.monotonic()

        data_ctx, data_out = "", ""
        if enable_data_engineer:
            data_out = self._safe_invoke(
                self.data_engineer,
                f"任务：{question}\n\nRAG参考：\n{rag_ctx}",
                "data_engineer", mem, errors, token_budget=token_budget,
            )
            data_ctx = f"\n\n数据预处理结果：\n{data_out}"

        model_in = self._build_prompt(question, "", rag_ctx,
                                      {"数据预处理结果": data_out} if data_ctx else None)
        model_out = self._safe_stream(self.modeler, model_in, "modeling", mem, errors,
                                      token_budget=token_budget, on_token=on_modeling_token)

        stm_ctx = self._get_stm_context(mem)
        prog_in = self._build_prompt(question, stm_ctx, rag_ctx, {"建模方案": model_out})
        prog_out = self._safe_stream(self.programmer, prog_in, "programming", mem, errors,
                                     triggered_by="modeling", token_budget=token_budget,
                                     on_token=on_programming_token)

        stm_ctx = self._get_stm_context(mem)
        write_in = self._build_prompt(question, stm_ctx, rag_ctx, {
            "建模方案": model_out, "编程方案": prog_out,
        })
        write_out = self._safe_stream(self.writer, write_in, "writing", mem, errors,
                                      triggered_by="programming", token_budget=token_budget,
                                      on_token=on_writing_token)

        stm_ctx = self._get_stm_context(mem)
        synth_in = self._build_prompt(question, stm_ctx, "", {
            "建模方案": model_out, "编程方案": prog_out, "写作方案": write_out,
        })
        synth_out = self._safe_stream(self.synthesizer, synth_in, "synthesizer", mem, errors,
                                      triggered_by="writing", token_budget=token_budget,
                                      on_token=on_synthesis_token)

        self._maybe_archive(question, synth_out)

        return WorkflowResult(
            question=question,
            modeling=StageResult("建模智能体", model_out),
            programming=StageResult("编程智能体", prog_out),
            writing=StageResult("写作智能体", write_out),
            synthesis=synth_out,
            memory=mem,
            errors=errors,
            total_prompt_tokens=token_budget.accumulated,
            total_completion_tokens=0,
            elapsed_seconds=time_module.monotonic() - started_at,
        )
