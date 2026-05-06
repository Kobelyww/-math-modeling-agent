from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable

from .agents import (
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
from .memory import SharedMemory
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

    def __init__(self, settings: Settings, rag: PaperRAG | None = None) -> None:
        base_llm = create_llm(settings)
        reviewer_temp = settings.get_agent_config("reviewer").temperature
        reviewer_llm = create_llm(settings, temperature=reviewer_temp)

        agents = create_agents(base_llm, reviewer_llm=reviewer_llm, max_retries=settings.max_retries)
        self.modeler: ModelerAgent = agents["modeler"]
        self.programmer: ProgrammerAgent = agents["programmer"]
        self.writer: WriterAgent = agents["writer"]
        self.reviewer: ReviewerAgent = agents["reviewer"]
        self.synthesizer: SynthesizerAgent = agents["synthesizer"]
        self.rag = rag

    def _rag_context(self, question: str, top_k: int = 6) -> str:
        if self.rag is None:
            return "暂无检索上下文。"
        chunks = self.rag.query(question, top_k=top_k)
        return _format_rag_context(chunks)

    # ---- 策略一：串行流水线（原始行为） ----

    def solve_sequential(
        self,
        question: str,
        top_k: int = 6,
        memory: SharedMemory | None = None,
    ) -> WorkflowResult:
        mem = memory or SharedMemory()
        rag_ctx = self._rag_context(question, top_k)

        # 建模
        model_out = self.modeler.invoke(f"任务：{question}\n\nRAG参考：\n{rag_ctx}")
        mem.post("modeling", model_out)
        mem.advance_round()

        # 编程
        prog_in = (
            f"任务：{question}\n\n建模专家输出：\n{model_out}\n\nRAG参考：\n{rag_ctx}"
        )
        prog_out = self.programmer.invoke(prog_in)
        mem.post("programming", prog_out)
        mem.advance_round()

        # 写作
        write_in = (
            f"任务：{question}\n\n"
            f"建模专家输出：\n{model_out}\n\n"
            f"编程专家输出：\n{prog_out}\n\n"
            f"RAG参考：\n{rag_ctx}"
        )
        write_out = self.writer.invoke(write_in)
        mem.post("writing", write_out)
        mem.advance_round()

        # 总控整合
        synth_in = (
            f"任务：{question}\n\n"
            f"建模专家：\n{model_out}\n\n"
            f"编程专家：\n{prog_out}\n\n"
            f"写作专家：\n{write_out}"
        )
        synth_out = self.synthesizer.invoke(synth_in)
        mem.post("synthesizer", synth_out)

        return WorkflowResult(
            question=question,
            modeling=StageResult("建模智能体", model_out),
            programming=StageResult("编程智能体", prog_out),
            writing=StageResult("写作智能体", write_out),
            synthesis=synth_out,
            memory=mem,
        )

    # ---- 策略二：带评审反思的深度协作 ----

    def solve_with_review(
        self,
        question: str,
        top_k: int = 6,
        max_review_rounds: int = 1,
        memory: SharedMemory | None = None,
    ) -> WorkflowResult:
        mem = memory or SharedMemory()
        rag_ctx = self._rag_context(question, top_k)

        # --- 建模 + 评审循环 ---
        model_out = self.modeler.invoke(f"任务：{question}\n\nRAG参考：\n{rag_ctx}")
        model_review = ""
        for rnd in range(max_review_rounds):
            review = self.reviewer.review("建模智能体", model_out, question)
            mem.post("reviewer(modeling)", review)
            if "无问题" in review and rnd > 0:
                break
            refine_prompt = (
                f"任务：{question}\n\n"
                f"你的上一版输出：\n{model_out}\n\n"
                f"评审反馈：\n{review}\n\n"
                f"请根据评审意见修改完善你的建模方案。"
            )
            model_out = self.modeler.invoke(refine_prompt)
            model_review = review
        mem.post("modeling", model_out)
        mem.advance_round()

        # --- 编程 + 评审循环 ---
        prog_in = f"任务：{question}\n\n建模专家输出：\n{model_out}\n\nRAG参考：\n{rag_ctx}"
        prog_out = self.programmer.invoke(prog_in)
        prog_review = ""
        for rnd in range(max_review_rounds):
            review = self.reviewer.review("编程智能体", prog_out, question)
            mem.post("reviewer(programming)", review)
            if "无问题" in review and rnd > 0:
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
        mem.post("programming", prog_out)
        mem.advance_round()

        # --- 写作 + 评审循环 ---
        write_in = (
            f"任务：{question}\n\n"
            f"建模专家输出：\n{model_out}\n\n"
            f"编程专家输出：\n{prog_out}\n\n"
            f"RAG参考：\n{rag_ctx}"
        )
        write_out = self.writer.invoke(write_in)
        write_review = ""
        for rnd in range(max_review_rounds):
            review = self.reviewer.review("写作智能体", write_out, question)
            mem.post("reviewer(writing)", review)
            if "无问题" in review and rnd > 0:
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
        mem.post("writing", write_out)
        mem.advance_round()

        # --- 总控整合 ---
        synth_in = (
            f"任务：{question}\n\n"
            f"建模专家（已评审）：\n{model_out}\n\n"
            f"编程专家（已评审）：\n{prog_out}\n\n"
            f"写作专家（已评审）：\n{write_out}"
        )
        synth_out = self.synthesizer.invoke(synth_in)
        mem.post("synthesizer", synth_out)

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
    ) -> WorkflowResult:
        mem = memory or SharedMemory()
        rag_ctx = self._rag_context(question, top_k)

        # 建模先行（编程和写作都依赖建模结果）
        model_out = self.modeler.invoke(f"任务：{question}\n\nRAG参考：\n{rag_ctx}")
        mem.post("modeling", model_out)

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

        mem.post("programming", prog_out)
        mem.post("writing", write_out)
        mem.advance_round()

        # 总控整合
        synth_in = (
            f"任务：{question}\n\n"
            f"建模专家：\n{model_out}\n\n"
            f"编程专家：\n{prog_out}\n\n"
            f"写作专家：\n{write_out}"
        )
        synth_out = self.synthesizer.invoke(synth_in)
        mem.post("synthesizer", synth_out)

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
    ) -> WorkflowResult:
        rag_ctx = self._rag_context(question, top_k)

        model_out = self.modeler.stream(
            f"任务：{question}\n\nRAG参考：\n{rag_ctx}",
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