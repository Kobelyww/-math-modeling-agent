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

    def _maybe_archive(self, question: str, result_summary: str) -> None:
        """求解完成后归档到长期记忆。"""
        if self.memory:
            self.memory.archive_solve(question, result_summary)

    def _rag_context(self, question: str, top_k: int = 6) -> str:
        parts: list[str] = []

        # 1. 长期记忆召回（历史相似题目、成功模式）
        if self.memory:
            ltm_context = self.memory.recall(question, top_k=3)
            if ltm_context:
                parts.append(ltm_context)

        # 2. RAG 论文检索
        if self.rag:
            if self.rag.has_embeddings:
                chunks = self.rag.query_hybrid(question, top_k=top_k, alpha=0.6)
            else:
                chunks = self.rag.query(question, top_k=top_k)
            if chunks:
                parts.append(_format_rag_context(chunks))

        return "\n\n---\n\n".join(parts) if parts else "暂无检索上下文。"

    # ---- 策略一：串行流水线（原始行为） ----

    def solve_sequential(
        self,
        question: str,
        top_k: int = 6,
        memory: SharedMemory | None = None,
        enable_data_engineer: bool = False,
    ) -> WorkflowResult:
        mem = self._get_stm(memory)
        rag_ctx = self._rag_context(question, top_k)

        # 数据预处理（可选）
        data_ctx = ""
        if enable_data_engineer:
            data_out = self.data_engineer.invoke(
                f"任务：{question}\n\nRAG参考：\n{rag_ctx}"
            )
            self._post(mem, "data_engineer", data_out)
            data_ctx = f"\n\n数据预处理结果：\n{data_out}"

        # 建模
        model_out = self.modeler.invoke(f"任务：{question}\n\nRAG参考：\n{rag_ctx}{data_ctx}")
        self._post(mem, "modeling", model_out)
        mem.advance_round()

        # 编程
        prog_in = (
            f"任务：{question}\n\n建模专家输出：\n{model_out}\n\nRAG参考：\n{rag_ctx}"
        )
        prog_out = self.programmer.invoke(prog_in)
        self._post(mem, "programming", prog_out)

        # 代码审查
        debug_out = self.code_debugger.invoke(
            f"原始任务：{question}\n\n编程输出：\n{prog_out[:4000]}\n\n请审查以上代码。"
        )
        self._post(mem, "code_debugger", debug_out)
        mem.advance_round()

        # 写作
        write_in = (
            f"任务：{question}\n\n"
            f"建模专家输出：\n{model_out}\n\n"
            f"编程专家输出：\n{prog_out}\n\n"
            f"代码审查：\n{debug_out}\n\n"
            f"RAG参考：\n{rag_ctx}"
        )
        write_out = self.writer.invoke(write_in)
        self._post(mem, "writing", write_out)
        mem.advance_round()

        # 总控整合
        synth_in = (
            f"任务：{question}\n\n"
            f"建模专家：\n{model_out}\n\n"
            f"编程专家：\n{prog_out}\n\n"
            f"写作专家：\n{write_out}"
        )
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
        model_out = self.modeler.invoke(f"任务：{question}\n\nRAG参考：\n{rag_ctx}{data_ctx}")
        model_review = ""
        for rnd in range(max_review_rounds):
            review = self.reviewer.review("建模智能体", model_out, question)
            self._post(mem, "reviewer(modeling)", review)
            if rnd > 0 and not self._review_needs_revision(review, "建模"):
                break
            refine_prompt = (
                f"任务：{question}\n\n"
                f"你的上一版输出：\n{model_out}\n\n"
                f"评审反馈：\n{review}\n\n"
                f"请根据评审意见修改完善你的建模方案。"
            )
            model_out = self.modeler.invoke(refine_prompt)
            model_review = review
        self._post(mem, "modeling", model_out)
        mem.advance_round()

        # --- 编程 + 评审循环 ---
        prog_in = f"任务：{question}\n\n建模专家输出：\n{model_out}\n\nRAG参考：\n{rag_ctx}"
        prog_out = self.programmer.invoke(prog_in)
        prog_review = ""
        for rnd in range(max_review_rounds):
            review = self.reviewer.review("编程智能体", prog_out, question)
            self._post(mem, "reviewer(programming)", review)
            if rnd > 0 and not self._review_needs_revision(review, "编程"):
                break
            refine_prompt = (
                f"任务：{question}\n\n"
                f"建模方案：\n{model_out}\n\n"
                f"你的上一版输出：\n{prog_out}\n\n"
                f"评审反馈：\n{review}\n\n"
                f"请根据评审意见修改完善你的实现方案。"
            )
            prog_out = self.programmer.invoke(refine_prompt)
            prog_review = review
        self._post(mem, "programming", prog_out)

        # 代码审查
        debug_out = self.code_debugger.invoke(
            f"原始任务：{question}\n\n编程输出（已评审修改）：\n{prog_out[:4000]}"
        )
        self._post(mem, "code_debugger", debug_out)
        mem.advance_round()

        # --- 写作 + 评审循环 ---
        write_in = (
            f"任务：{question}\n\n"
            f"建模专家输出：\n{model_out}\n\n"
            f"编程专家输出：\n{prog_out}\n\n"
            f"代码审查：\n{debug_out}\n\n"
            f"RAG参考：\n{rag_ctx}"
        )
        write_out = self.writer.invoke(write_in)
        write_review = ""
        for rnd in range(max_review_rounds):
            review = self.reviewer.review("写作智能体", write_out, question)
            self._post(mem, "reviewer(writing)", review)
            if rnd > 0 and not self._review_needs_revision(review, "写作"):
                break
            refine_prompt = (
                f"任务：{question}\n\n"
                f"建模方案：\n{model_out}\n\n"
                f"编程方案：\n{prog_out}\n\n"
                f"你的上一版输出：\n{write_out}\n\n"
                f"评审反馈：\n{review}\n\n"
                f"请根据评审意见修改完善你的论文写作方案。"
            )
            write_out = self.writer.invoke(refine_prompt)
            write_review = review
        self._post(mem, "writing", write_out)
        mem.advance_round()

        # --- 总控整合 ---
        synth_in = (
            f"任务：{question}\n\n"
            f"建模专家（已评审）：\n{model_out}\n\n"
            f"编程专家（已评审）：\n{prog_out}\n\n"
            f"写作专家（已评审）：\n{write_out}"
        )
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

        # 建模先行（编程和写作都依赖建模结果）
        model_out = self.modeler.invoke(f"任务：{question}\n\nRAG参考：\n{rag_ctx}{data_ctx}")
        self._post(mem, "modeling", model_out)

        # 编程和写作并行
        def run_programmer() -> str:
            return self.programmer.invoke(
                f"任务：{question}\n\n建模专家输出：\n{model_out}\n\nRAG参考：\n{rag_ctx}"
            )

        def run_writer() -> str:
            return self.writer.invoke(
                f"任务：{question}\n\n建模专家输出：\n{model_out}\n\nRAG参考：\n{rag_ctx}"
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            prog_future = executor.submit(run_programmer)
            write_future = executor.submit(run_writer)
            prog_out = prog_future.result()
            write_out = write_future.result()

        self._post(mem, "programming", prog_out)
        self._post(mem, "writing", write_out)

        # 代码审查（并行模式下额外对代码质量把关）
        debug_out = self.code_debugger.invoke(
            f"原始任务：{question}\n\n编程输出：\n{prog_out[:4000]}"
        )
        self._post(mem, "code_debugger", debug_out)
        mem.advance_round()

        # 总控整合
        synth_in = (
            f"任务：{question}\n\n"
            f"建模专家：\n{model_out}\n\n"
            f"编程专家：\n{prog_out}\n\n"
            f"代码审查：\n{debug_out}\n\n"
            f"写作专家：\n{write_out}"
        )
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
        rag_ctx = self._rag_context(question, top_k)

        data_ctx = ""
        if enable_data_engineer:
            data_out = self.data_engineer.invoke(
                f"任务：{question}\n\nRAG参考：\n{rag_ctx}"
            )
            data_ctx = f"\n\n数据预处理结果：\n{data_out}"

        model_out = self.modeler.stream(
            f"任务：{question}\n\nRAG参考：\n{rag_ctx}{data_ctx}",
            on_token=on_modeling_token,
        )
        prog_out = self.programmer.stream(
            f"任务：{question}\n\n建模专家输出：\n{model_out}\n\nRAG参考：\n{rag_ctx}",
            on_token=on_programming_token,
        )
        write_out = self.writer.stream(
            f"任务：{question}\n\n建模专家输出：\n{model_out}\n\n编程专家输出：\n{prog_out}\n\nRAG参考：\n{rag_ctx}",
            on_token=on_writing_token,
        )
        synth_out = self.synthesizer.stream(
            f"任务：{question}\n\n建模专家：\n{model_out}\n\n编程专家：\n{prog_out}\n\n写作专家：\n{write_out}",
            on_token=on_synthesis_token,
        )

        return WorkflowResult(
            question=question,
            modeling=StageResult("建模智能体", model_out),
            programming=StageResult("编程智能体", prog_out),
            writing=StageResult("写作智能体", write_out),
            synthesis=synth_out,
        )