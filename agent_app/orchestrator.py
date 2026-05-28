
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
    PlannerAgent,
    ProgrammerAgent,
    ReviewerAgent,
    SynthesizerAgent,
    WriterAgent,
    create_agents,
    resolve_agent_skills,
)
from .agent_loop import (
    ACTION_TO_ROLE,
    AgentLoopDecision,
    AgentLoopState,
    AgentLoopTrace,
    fallback_next_decision,
    parse_coordinator_decision,
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
from .skills import SkillRegistry, SkillResolver
from .subagent import configure_subagent_llm, _set_code_tools, spawn_subagent
from .base import register_tool_executor

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
    agent_loop_trace: list[AgentLoopTrace] = field(default_factory=list)

    @property
    def build_log(self) -> str:
        return getattr(self, "_build_log", "")

    @build_log.setter
    def build_log(self, value: str) -> None:
        setattr(self, "_build_log", value)

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
            "agent_loop_trace": [
                {
                    "step": trace.step,
                    "action": trace.action,
                    "role": trace.role,
                    "reason": trace.reason,
                    "instruction": trace.instruction,
                    "output": trace.output,
                }
                for trace in self.agent_loop_trace
            ],
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
        build_log = getattr(self, "build_log", "")
        if build_log:
            lines.append("")
            lines.append(build_log)
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


# STM 阶段标签 → 工具注册键（_agent_tools 使用 modeler/programmer 等）
_ROLE_LABEL_ALIASES: dict[str, str] = {
    "modeling": "modeler",
    "programming": "programmer",
    "writing": "writer",
    "coordinator": "synthesizer",
}

_AGENT_TOOL_ROLE: dict[type, str] = {
    DataEngineerAgent: "data_engineer",
    ModelerAgent: "modeler",
    ProgrammerAgent: "programmer",
    CodeDebuggerAgent: "code_debugger",
    WriterAgent: "writer",
    ReviewerAgent: "reviewer",
    SynthesizerAgent: "synthesizer",
    PlannerAgent: "planner",
}

_MAX_TOOL_ROUNDS: dict[str, int] = {
    "programmer": 6,
    "writer": 6,
    "code_debugger": 5,
    "modeler": 4,
    "data_engineer": 4,
    "synthesizer": 4,
    "planner": 4,
}


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
        self.planner: PlannerAgent = agents["planner"]
        self.rag = rag
        self.skill_registry = SkillRegistry()
        self.skill_resolver = SkillResolver(registry=self.skill_registry, max_skills=4)

        # Default streaming callbacks — set by CLI for real-time output
        self.on_agent_token: Callable[[str, str], None] | None = None
        self.on_agent_thinking: Callable[[str, str], None] | None = None

        # Subagent system — configure LLM and register code tools
        configure_subagent_llm(base_llm)
        from .tools import (python_exec, pip_install, read_csv_info,
                           latex_template, latex_compile, latex_render_math,
                           calculator, current_time, save_note, read_note, list_notes,
                           nature_viz_template, model_reference, writing_rules,
                           search_arxiv, search_semantic_scholar, search_crossref,
                           fetch_paper_to_kb)
        from .exploration import (read_file, search_files, search_content,
                                  list_directory, web_search, web_fetch,
                                  write_file)
        _set_code_tools(python_exec.func, pip_install.func, read_csv_info.func)

        # Register all tools for agent tool-calling
        _tool_map = {
            "python_exec": python_exec, "pip_install": pip_install,
            "read_csv_info": read_csv_info, "latex_template": latex_template,
            "latex_compile": latex_compile, "latex_render_math": latex_render_math,
            "calculator": calculator, "current_time": current_time,
            "save_note": save_note, "read_note": read_note, "list_notes": list_notes,
            "nature_viz_template": nature_viz_template,
            "model_reference": model_reference, "writing_rules": writing_rules,
            "search_arxiv": search_arxiv, "search_semantic_scholar": search_semantic_scholar,
            "search_crossref": search_crossref, "fetch_paper_to_kb": fetch_paper_to_kb,
            "read_file": read_file, "search_files": search_files,
            "search_content": search_content, "list_directory": list_directory,
            "web_search": web_search, "web_fetch": web_fetch,
            "write_file": write_file,
            "spawn_subagent": spawn_subagent,
        }
        for name, tool_obj in _tool_map.items():
            register_tool_executor(name, tool_obj)

        # Per-agent tool assignments — every agent gets write_file + save_note + spawn_subagent
        self._agent_tools: dict[str, list] = {
            "modeler": [write_file, save_note, spawn_subagent, web_search, search_arxiv, model_reference, writing_rules, read_file, search_content],
            "programmer": [write_file, save_note, python_exec, spawn_subagent, read_file, search_files, search_content, read_csv_info, pip_install],
            "code_debugger": [write_file, save_note, python_exec, read_file, search_content, spawn_subagent],
            "writer": [write_file, save_note, latex_template, latex_compile, spawn_subagent, web_search, read_note, writing_rules, read_file, list_directory],
            "synthesizer": [write_file, save_note, spawn_subagent, web_search, search_files, search_content, read_file, list_directory, web_fetch],
            "reviewer": [write_file, save_note, read_file, search_content, web_search],
            "planner": [write_file, save_note, spawn_subagent, web_search, model_reference, writing_rules, search_files, search_content, read_file],
            "data_engineer": [write_file, save_note, read_csv_info, search_files, read_file, python_exec],
        }

        # 默认终止条件
        self._default_conditions = CompoundCondition(
            TokenBudgetCondition(max_total_tokens=200000),
            TimeoutCondition(timeout_seconds=600.0),
        )

    def _resolve_agent_tools(self, agent: BaseAgent, role_label: str) -> list:
        """将 STM 阶段标签或 Agent 实例解析为 _agent_tools 的注册键。"""
        for agent_cls, key in _AGENT_TOOL_ROLE.items():
            if isinstance(agent, agent_cls):
                return self._agent_tools.get(key, [])
        tool_key = _ROLE_LABEL_ALIASES.get(role_label, role_label)
        return self._agent_tools.get(tool_key, [])

    def _max_tool_rounds(self, agent: BaseAgent, role_label: str) -> int:
        for agent_cls, key in _AGENT_TOOL_ROLE.items():
            if isinstance(agent, agent_cls):
                return _MAX_TOOL_ROUNDS.get(key, 4)
        tool_key = _ROLE_LABEL_ALIASES.get(role_label, role_label)
        return _MAX_TOOL_ROUNDS.get(tool_key, 4)

    def _finalize_workflow(self, result: WorkflowResult) -> WorkflowResult:
        """工作流结束后自动落盘、执行代码并编译 LaTeX。"""
        try:
            setattr(result, "build_log", self._save_outputs(result))
        except Exception as exc:
            logger.warning("Failed to save workflow outputs: %s", exc)
            result.errors.append(f"[输出保存] {exc}")
        return result

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
                     token_budget: TokenBudgetCondition | None = None,
                     on_token: Callable[[str], None] | None = None,
                     on_thinking: Callable[[str], None] | None = None) -> str:
        """安全调用 agent；有工具时走工具循环，否则流式输出。"""
        # Fall back to orchestrator-level callbacks when caller doesn't provide them
        _on_token = on_token
        _on_thinking = on_thinking
        if _on_token is None and self.on_agent_token:
            _label = role_label
            _on_token = lambda t, lbl=_label: self.on_agent_token(t, lbl)
        if _on_thinking is None and self.on_agent_thinking:
            _label = role_label
            _on_thinking = lambda t, lbl=_label: self.on_agent_thinking(t, lbl)

        try:
            agent_tools = self._resolve_agent_tools(agent, role_label)
            if agent_tools:
                result = agent.invoke_with_tools(
                    prompt,
                    tools=agent_tools,
                    max_tool_rounds=self._max_tool_rounds(agent, role_label),
                )
                if _on_token and result:
                    chunk_size = 2048
                    for start in range(0, len(result), chunk_size):
                        _on_token(result[start:start + chunk_size])
            else:
                result = agent.stream(prompt, on_token=_on_token, on_thinking=_on_thinking)
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
                     on_token: Callable[[str], None] | None = None,
                     on_thinking: Callable[[str], None] | None = None) -> str:
        """安全调用 agent；有工具时走 ReAct 工具循环，否则流式输出。"""
        _on_token = on_token
        _on_thinking = on_thinking
        if _on_token is None and self.on_agent_token:
            _label = role_label
            _on_token = lambda t, lbl=_label: self.on_agent_token(t, lbl)
        if _on_thinking is None and self.on_agent_thinking:
            _label = role_label
            _on_thinking = lambda t, lbl=_label: self.on_agent_thinking(t, lbl)

        try:
            result = agent.stream(prompt, on_token=_on_token, on_thinking=_on_thinking)
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

    def _get_stm_context(self, stm: SharedMemory, max_tokens: int = 3000,
                         compressed_only: bool = False) -> str:
        """获取 STM 上下文。

        compressed_only=True：只返回压缩前缀（历史脉络），
        不包括 recent_window——用于已有显式阶段输出的后续 Agent 提示词，
        避免同一份建模/编程输出在 STM 和 extra_contexts 中重复拼接。
        """
        if self.memory:
            ctx = self.memory.get_context(max_tokens=max_tokens, compressed_only=compressed_only)
        else:
            ctx = stm.format_context(max_tokens=max_tokens, compressed_only=compressed_only)
        return ctx

    def _maybe_archive(self, question: str, result_summary: str) -> None:
        if self.memory:
            try:
                self.memory.archive_solve(question, result_summary)
            except Exception:
                logger.debug("Archive failed", exc_info=True)

    # ─── 文件生成与验证 ─────────────────────────────────────────────────

    @staticmethod
    def _extract_code_blocks(text: str, lang: str = "python") -> list[str]:
        import re
        langs = [lang] if lang != "python" else ["python", "py"]
        blocks: list[str] = []
        for lg in langs:
            pattern = rf"```{re.escape(lg)}\s*\n(.*?)```"
            blocks.extend(m.strip() for m in re.findall(pattern, text, re.DOTALL))
        return blocks

    @staticmethod
    def _extract_latex_document(text: str) -> str | None:
        import re
        m = re.search(r"\\documentclass.*?\\end\{document\}", text, re.DOTALL)
        if m:
            return m.group(0)
        for block in re.findall(r"```(?:latex|tex)\s*\n(.*?)```", text, re.DOTALL):
            if "\\documentclass" in block:
                return block.strip()
        return None

    def _save_outputs(self, result: WorkflowResult) -> str:
        """Persist outputs AND execute/compile them. Returns a build log."""
        from pathlib import Path
        out = Path(__file__).resolve().parent / "output"
        out.mkdir(exist_ok=True)
        lines: list[str] = ["", "═" * 50, "  文件生成与验证", "═" * 50]

        # ── 1. Modeling report ──────────────────────────────────────
        if result.modeling.content:
            (out / "modeling_report.md").write_text(result.modeling.content, encoding="utf-8")
            lines.append("✅ modeling_report.md")

        # ── 2. Python code → save + execute ────────────────────────
        py_blocks = self._extract_code_blocks(result.programming.content, "python")
        py_path = None
        if py_blocks:
            for i, block in enumerate(py_blocks):
                fname = "solve.py" if i == 0 else f"solve_part{i+1}.py"
                path = out / fname
                path.write_text(block, encoding="utf-8")
                lines.append(f"✅ {fname} ({len(block)} chars)")
                if i == 0:
                    py_path = path
        else:
            # No code block found — save full output as .py anyway
            py_path = out / "solve_raw.py"
            py_path.write_text(result.programming.content, encoding="utf-8")
            lines.append(f"✅ solve_raw.py (full output, {len(result.programming.content)} chars)")

        if py_path:
            lines.append("── 执行 Python 代码 ──")
            try:
                from .tools import python_exec
                exec_result = python_exec.invoke({"code": py_path.read_text(encoding="utf-8")})
                lines.append(exec_result[:1500])
            except Exception as exc:
                lines.append(f"⚠ 执行失败: {exc}")

        # ── 3. LaTeX → save + compile ──────────────────────────────
        latex = self._extract_latex_document(result.writing.content)
        tex_path = None
        if latex:
            tex_path = out / "paper.tex"
            tex_path.write_text(latex, encoding="utf-8")
            lines.append(f"✅ paper.tex ({len(latex)} chars)")
        else:
            # No LaTeX document found — save raw as .tex
            tex_path = out / "paper_raw.tex"
            tex_path.write_text(result.writing.content, encoding="utf-8")
            lines.append(f"✅ paper_raw.tex (full output, {len(result.writing.content)} chars)")

        if tex_path:
            lines.append("── 编译 LaTeX ──")
            try:
                from .tools import latex_compile
                compile_result = latex_compile.invoke({
                    "content": tex_path.read_text(encoding="utf-8"),
                    "filename": tex_path.stem,
                })
                lines.append(compile_result[:1000])
            except Exception as exc:
                lines.append(f"⚠ 编译失败: {exc}")

        # ── 4. Synthesis ───────────────────────────────────────────
        if result.synthesis:
            (out / "final_synthesis.md").write_text(result.synthesis, encoding="utf-8")
            lines.append("✅ final_synthesis.md")

        # ── 5. Full result JSON ────────────────────────────────────
        def _stage_to_json(stage: StageResult) -> dict:
            return {
                "role": stage.role,
                "content": stage.content,
                "review_feedback": stage.review_feedback,
                "round_idx": stage.round_idx,
            }

        jsonable_result = {
            "question": result.question,
            "modeling": _stage_to_json(result.modeling),
            "programming": _stage_to_json(result.programming),
            "writing": _stage_to_json(result.writing),
            "synthesis": result.synthesis,
            "errors": result.errors,
            "total_prompt_tokens": result.total_prompt_tokens,
            "total_completion_tokens": result.total_completion_tokens,
            "total_tokens": result.total_tokens,
            "estimated_cost_usd": round(result.estimated_cost_usd, 6),
            "elapsed_seconds": round(result.elapsed_seconds, 1),
            "agent_loop_trace": [
                {
                    "step": trace.step,
                    "action": trace.action,
                    "role": trace.role,
                    "reason": trace.reason,
                    "instruction": trace.instruction,
                    "output": trace.output,
                }
                for trace in result.agent_loop_trace
            ],
        }
        (out / "workflow_result.json").write_text(
            json.dumps(jsonable_result, ensure_ascii=False, indent=2), encoding="utf-8")
        lines.append("✅ workflow_result.json")
        lines.append("═" * 50)

        build_log = "\n".join(lines)
        logger.info("Output files saved to %s", out)
        return build_log

    def _rag_context(self, question: str, top_k: int = 6) -> str:
        parts: list[str] = []

        if self.memory:
            try:
                ltm_context = self.memory.recall(question, top_k=3)
                if ltm_context:
                    parts.append(ltm_context)
            except (UnicodeEncodeError, UnicodeDecodeError, Exception):
                logger.debug("LTM recall failed for query encoding", exc_info=True)

        if self.rag:
            try:
                if self.rag.has_embeddings:
                    chunks = self.rag.query_hybrid(question, top_k=top_k, alpha=0.6)
                else:
                    chunks = self.rag.query(question, top_k=top_k)
                if chunks:
                    parts.append(_format_rag_context(chunks))
            except Exception:
                logger.debug("RAG query failed", exc_info=True)

        return "\n\n---\n\n".join(parts) if parts else "暂无检索上下文。"

    # ─── 提示词构建 ───────────────────────────────────────────────────

    def _build_prompt(self, question: str, stm_ctx: str, rag_ctx: str,
                      extra_contexts: dict[str, str] | None = None,
                      agent_role: str | None = None,
                      inject_skills: bool = False) -> str:
        """构建 Agent prompt，支持渐进式技能注入。

        stm_ctx 已由调用方决定是否包含 recent_window：
        - 有 extra_contexts 时：调用方传 compressed_only=True，STM 只含压缩前缀
        - 无 extra_contexts 时：调用方传 compressed_only=False，STM 含完整上下文

        inject_skills=True 时，将根据任务和 agent_role 注入相关领域知识，
        实现类似 Claude Code Skills 的渐进式披露效果。
        """
        parts = [f"任务：{question}"]

        if stm_ctx:
            parts.append(f"历史脉络（压缩摘要）：\n{stm_ctx}")

        # 渐进式披露：注入任务相关技能
        if inject_skills and agent_role:
            skill_content = resolve_agent_skills(
                question, agent_role, skill_registry=self.skill_registry,
            )
            if skill_content:
                parts.append(f"## 领域专业知识（按需加载）\n\n{skill_content}")

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
    # 策略零：Plan-and-Execute（规划先行，再执行）
    # ═════════════════════════════════════════════════════════════════

    def plan_only(
        self,
        question: str,
        top_k: int = 6,
        memory: SharedMemory | None = None,
    ) -> str:
        """仅生成求解计划，不执行。

        Plan phase of Plan-and-Execute. The planner analyzes the problem,
        decomposes it, selects candidate models, identifies needed skills,
        and produces a structured execution plan. User can review and
        modify before calling solve_with_plan().

        Args:
            question: The modeling problem
            top_k: Number of RAG chunks to retrieve
            memory: Optional SharedMemory

        Returns:
            Structured plan as markdown text
        """
        mem = self._get_stm(memory)
        rag_ctx = self._rag_context(question, top_k)

        # Resolve planning-relevant skills (cross-domain for analysis)
        plan_skills = resolve_agent_skills(
            question, "planner", skill_registry=self.skill_registry,
        )

        # Get LTM context
        ltm_context = (
            self.memory.recall(question, top_k=5)
            if self.memory else "暂无长期记忆。"
        )

        # Generate the plan
        logger.info("[Plan] 生成求解计划...")
        plan = self.planner.plan(
            question=question,
            rag_context=rag_ctx,
            memory_context=ltm_context,
            skill_context=plan_skills,
        )

        self._post(mem, "planner", plan, triggered_by="")
        return plan

    def _build_agent_loop_decision_prompt(
        self,
        state: AgentLoopState,
        rag_ctx: str,
        max_steps: int,
    ) -> str:
        """Build the coordinator prompt for the dynamic agent loop."""
        outputs = []
        for role, content in state.outputs.items():
            if content.strip():
                outputs.append(f"[{role}]\n{content[:2500]}")
        outputs_text = "\n\n".join(outputs) if outputs else "No agent outputs yet."
        trace_text = state.trace_text(max_chars=6000) or "No loop steps yet."
        actions = ", ".join(sorted([*ACTION_TO_ROLE.keys(), "ask_user", "final"]))

        return f"""You are the coordinator for a multi-agent mathematical modeling workflow.
Choose exactly one next action.

Original task:
{state.question}

Maximum loop steps: {max_steps}

Available actions:
{actions}

Action meanings:
- explore: record missing context or investigation notes without calling a specialist agent.
- model: ask the modeling agent for mathematical formulation.
- program: ask the programming agent for code or computational implementation.
- debug: ask the code debugger to inspect or improve the programming output.
- write: ask the writing agent for report/paper content.
- review: ask the reviewer to critique an existing output.
- synthesize: ask the synthesizer for final integration.
- ask_user: stop and request clarification from the user.
- final: stop because the current synthesis is sufficient.

Return only a JSON object with these keys:
{{
  "action": "model|program|debug|write|review|synthesize|explore|ask_user|final",
  "reason": "brief reason",
  "target_agent": "modeler|programmer|code_debugger|writer|reviewer|synthesizer|explore",
  "instruction": "specific instruction for the selected step"
}}

Retrieved context:
{rag_ctx[:5000]}

Current outputs:
{outputs_text}

Loop trace:
{trace_text}
"""

    def _decide_agent_loop_next(
        self,
        state: AgentLoopState,
        rag_ctx: str,
        max_steps: int,
    ) -> AgentLoopDecision:
        prompt = self._build_agent_loop_decision_prompt(state, rag_ctx, max_steps)
        try:
            raw = self.synthesizer.invoke(prompt)
            return parse_coordinator_decision(raw)
        except Exception as exc:
            logger.warning("Agent loop coordinator decision failed; using fallback: %s", exc)
            return fallback_next_decision(state)

    def solve_agent_loop(
        self,
        question: str,
        top_k: int = 6,
        memory: SharedMemory | None = None,
        max_steps: int = 8,
        conditions: list[BaseCondition] | None = None,
    ) -> WorkflowResult:
        """Conversation-driven dynamic agent loop coordinated by DeepSeek."""
        mem = self._get_stm(memory)
        rag_ctx = self._rag_context(question, top_k)
        errors: list[str] = []
        state = AgentLoopState(question=question, errors=errors)
        token_budget = TokenBudgetCondition(max_total_tokens=200000)
        timeout = TimeoutCondition(timeout_seconds=600.0)
        timeout.start()
        active_conditions: list[BaseCondition] = [token_budget, timeout]
        if conditions:
            active_conditions.extend(conditions)
        started_at = time_module.monotonic()

        model_out = ""
        prog_out = ""
        write_out = ""
        synth_out = ""

        def loop_contexts(decision: AgentLoopDecision) -> dict[str, str]:
            contexts: dict[str, str] = {
                "协调者指令": decision.instruction or decision.reason or "Continue the workflow.",
            }
            if state.trace:
                contexts["动态循环轨迹"] = state.trace_text(max_chars=5000)
            for role, label in [
                ("explore", "探索记录"),
                ("modeling", "建模方案"),
                ("programming", "编程方案"),
                ("code_debugger", "代码审查"),
                ("reviewer", "评审意见"),
                ("writing", "写作方案"),
                ("synthesizer", "已有整合"),
            ]:
                if state.has(role):
                    contexts[label] = state.latest(role)
            return contexts

        def build_step_prompt(decision: AgentLoopDecision, agent_role: str) -> str:
            return self._build_prompt(
                question,
                self._get_stm_context(mem, compressed_only=True),
                rag_ctx,
                loop_contexts(decision),
                agent_role=agent_role,
                inject_skills=False,
            )

        def review_target(decision: AgentLoopDecision) -> tuple[str, str, str]:
            aliases = {
                "model": "modeling",
                "modeler": "modeling",
                "program": "programming",
                "programmer": "programming",
                "debug": "code_debugger",
                "code_debugger": "code_debugger",
                "write": "writing",
                "writer": "writing",
                "synthesize": "synthesizer",
                "synthesizer": "synthesizer",
            }
            key = aliases.get(decision.target_agent.strip().lower(), "")
            if not key or not state.has(key):
                for candidate in ("writing", "programming", "modeling", "synthesizer", "code_debugger"):
                    if state.has(candidate):
                        key = candidate
                        break
            labels = {
                "modeling": "建模智能体",
                "programming": "编程智能体",
                "code_debugger": "代码审查智能体",
                "writing": "写作智能体",
                "synthesizer": "总控智能体",
            }
            return key, labels.get(key, key or "未知输出"), state.latest(key)

        for step in range(1, max_steps + 1):
            stop_reason = self._check_conditions(
                active_conditions,
                mem,
                step - 1,
                timeout.elapsed,
            )
            if stop_reason:
                errors.append(stop_reason)
                synth_out = synth_out or stop_reason
                break

            decision = self._decide_agent_loop_next(state, rag_ctx, max_steps)
            if decision.action not in ACTION_TO_ROLE and decision.action not in {"ask_user", "final"}:
                decision = fallback_next_decision(state)

            if decision.action == "final":
                synth_out = (
                    synth_out
                    or state.latest("synthesizer")
                    or decision.instruction
                    or state.latest("writing")
                    or state.latest("programming")
                    or state.latest("modeling")
                )
                break

            role = ACTION_TO_ROLE.get(decision.action, "synthesizer")
            triggered_by = state.trace[-1].role if state.trace else ""
            output = ""
            should_stop = False

            if decision.action == "explore":
                output = decision.instruction or decision.reason or "Explore the problem context before specialist work."
                self._post(mem, "explore", output, triggered_by=triggered_by)
                state.record_output("explore", output)

            elif decision.action == "model":
                output = self._safe_invoke(
                    self.modeler,
                    build_step_prompt(decision, "modeler"),
                    "modeling",
                    mem,
                    errors,
                    triggered_by=triggered_by,
                    token_budget=token_budget,
                )
                model_out = output
                state.record_output("modeling", output)

            elif decision.action == "program":
                output = self._safe_invoke(
                    self.programmer,
                    build_step_prompt(decision, "programmer"),
                    "programming",
                    mem,
                    errors,
                    triggered_by=triggered_by,
                    token_budget=token_budget,
                )
                prog_out = output
                state.record_output("programming", output)

            elif decision.action == "debug":
                output = self._safe_invoke(
                    self.code_debugger,
                    build_step_prompt(decision, "code_debugger"),
                    "code_debugger",
                    mem,
                    errors,
                    triggered_by=triggered_by or "programming",
                    token_budget=token_budget,
                )
                state.record_output("code_debugger", output)
                base_program = state.latest("programming")
                prog_out = (
                    f"{base_program}\n\n## Code Review\n\n{output}"
                    if base_program else output
                )
                state.record_output("programming", prog_out)

            elif decision.action == "write":
                output = self._safe_invoke(
                    self.writer,
                    build_step_prompt(decision, "writer"),
                    "writing",
                    mem,
                    errors,
                    triggered_by=triggered_by,
                    token_budget=token_budget,
                )
                write_out = output
                state.record_output("writing", output)

            elif decision.action == "review":
                target_key, target_label, target_output = review_target(decision)
                try:
                    output = self.reviewer.review(target_label, target_output, question)
                    usage = getattr(self.reviewer, "last_usage", {})
                    self._post(
                        mem,
                        "reviewer",
                        output,
                        triggered_by=target_key,
                        usage=usage,
                    )
                    token_budget.add_usage(
                        usage.get("prompt_tokens", 0),
                        usage.get("completion_tokens", 0),
                    )
                except Exception as exc:
                    err_msg = f"[reviewer] 执行失败: {exc}"
                    logger.warning(err_msg)
                    errors.append(err_msg)
                    output = f"[reviewer 因错误未能完成: {exc}]"
                    self._post(mem, "reviewer", output, triggered_by=target_key)
                state.record_output("reviewer", output)

            elif decision.action == "synthesize":
                output = self._safe_invoke(
                    self.synthesizer,
                    build_step_prompt(decision, "synthesizer"),
                    "synthesizer",
                    mem,
                    errors,
                    triggered_by=triggered_by,
                    token_budget=token_budget,
                )
                synth_out = output
                state.record_output("synthesizer", output)

            elif decision.action == "ask_user":
                output = decision.instruction or decision.reason or "Need user clarification before continuing."
                self._post(mem, "synthesizer", output, triggered_by=triggered_by)
                synth_out = output
                state.record_output("synthesizer", output)
                should_stop = True

            state.trace.append(
                AgentLoopTrace(
                    step=step,
                    action=decision.action,
                    role=role,
                    reason=decision.reason,
                    instruction=decision.instruction,
                    output=output,
                )
            )
            mem.advance_round()

            if should_stop:
                break

        synth_out = (
            synth_out
            or state.latest("synthesizer")
            or state.latest("writing")
            or state.latest("programming")
            or state.latest("modeling")
            or "Agent loop finished without producing a specialist output."
        )

        self._maybe_archive(question, synth_out)
        result = WorkflowResult(
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
            agent_loop_trace=state.trace,
        )
        self._reset_conditions(active_conditions)
        return self._finalize_workflow(result)

    def solve_with_plan(
        self,
        question: str,
        top_k: int = 6,
        memory: SharedMemory | None = None,
        enable_data_engineer: bool = False,
        conditions: list[BaseCondition] | None = None,
        pre_generated_plan: str | None = None,
    ) -> WorkflowResult:
        """Plan-and-Execute strategy — the recommended approach.

        Phase 0 - PLAN: PlannerAgent analyzes the problem, decomposes it
          into sub-problems, selects candidate models, identifies needed
          skills, and maps agent assignments with dependencies.

        Phase 1 - EXECUTE: Follow the plan — modeling → programming →
          debugging → writing → synthesis. Each agent receives the plan
          as context and knows exactly what it needs to produce.

        Phase 2 - SYNTHESIZE: Final assembly of all outputs.

        This architecture mirrors the classic Plan-and-Execute pattern:
        a planner reasons about the overall approach, then executors
        carry out individual steps with full context of the plan.

        Args:
            question: The modeling problem
            top_k: Number of RAG chunks
            memory: Optional SharedMemory
            enable_data_engineer: Whether to use DataEngineerAgent
            conditions: Additional termination conditions
            pre_generated_plan: If provided, skip plan generation and use this

        Returns:
            WorkflowResult with all stage outputs
        """
        mem = self._get_stm(memory)
        rag_ctx = self._rag_context(question, top_k)
        errors: list[str] = []
        token_budget = TokenBudgetCondition(max_total_tokens=200000)
        timeout = TimeoutCondition(timeout_seconds=600.0)
        timeout.start()
        started_at = time_module.monotonic()

        active_conditions: list[BaseCondition] = [
            MaxRoundCondition(1),
            token_budget,
            timeout,
        ]
        if conditions:
            active_conditions.extend(conditions)

        # ── Phase 0: PLAN ───────────────────────────────────────────
        if pre_generated_plan:
            plan = pre_generated_plan
            logger.info("[Plan] 使用预生成的计划")
        else:
            plan = self.plan_only(question, top_k=top_k, memory=mem)
            logger.info("[Plan] 计划已生成，开始执行...")

        # ── Phase 1: EXECUTE ────────────────────────────────────────

        data_ctx, data_out = "", ""
        if enable_data_engineer:
            data_out = self._safe_invoke(
                self.data_engineer,
                self._build_prompt(question, "", rag_ctx,
                                   {"求解计划": plan},
                                   agent_role="data_engineer", inject_skills=True),
                "data_engineer", mem, errors, token_budget=token_budget,
            )
            data_ctx = f"\n\n数据预处理结果：\n{data_out}"

        # Modeling
        extra = {"求解计划": plan}
        if data_ctx:
            extra["数据预处理结果"] = data_out
        model_in = self._build_prompt(question, "", rag_ctx, extra,
                                      agent_role="modeler", inject_skills=True)
        model_out = self._safe_invoke(self.modeler, model_in, "modeling", mem, errors,
                                      token_budget=token_budget)
        mem.advance_round()

        # Programming
        stm_ctx = self._get_stm_context(mem, compressed_only=True)
        prog_in = self._build_prompt(question, stm_ctx, rag_ctx,
                                     {"建模方案": model_out, "求解计划": plan},
                                     agent_role="programmer", inject_skills=True)
        prog_out = self._safe_invoke(self.programmer, prog_in, "programming", mem, errors,
                                     triggered_by="modeling", token_budget=token_budget)

        # Debugging
        debug_out = self._safe_invoke(
            self.code_debugger,
            self._build_prompt(question, self._get_stm_context(mem, compressed_only=True), "",
                               {"编程输出": prog_out[:4000]},
                               agent_role="code_debugger", inject_skills=True),
            "code_debugger", mem, errors, triggered_by="programming", token_budget=token_budget,
        )
        mem.advance_round()

        # Writing
        stm_ctx = self._get_stm_context(mem, compressed_only=True)
        write_in = self._build_prompt(question, stm_ctx, rag_ctx, {
            "建模方案": model_out, "编程方案": prog_out,
            "代码审查": debug_out, "求解计划": plan,
        }, agent_role="writer", inject_skills=True)
        write_out = self._safe_invoke(self.writer, write_in, "writing", mem, errors,
                                      triggered_by="code_debugger", token_budget=token_budget)
        mem.advance_round()

        # ── Phase 2: SYNTHESIZE ─────────────────────────────────────
        stm_ctx = self._get_stm_context(mem, compressed_only=True)
        synth_in = self._build_prompt(question, stm_ctx, "", {
            "建模方案": model_out, "编程方案": prog_out,
            "写作方案": write_out, "求解计划": plan,
        }, agent_role="synthesizer", inject_skills=True)
        synth_out = self._safe_invoke(self.synthesizer, synth_in, "synthesizer", mem, errors,
                                      triggered_by="writing", token_budget=token_budget)

        self._maybe_archive(question, synth_out)
        self._reset_conditions(active_conditions)

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
                                      {"数据预处理结果": data_out} if data_ctx else None,
                                      agent_role="modeler", inject_skills=True)
        model_out = self._safe_invoke(self.modeler, model_in, "modeling", mem, errors,
                                      token_budget=token_budget)
        mem.advance_round()

        stm_ctx = self._get_stm_context(mem, compressed_only=True)
        prog_in = self._build_prompt(question, stm_ctx, rag_ctx, {"建模方案": model_out},
                                     agent_role="programmer", inject_skills=True)
        prog_out = self._safe_invoke(self.programmer, prog_in, "programming", mem, errors,
                                     triggered_by="modeling", token_budget=token_budget)

        debug_out = self._safe_invoke(
            self.code_debugger,
            self._build_prompt(question, self._get_stm_context(mem, compressed_only=True), "",
                               {"编程输出": prog_out[:4000]},
                               agent_role="code_debugger", inject_skills=True),
            "code_debugger", mem, errors, triggered_by="programming", token_budget=token_budget,
        )
        mem.advance_round()

        stm_ctx = self._get_stm_context(mem, compressed_only=True)
        write_in = self._build_prompt(question, stm_ctx, rag_ctx, {
            "建模方案": model_out, "编程方案": prog_out, "代码审查": debug_out,
        }, agent_role="writer", inject_skills=True)
        write_out = self._safe_invoke(self.writer, write_in, "writing", mem, errors,
                                      triggered_by="code_debugger", token_budget=token_budget)
        mem.advance_round()

        stm_ctx = self._get_stm_context(mem, compressed_only=True)
        synth_in = self._build_prompt(question, stm_ctx, "", {
            "建模方案": model_out, "编程方案": prog_out, "写作方案": write_out,
        }, agent_role="synthesizer", inject_skills=True)
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
                                      {"数据预处理结果": data_out} if data_ctx else None,
                                      agent_role="modeler", inject_skills=True)
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
            refine_prompt = self._build_prompt(question, self._get_stm_context(mem, compressed_only=True), rag_ctx, {
                "你的上一版输出": model_out, "评审反馈": review,
            }, agent_role="modeler", inject_skills=True)
            model_out = self._safe_invoke(self.modeler, refine_prompt, "modeling", mem, errors,
                                          triggered_by="reviewer(modeling)", token_budget=token_budget)
            model_review = review
        mem.advance_round()

        # --- 编程 + 评审循环 ---
        stm_ctx = self._get_stm_context(mem, compressed_only=True)
        prog_in = self._build_prompt(question, stm_ctx, rag_ctx, {"建模方案": model_out},
                                     agent_role="programmer", inject_skills=True)
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
            refine_prompt = self._build_prompt(question, self._get_stm_context(mem, compressed_only=True), rag_ctx, {
                "建模方案": model_out, "你的上一版输出": prog_out, "评审反馈": review,
            }, agent_role="programmer", inject_skills=True)
            prog_out = self._safe_invoke(self.programmer, refine_prompt, "programming", mem, errors,
                                         triggered_by="reviewer(programming)", token_budget=token_budget)
            prog_review = review

        debug_out = self._safe_invoke(
            self.code_debugger,
            self._build_prompt(question, self._get_stm_context(mem, compressed_only=True), "",
                               {"编程输出（已评审修改）": prog_out[:4000]},
                               agent_role="code_debugger", inject_skills=True),
            "code_debugger", mem, errors, triggered_by="programming", token_budget=token_budget,
        )
        mem.advance_round()

        # --- 写作 + 评审循环 ---
        stm_ctx = self._get_stm_context(mem, compressed_only=True)
        write_in = self._build_prompt(question, stm_ctx, rag_ctx, {
            "建模方案": model_out, "编程方案": prog_out, "代码审查": debug_out,
        }, agent_role="writer", inject_skills=True)
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
            refine_prompt = self._build_prompt(question, self._get_stm_context(mem, compressed_only=True), rag_ctx, {
                "建模方案": model_out, "编程方案": prog_out,
                "你的上一版输出": write_out, "评审反馈": review,
            }, agent_role="writer", inject_skills=True)
            write_out = self._safe_invoke(self.writer, refine_prompt, "writing", mem, errors,
                                          triggered_by="reviewer(writing)", token_budget=token_budget)
            write_review = review
        mem.advance_round()

        # --- 总控整合 ---
        stm_ctx = self._get_stm_context(mem, compressed_only=True)
        synth_in = self._build_prompt(question, stm_ctx, "", {
            "建模方案（已评审）": model_out,
            "编程方案（已评审）": prog_out,
            "写作方案（已评审）": write_out,
        }, agent_role="synthesizer", inject_skills=True)
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
                                      {"数据预处理结果": data_out} if data_ctx else None,
                                      agent_role="modeler", inject_skills=True)
        model_out = self._safe_invoke(self.modeler, model_in, "modeling", mem, errors,
                                      token_budget=token_budget)

        stm_ctx = self._get_stm_context(mem, compressed_only=True)

        def run_programmer() -> str:
            return self.programmer.stream(
                self._build_prompt(question, stm_ctx, rag_ctx, {"建模方案": model_out})
            )

        def run_writer() -> str:
            return self.writer.stream(
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
            self._build_prompt(question, self._get_stm_context(mem, compressed_only=True), "",
                               {"编程输出": prog_out[:4000]}),
            "code_debugger", mem, errors, triggered_by="programming", token_budget=token_budget,
        )
        mem.advance_round()

        stm_ctx = self._get_stm_context(mem, compressed_only=True)
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
        on_modeling_thinking: Callable[[str], None] | None = None,
        on_programming_thinking: Callable[[str], None] | None = None,
        on_writing_thinking: Callable[[str], None] | None = None,
        on_synthesis_thinking: Callable[[str], None] | None = None,
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
                                      {"数据预处理结果": data_out} if data_ctx else None,
                                      agent_role="modeler", inject_skills=True)
        model_out = self._safe_stream(self.modeler, model_in, "modeling", mem, errors,
                                      token_budget=token_budget, on_token=on_modeling_token,
                                      on_thinking=on_modeling_thinking)

        stm_ctx = self._get_stm_context(mem, compressed_only=True)
        prog_in = self._build_prompt(question, stm_ctx, rag_ctx, {"建模方案": model_out},
                                     agent_role="programmer", inject_skills=True)
        prog_out = self._safe_stream(self.programmer, prog_in, "programming", mem, errors,
                                     triggered_by="modeling", token_budget=token_budget,
                                     on_token=on_programming_token,
                                     on_thinking=on_programming_thinking)

        stm_ctx = self._get_stm_context(mem, compressed_only=True)
        write_in = self._build_prompt(question, stm_ctx, rag_ctx, {
            "建模方案": model_out, "编程方案": prog_out,
        }, agent_role="writer", inject_skills=True)
        write_out = self._safe_stream(self.writer, write_in, "writing", mem, errors,
                                      triggered_by="programming", token_budget=token_budget,
                                      on_token=on_writing_token,
                                      on_thinking=on_writing_thinking)

        stm_ctx = self._get_stm_context(mem, compressed_only=True)
        synth_in = self._build_prompt(question, stm_ctx, "", {
            "建模方案": model_out, "编程方案": prog_out, "写作方案": write_out,
        }, agent_role="synthesizer", inject_skills=True)
        synth_out = self._safe_stream(self.synthesizer, synth_in, "synthesizer", mem, errors,
                                      triggered_by="writing", token_budget=token_budget,
                                      on_token=on_synthesis_token,
                                      on_thinking=on_synthesis_thinking)

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
    # 流式变体（review / parallel）
    # ═════════════════════════════════════════════════════════════════

    def solve_with_review_stream(
        self,
        question: str,
        top_k: int = 6,
        max_review_rounds: int = 1,
        on_modeling_token: Callable[[str], None] | None = None,
        on_programming_token: Callable[[str], None] | None = None,
        on_writing_token: Callable[[str], None] | None = None,
        on_synthesis_token: Callable[[str], None] | None = None,
        enable_data_engineer: bool = False,
        conditions: list[BaseCondition] | None = None,
    ) -> WorkflowResult:
        """solve_with_review 的流式版本：主阶段输出 token 实时推送。"""
        mem = self._get_stm()
        rag_ctx = self._rag_context(question, top_k)
        errors: list[str] = []
        token_budget = TokenBudgetCondition(max_total_tokens=200000)
        timeout = TimeoutCondition(timeout_seconds=600.0)
        timeout.start()
        started_at = time_module.monotonic()

        active_conditions: list[BaseCondition] = [
            MaxRoundCondition(max_review_rounds), token_budget, timeout,
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

        # 建模 + 评审循环
        model_in = self._build_prompt(question, "", rag_ctx,
                                      {"数据预处理结果": data_out} if data_ctx else None,
                                      agent_role="modeler", inject_skills=True)
        model_out = self._safe_stream(self.modeler, model_in, "modeling", mem, errors,
                                      token_budget=token_budget, on_token=on_modeling_token)
        model_review = ""
        for rnd in range(max_review_rounds):
            stop_reason = self._check_conditions(active_conditions, mem, rnd, timeout.elapsed)
            if stop_reason:
                break
            review = self.reviewer.review("建模智能体", model_out, question)
            self._post(mem, "reviewer(modeling)", review, triggered_by="modeling")
            if rnd > 0 and not self._review_needs_revision(review, "建模"):
                break
            refine_prompt = self._build_prompt(question, self._get_stm_context(mem, compressed_only=True), rag_ctx, {
                "你的上一版输出": model_out, "评审反馈": review,
            })
            model_out = self._safe_stream(self.modeler, refine_prompt, "modeling", mem, errors,
                                          triggered_by="reviewer(modeling)",
                                          token_budget=token_budget, on_token=on_modeling_token)
            model_review = review
        mem.advance_round()

        # 编程 + 评审循环
        stm_ctx = self._get_stm_context(mem, compressed_only=True)
        prog_in = self._build_prompt(question, stm_ctx, rag_ctx, {"建模方案": model_out})
        prog_out = self._safe_stream(self.programmer, prog_in, "programming", mem, errors,
                                     triggered_by="modeling", token_budget=token_budget,
                                     on_token=on_programming_token)
        prog_review = ""
        for rnd in range(max_review_rounds):
            stop_reason = self._check_conditions(active_conditions, mem, rnd, timeout.elapsed)
            if stop_reason:
                break
            review = self.reviewer.review("编程智能体", prog_out, question)
            self._post(mem, "reviewer(programming)", review, triggered_by="programming")
            if rnd > 0 and not self._review_needs_revision(review, "编程"):
                break
            refine_prompt = self._build_prompt(question, self._get_stm_context(mem, compressed_only=True), rag_ctx, {
                "建模方案": model_out, "你的上一版输出": prog_out, "评审反馈": review,
            })
            prog_out = self._safe_stream(self.programmer, refine_prompt, "programming", mem, errors,
                                         triggered_by="reviewer(programming)",
                                         token_budget=token_budget, on_token=on_programming_token)
            prog_review = review

        debug_out = self._safe_invoke(
            self.code_debugger,
            self._build_prompt(question, self._get_stm_context(mem, compressed_only=True), "",
                               {"编程输出（已评审修改）": prog_out[:4000]}),
            "code_debugger", mem, errors, triggered_by="programming", token_budget=token_budget,
        )
        mem.advance_round()

        # 写作 + 评审循环
        stm_ctx = self._get_stm_context(mem, compressed_only=True)
        write_in = self._build_prompt(question, stm_ctx, rag_ctx, {
            "建模方案": model_out, "编程方案": prog_out, "代码审查": debug_out,
        })
        write_out = self._safe_stream(self.writer, write_in, "writing", mem, errors,
                                      triggered_by="code_debugger", token_budget=token_budget,
                                      on_token=on_writing_token)
        write_review = ""
        for rnd in range(max_review_rounds):
            stop_reason = self._check_conditions(active_conditions, mem, rnd, timeout.elapsed)
            if stop_reason:
                break
            review = self.reviewer.review("写作智能体", write_out, question)
            self._post(mem, "reviewer(writing)", review, triggered_by="writing")
            if rnd > 0 and not self._review_needs_revision(review, "写作"):
                break
            refine_prompt = self._build_prompt(question, self._get_stm_context(mem, compressed_only=True), rag_ctx, {
                "建模方案": model_out, "编程方案": prog_out,
                "你的上一版输出": write_out, "评审反馈": review,
            })
            write_out = self._safe_stream(self.writer, refine_prompt, "writing", mem, errors,
                                          triggered_by="reviewer(writing)",
                                          token_budget=token_budget, on_token=on_writing_token)
            write_review = review
        mem.advance_round()

        # 总控整合
        stm_ctx = self._get_stm_context(mem, compressed_only=True)
        synth_in = self._build_prompt(question, stm_ctx, "", {
            "建模方案（已评审）": model_out,
            "编程方案（已评审）": prog_out,
            "写作方案（已评审）": write_out,
        })
        synth_out = self._safe_stream(self.synthesizer, synth_in, "synthesizer", mem, errors,
                                      triggered_by="writing", token_budget=token_budget,
                                      on_token=on_synthesis_token)

        self._maybe_archive(question, synth_out)
        self._reset_conditions(active_conditions)

        return WorkflowResult(
            question=question,
            modeling=StageResult("建模智能体", model_out, model_review, mem.round_idx),
            programming=StageResult("编程智能体", prog_out, prog_review, mem.round_idx),
            writing=StageResult("写作智能体", write_out, write_review, mem.round_idx),
            synthesis=synth_out, memory=mem, errors=errors,
            total_prompt_tokens=token_budget.accumulated, total_completion_tokens=0,
            elapsed_seconds=time_module.monotonic() - started_at,
        )

    def solve_parallel_stream(
        self,
        question: str,
        top_k: int = 6,
        on_modeling_token: Callable[[str], None] | None = None,
        on_programming_token: Callable[[str], None] | None = None,
        on_writing_token: Callable[[str], None] | None = None,
        on_synthesis_token: Callable[[str], None] | None = None,
        enable_data_engineer: bool = False,
    ) -> WorkflowResult:
        """solve_parallel 的流式版本：建模 → 编程/写作并行流式 → 总控整合流式。"""
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
                                      {"数据预处理结果": data_out} if data_ctx else None,
                                      agent_role="modeler", inject_skills=True)
        model_out = self._safe_stream(self.modeler, model_in, "modeling", mem, errors,
                                      token_budget=token_budget, on_token=on_modeling_token)
        stm_ctx = self._get_stm_context(mem, compressed_only=True)

        def run_programmer_stream():
            return self.programmer.stream(
                self._build_prompt(question, stm_ctx, rag_ctx, {"建模方案": model_out}),
                on_token=on_programming_token,
            )

        def run_writer_stream():
            return self.writer.stream(
                self._build_prompt(question, stm_ctx, rag_ctx, {"建模方案": model_out}),
                on_token=on_writing_token,
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            pf = executor.submit(run_programmer_stream)
            wf = executor.submit(run_writer_stream)
            try:
                prog_out = pf.result()
            except Exception as exc:
                prog_out = f"[编程智能体 执行失败: {exc}]"
                errors.append(f"[programming] {exc}")
            try:
                write_out = wf.result()
            except Exception as exc:
                write_out = f"[写作智能体 执行失败: {exc}]"
                errors.append(f"[writing] {exc}")

        self._post(mem, "programming", prog_out, triggered_by="modeling")
        self._post(mem, "writing", write_out, triggered_by="modeling")

        debug_out = self._safe_invoke(
            self.code_debugger,
            self._build_prompt(question, self._get_stm_context(mem, compressed_only=True), "",
                               {"编程输出": prog_out[:4000]}),
            "code_debugger", mem, errors, triggered_by="programming", token_budget=token_budget,
        )
        mem.advance_round()

        stm_ctx = self._get_stm_context(mem, compressed_only=True)
        synth_in = self._build_prompt(question, stm_ctx, "", {
            "建模方案": model_out, "编程方案": prog_out,
            "代码审查": debug_out, "写作方案": write_out,
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
            synthesis=synth_out, memory=mem, errors=errors,
            total_prompt_tokens=token_budget.accumulated, total_completion_tokens=0,
            elapsed_seconds=time_module.monotonic() - started_at,
        )

    # ═════════════════════════════════════════════════════════════════
    # 策略五：动态 Agentic 循环 — 协调者自主决策每一步
    # ═════════════════════════════════════════════════════════════════

    def solve_explore(
        self,
        question: str,
        top_k: int = 6,
        memory: SharedMemory | None = None,
        enable_data_engineer: bool = False,
        conditions: list[BaseCondition] | None = None,
    ) -> WorkflowResult:
        """Exploration-first strategy — orchestrator 自主决策探索策略。

        与之前的手动探索不同，此策略自动执行：
        Phase 1 - Auto Explore: 编排器自动判断需要什么信息，并发派生
          explore + research 子智能体去获取。无需人工指定探索步骤。
        Phase 2 - Synthesize: 整合所有发现为结构化报告。
        Phase 3 - Solve: 各阶段智能体基于富上下文自主选择最合适的模型/方法。

        这模拟了 Claude Code 的自主探索模式：agent 看到问题 → 自己判断
        需要查什么 → 并行搜索 → 合成结果 → 解决问题。
        """
        mem = self._get_stm(memory)
        rag_ctx = self._rag_context(question, top_k)
        errors: list[str] = []
        token_budget = TokenBudgetCondition(max_total_tokens=200000)
        timeout = TimeoutCondition(timeout_seconds=600.0)
        timeout.start()
        started_at = time_module.monotonic()

        active_conditions: list[BaseCondition] = [
            TokenBudgetCondition(max_total_tokens=200000),
            timeout,
        ]
        if conditions:
            active_conditions.extend(conditions)

        # ── Phase 0: Meta-decision — 编排器分析问题，决定探索策略 ──
        logger.info("[Explore] 分析问题，决定探索策略...")

        analysis_prompt = f"""分析以下建模问题，决定需要什么信息才能解决它。
只做分析，不求解。

问题：{question}

判断以下每项是否需要（回答"需要"或"不需要"）：
1. 项目文件探索（已有代码/数据？）：
2. 网络文献调研（最新方法/论文？）：
3. 领域专业知识加载（特定模型理论？）：

然后用一句话说明探索重点。"""

        analysis = self._safe_invoke(
            self.synthesizer, analysis_prompt, "meta_planner", mem, errors,
            triggered_by="", token_budget=token_budget,
        )
        need_explore = "需要" in analysis.split("1.")[-1].split("2.")[0] if "1." in analysis else True
        need_research = "需要" in analysis.split("2.")[-1].split("3.")[0] if "2." in analysis else True

        # ── Phase 1: Autonomous parallel exploration ─────────────────
        logger.info("[Explore] 开始自主并行探索...")

        from .subagent import _run_subagent, SUBAGENT_TYPES

        # 1a. Resolve skills (always needed)
        exploration_skills = resolve_agent_skills(
            question, "synthesizer", skill_registry=self.skill_registry,
        )

        # 1b. Prepare subagent tasks based on meta-analysis
        subagent_tasks: list[tuple[str, str]] = []

        if need_explore:
            explore_task = f"""探索项目中与以下问题相关的代码、数据和文件：
"{question}"

请搜索：
- 项目中是否有与问题主题相关的 .py 文件或数据文件
- agent_app/ 和项目根目录中是否有可复用的建模代码或工具
- output/ 目录中是否有之前的求解结果或生成文件
- 项目中 .md 文档中的相关记录

用 search_files, search_content, read_file 来探索。
报告你找到了什么和没找到什么。控制在 3000 字符内。"""
            subagent_tasks.append(("explore", explore_task))

        if need_research:
            research_task = f"""为以下数学建模问题搜索参考资料：
"{question}"

请执行以下搜索：
1. 用 web_search 搜索该问题的标准建模方法和最新解法
2. 用 search_arxiv 或 search_semantic_scholar 搜索相关学术论文
3. 如果搜索到关键资料，用 web_fetch 查看详情

报告关键发现：推荐的方法、参考实现、注意事项。控制在 5000 字符内。"""
            subagent_tasks.append(("research", research_task))

        # 1c. Run subagents in parallel (like Claude Code's Agent tool)
        explore_report = ""
        research_report = ""

        if subagent_tasks:
            llm = self.synthesizer.llm  # Use the same LLM instance
            from .subagent import spawn_parallel
            results = spawn_parallel(subagent_tasks, llm)

            idx = 0
            if need_explore:
                explore_report = results[idx]
                idx += 1
            if need_research:
                research_report = results[idx]

        # Record LTM context
        ltm_context = (
            self.memory.recall(question, top_k=5)
            if self.memory else "暂无长期记忆。"
        )

        # ── Phase 2: Synthesize exploration findings ─────────────────
        logger.info("[Explore] 整合探索发现...")

        synthesis_prompt = self._build_prompt(
            question,
            "", "",
            {
                "项目文件探索结果": explore_report or "（跳过）",
                "网络文献调研结果": research_report or "（跳过）",
                "RAG论文检索": rag_ctx,
                "长期记忆": ltm_context,
                "领域专业知识": exploration_skills,
            },
            agent_role="synthesizer", inject_skills=True,
        )

        synthesis_result = self._safe_invoke(
            self.synthesizer,
            synthesis_prompt + "\n\n请将以上所有探索发现整合为一份结构化的「探索报告」，包含：\n"
            "## 探索报告\n"
            "### 1. 问题核心与难点\n"
            "### 2. 推荐模型与理由（基于找到的资料）\n"
            "### 3. 项目中的可复用资源\n"
            "### 4. 外部参考文献\n"
            "### 5. 求解策略建议",
            "explorer", mem, errors,
            triggered_by="subagents", token_budget=token_budget,
        )

        # ── Phase 3: Autonomous solving ──────────────────────────────
        logger.info("[Explore] 基于探索结果自主求解...")

        data_ctx, data_out = "", ""
        if enable_data_engineer:
            data_out = self._safe_invoke(
                self.data_engineer,
                self._build_prompt(question, "", rag_ctx,
                                   {"探索报告": synthesis_result} if not data_ctx else {"探索报告": synthesis_result, "数据预处理结果": data_out},
                                   agent_role="data_engineer", inject_skills=True),
                "data_engineer", mem, errors, token_budget=token_budget,
            )
            data_ctx = f"\n\n数据预处理结果：\n{data_out}"

        extra = {"探索报告": synthesis_result}
        if data_ctx:
            extra["数据预处理结果"] = data_out
        model_in = self._build_prompt(question, "", rag_ctx, extra,
                                      agent_role="modeler", inject_skills=True)
        model_out = self._safe_invoke(self.modeler, model_in, "modeling", mem, errors,
                                      token_budget=token_budget)
        mem.advance_round()

        stm_ctx = self._get_stm_context(mem, compressed_only=True)
        prog_in = self._build_prompt(question, stm_ctx, rag_ctx,
                                     {"建模方案": model_out, "探索报告": synthesis_result},
                                     agent_role="programmer", inject_skills=True)
        prog_out = self._safe_invoke(self.programmer, prog_in, "programming", mem, errors,
                                     triggered_by="modeling", token_budget=token_budget)

        debug_out = self._safe_invoke(
            self.code_debugger,
            self._build_prompt(question, self._get_stm_context(mem, compressed_only=True), "",
                               {"编程输出": prog_out[:4000]},
                               agent_role="code_debugger", inject_skills=True),
            "code_debugger", mem, errors, triggered_by="programming", token_budget=token_budget,
        )
        mem.advance_round()

        stm_ctx = self._get_stm_context(mem, compressed_only=True)
        write_in = self._build_prompt(question, stm_ctx, rag_ctx, {
            "建模方案": model_out, "编程方案": prog_out,
            "代码审查": debug_out, "探索报告": synthesis_result,
        }, agent_role="writer", inject_skills=True)
        write_out = self._safe_invoke(self.writer, write_in, "writing", mem, errors,
                                      triggered_by="code_debugger", token_budget=token_budget)
        mem.advance_round()

        stm_ctx = self._get_stm_context(mem, compressed_only=True)
        synth_in = self._build_prompt(question, stm_ctx, "", {
            "建模方案": model_out, "编程方案": prog_out,
            "写作方案": write_out, "探索报告": synthesis_result,
        }, agent_role="synthesizer", inject_skills=True)
        synth_out = self._safe_invoke(self.synthesizer, synth_in, "synthesizer", mem, errors,
                                      triggered_by="writing", token_budget=token_budget)

        self._maybe_archive(question, synth_out)
        self._reset_conditions(active_conditions)

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
