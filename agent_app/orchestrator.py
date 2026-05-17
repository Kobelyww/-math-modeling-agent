from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
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
from .config import Settings
from .llm import create_llm
from .memory import MemoryManager, SharedMemory
from .rag import Chunk, PaperRAG


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

    def to_dict(self) -> dict:
        return {
            "modeling": self.modeling,
            "programming": self.programming,
            "writing": self.writing,
            "synthesis": self.synthesis,
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
        ]
        return "\n".join(lines)


def _format_rag_context(chunks: list[Chunk]) -> str:
    if not chunks:
        return "暂无检索上下文。"
    lines = [f"[来源: {c.source} | 片段: {c.chunk_id}] {c.content}" for c in chunks]
    return "\n\n".join(lines)


class Orchestrator:
    """多智能体编排器，支持多种协作策略"""

    def __init__(self, settings: Settings, rag: PaperRAG | None = None, memory_manager: MemoryManager | None = None) -> None:
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

    # ─── 记忆辅助 ─────────────────────────────────────────────────────

    def _get_stm(self, memory: SharedMemory | None = None) -> SharedMemory:
        """解析使用哪个 STM 实例。MemoryManager 存在时优先使用其 STM。"""
        if self.memory:
            return self.memory.stm
        return memory or SharedMemory()

    def _post(self, stm: SharedMemory, role: str, content: str) -> None:
        """记录一条消息。MemoryManager 存在时走 remember() 获得自动压缩。"""
        if self.memory:
            self.memory.remember(role, content)
        else:
            stm.post(role, content)

    def _get_stm_context(self, stm: SharedMemory, max_tokens: int = 3000) -> str:
        """获取 STM 上下文（含压缩前缀），用于注入 Agent prompt。

        当 MemoryManager 存在时走其 get_context()，否则直接调用 stm.format_context()。
        """
        if self.memory:
            ctx = self.memory.get_context(max_tokens=max_tokens)
        else:
            ctx = stm.format_context(max_tokens=max_tokens)
        return ctx

    def _maybe_archive(self, question: str, result_summary: str) -> None:
        """求解完成后归档到长期记忆。"""
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
        """统一构建带压缩上下文的 Agent prompt。

        Args:
            question: 用户问题
            stm_ctx: STM 上下文（含压缩摘要）
            rag_ctx: RAG + LTM 检索上下文
            extra_contexts: 额外的阶段特定上下文，如 {"建模方案": model_out, "编程方案": prog_out}
        """
        parts = [f"任务：{question}"]

        if stm_ctx:
            parts.append(f"协作历史（压缩）：\n{stm_ctx}")

        if rag_ctx and rag_ctx != "暂无检索上下文。":
            parts.append(f"参考资料：\n{rag_ctx}")

        if extra_contexts:
            for label, content in extra_contexts.items():
                parts.append(f"{label}：\n{content}")

        return "\n\n".join(parts)

    # ---- 策略一：串行流水线 ----

    def solve_sequential(
        self,
        question: str,
        top_k: int = 6,
        memory: SharedMemory | None = None,
        enable_data_engineer: bool = False,
    ) -> WorkflowResult:
        mem = self._get_stm(memory)
        rag_ctx = self._rag_context(question, top_k)

        data_ctx = ""
        if enable_data_engineer:
            data_out = self.data_engineer.invoke(
                f"任务：{question}\n\nRAG参考：\n{rag_ctx}"
            )
            self._post(mem, "data_engineer", data_out)
            data_ctx = f"\n\n数据预处理结果：\n{data_out}"

        # 建模 — 首阶段无 STM 历史
        model_in = self._build_prompt(question, "", rag_ctx,
                                      {"数据预处理结果": data_out} if data_ctx else None)
        model_out = self.modeler.invoke(model_in)
        self._post(mem, "modeling", model_out)
        mem.advance_round()

        # 编程 — 注入 STM 上下文 + 完整建模方案
        stm_ctx = self._get_stm_context(mem)
        prog_in = self._build_prompt(question, stm_ctx, rag_ctx,
                                     {"建模方案": model_out})
        prog_out = self.programmer.invoke(prog_in)
        self._post(mem, "programming", prog_out)

        # 代码审查
        debug_out = self.code_debugger.invoke(
            self._build_prompt(question, self._get_stm_context(mem), "",
                               {"编程输出": prog_out[:4000]})
        )
        self._post(mem, "code_debugger", debug_out)
        mem.advance_round()

        # 写作 — 注入 STM 上下文 + 建模 + 编程 + 代码审查
        stm_ctx = self._get_stm_context(mem)
        write_in = self._build_prompt(question, stm_ctx, rag_ctx, {
            "建模方案": model_out,
            "编程方案": prog_out,
            "代码审查": debug_out,
        })
        write_out = self.writer.invoke(write_in)
        self._post(mem, "writing", write_out)
        mem.advance_round()

        # 总控整合 — 注入 STM 上下文 + 关键阶段输出
        stm_ctx = self._get_stm_context(mem)
        synth_in = self._build_prompt(question, stm_ctx, "", {
            "建模方案": model_out,
            "编程方案": prog_out,
            "写作方案": write_out,
        })
        synth_out = self.synthesizer.invoke(synth_in)
        self._post(mem, "synthesizer", synth_out)

        self._maybe_archive(question, synth_out)

        return WorkflowResult(
            question=question,
            modeling=StageResult("建模智能体", model_out),
            programming=StageResult("编程智能体", prog_out),
            writing=StageResult("写作智能体", write_out),
            synthesis=synth_out,
            memory=mem,
        )

    # ---- 评审辅助 ----

    def _review_needs_revision(self, review_text: str, stage_name: str) -> bool:
        """用 LLM 判断评审意见是否表明需要修改（替代关键词匹配）。"""
        prompt = (
            f"以下是评审专家对 {stage_name} 输出的评审意见。\n\n"
            f"{review_text[:1500]}\n\n"
            f"请判断：这份评审意见是否认为输出存在需要修复的实质性问题？\n"
            f"只需回复一个词：需要修改 或 无需修改。"
        )
        result = self.synthesizer.invoke(prompt).strip()
        return "无需修改" not in result

    # ---- 策略二：带评审反思的深度协作 ----

    def solve_with_review(
        self,
        question: str,
        top_k: int = 6,
        max_review_rounds: int = 1,
        memory: SharedMemory | None = None,
        enable_data_engineer: bool = False,
    ) -> WorkflowResult:
        mem = self._get_stm(memory)
        rag_ctx = self._rag_context(question, top_k)

        data_ctx = ""
        if enable_data_engineer:
            data_out = self.data_engineer.invoke(
                f"任务：{question}\n\nRAG参考：\n{rag_ctx}"
            )
            self._post(mem, "data_engineer", data_out)
            data_ctx = f"\n\n数据预处理结果：\n{data_out}"

        # --- 建模 + 评审循环 ---
        model_in = self._build_prompt(question, "", rag_ctx,
                                      {"数据预处理结果": data_out} if data_ctx else None)
        model_out = self.modeler.invoke(model_in)
        model_review = ""
        for rnd in range(max_review_rounds):
            review = self.reviewer.review("建模智能体", model_out, question)
            self._post(mem, "reviewer(modeling)", review)
            if rnd > 0 and not self._review_needs_revision(review, "建模"):
                break
            stm_ctx = self._get_stm_context(mem)
            refine_prompt = self._build_prompt(question, stm_ctx, rag_ctx, {
                "你的上一版输出": model_out,
                "评审反馈": review,
            })
            model_out = self.modeler.invoke(refine_prompt)
            model_review = review
        self._post(mem, "modeling", model_out)
        mem.advance_round()

        # --- 编程 + 评审循环 ---
        stm_ctx = self._get_stm_context(mem)
        prog_in = self._build_prompt(question, stm_ctx, rag_ctx, {"建模方案": model_out})
        prog_out = self.programmer.invoke(prog_in)
        prog_review = ""
        for rnd in range(max_review_rounds):
            review = self.reviewer.review("编程智能体", prog_out, question)
            self._post(mem, "reviewer(programming)", review)
            if rnd > 0 and not self._review_needs_revision(review, "编程"):
                break
            stm_ctx = self._get_stm_context(mem)
            refine_prompt = self._build_prompt(question, stm_ctx, rag_ctx, {
                "建模方案": model_out,
                "你的上一版输出": prog_out,
                "评审反馈": review,
            })
            prog_out = self.programmer.invoke(refine_prompt)
            prog_review = review
        self._post(mem, "programming", prog_out)

        # 代码审查
        debug_out = self.code_debugger.invoke(
            self._build_prompt(question, self._get_stm_context(mem), "",
                               {"编程输出（已评审修改）": prog_out[:4000]})
        )
        self._post(mem, "code_debugger", debug_out)
        mem.advance_round()

        # --- 写作 + 评审循环 ---
        stm_ctx = self._get_stm_context(mem)
        write_in = self._build_prompt(question, stm_ctx, rag_ctx, {
            "建模方案": model_out,
            "编程方案": prog_out,
            "代码审查": debug_out,
        })
        write_out = self.writer.invoke(write_in)
        write_review = ""
        for rnd in range(max_review_rounds):
            review = self.reviewer.review("写作智能体", write_out, question)
            self._post(mem, "reviewer(writing)", review)
            if rnd > 0 and not self._review_needs_revision(review, "写作"):
                break
            stm_ctx = self._get_stm_context(mem)
            refine_prompt = self._build_prompt(question, stm_ctx, rag_ctx, {
                "建模方案": model_out,
                "编程方案": prog_out,
                "你的上一版输出": write_out,
                "评审反馈": review,
            })
            write_out = self.writer.invoke(refine_prompt)
            write_review = review
        self._post(mem, "writing", write_out)
        mem.advance_round()

        # --- 总控整合 ---
        stm_ctx = self._get_stm_context(mem)
        synth_in = self._build_prompt(question, stm_ctx, "", {
            "建模方案（已评审）": model_out,
            "编程方案（已评审）": prog_out,
            "写作方案（已评审）": write_out,
        })
        synth_out = self.synthesizer.invoke(synth_in)
        self._post(mem, "synthesizer", synth_out)

        self._maybe_archive(question, synth_out)

        return WorkflowResult(
            question=question,
            modeling=StageResult("建模智能体", model_out, model_review, mem.round_idx),
            programming=StageResult("编程智能体", prog_out, prog_review, mem.round_idx),
            writing=StageResult("写作智能体", write_out, write_review, mem.round_idx),
            synthesis=synth_out,
            memory=mem,
        )

    # ---- 策略三：快速并行（建模先行，编程+写作并行） ----

    def solve_parallel(
        self,
        question: str,
        top_k: int = 6,
        memory: SharedMemory | None = None,
        enable_data_engineer: bool = False,
    ) -> WorkflowResult:
        mem = self._get_stm(memory)
        rag_ctx = self._rag_context(question, top_k)

        data_ctx = ""
        if enable_data_engineer:
            data_out = self.data_engineer.invoke(
                f"任务：{question}\n\nRAG参考：\n{rag_ctx}"
            )
            self._post(mem, "data_engineer", data_out)
            data_ctx = f"\n\n数据预处理结果：\n{data_out}"

        # 建模先行
        model_in = self._build_prompt(question, "", rag_ctx,
                                      {"数据预处理结果": data_out} if data_ctx else None)
        model_out = self.modeler.invoke(model_in)
        self._post(mem, "modeling", model_out)

        stm_ctx = self._get_stm_context(mem)

        # 编程和写作并行
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
            prog_out = prog_future.result()
            write_out = write_future.result()

        self._post(mem, "programming", prog_out)
        self._post(mem, "writing", write_out)

        # 代码审查
        debug_out = self.code_debugger.invoke(
            self._build_prompt(question, self._get_stm_context(mem), "",
                               {"编程输出": prog_out[:4000]})
        )
        self._post(mem, "code_debugger", debug_out)
        mem.advance_round()

        # 总控整合
        stm_ctx = self._get_stm_context(mem)
        synth_in = self._build_prompt(question, stm_ctx, "", {
            "建模方案": model_out,
            "编程方案": prog_out,
            "代码审查": debug_out,
            "写作方案": write_out,
        })
        synth_out = self.synthesizer.invoke(synth_in)
        self._post(mem, "synthesizer", synth_out)

        self._maybe_archive(question, synth_out)

        return WorkflowResult(
            question=question,
            modeling=StageResult("建模智能体", model_out),
            programming=StageResult("编程智能体", prog_out),
            writing=StageResult("写作智能体", write_out),
            synthesis=synth_out,
            memory=mem,
        )

    # ---- 流式串行（兼容原 UI） ----

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

        data_ctx = ""
        if enable_data_engineer:
            data_out = self.data_engineer.invoke(
                f"任务：{question}\n\nRAG参考：\n{rag_ctx}"
            )
            self._post(mem, "data_engineer", data_out)
            data_ctx = f"\n\n数据预处理结果：\n{data_out}"

        # 建模
        model_in = self._build_prompt(question, "", rag_ctx,
                                      {"数据预处理结果": data_out} if data_ctx else None)
        model_out = self.modeler.stream(model_in, on_token=on_modeling_token)
        self._post(mem, "modeling", model_out)

        # 编程 — 注入 STM 上下文
        stm_ctx = self._get_stm_context(mem)
        prog_in = self._build_prompt(question, stm_ctx, rag_ctx, {"建模方案": model_out})
        prog_out = self.programmer.stream(prog_in, on_token=on_programming_token)
        self._post(mem, "programming", prog_out)

        # 写作 — 注入 STM 上下文
        stm_ctx = self._get_stm_context(mem)
        write_in = self._build_prompt(question, stm_ctx, rag_ctx, {
            "建模方案": model_out,
            "编程方案": prog_out,
        })
        write_out = self.writer.stream(write_in, on_token=on_writing_token)
        self._post(mem, "writing", write_out)

        # 总控整合 — 注入 STM 上下文
        stm_ctx = self._get_stm_context(mem)
        synth_in = self._build_prompt(question, stm_ctx, "", {
            "建模方案": model_out,
            "编程方案": prog_out,
            "写作方案": write_out,
        })
        synth_out = self.synthesizer.stream(synth_in, on_token=on_synthesis_token)
        self._post(mem, "synthesizer", synth_out)

        self._maybe_archive(question, synth_out)

        return WorkflowResult(
            question=question,
            modeling=StageResult("建模智能体", model_out),
            programming=StageResult("编程智能体", prog_out),
            writing=StageResult("写作智能体", write_out),
            synthesis=synth_out,
            memory=mem,
        )
