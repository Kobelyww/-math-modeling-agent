"""Thin wrapper around DeepAgent Coordinator invocation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .agents import create_coordinator, ReviewerAgent
from .base import normalize_content
from .config import Settings
from .llm import create_llm
from .skills_store import SkillsStore


@dataclass
class StageResult:
    role: str
    content: str


@dataclass
class WorkflowResult:
    topic: str
    genre: str
    topic_analysis: str
    outline: str
    draft: str
    polished: str
    review: str
    synthesis: str

    def __post_init__(self) -> None:
        """Normalise StageResult fields to plain strings for backward compatibility."""
        for _field in ("topic_analysis", "outline", "draft"):
            val = getattr(self, _field)
            if isinstance(val, StageResult):
                setattr(self, _field, val.content)

    def format_overview(self) -> str:
        lines = [
            "=" * 60,
            f"  选题：{self.topic}",
            f"  题材：{self.genre}",
            "=" * 60,
            "",
            self.polished,
            "",
            "=" * 60,
            self.synthesis,
        ]
        return "\n".join(lines)

    def format_analysis(self) -> str:
        lines = [
            "=" * 60,
            f"  选题：{self.topic}",
            f"  题材：{self.genre}",
            "=" * 60,
            "",
            "【选题分析】",
            self.topic_analysis[:400] + "..." if len(self.topic_analysis) > 400 else self.topic_analysis,
            "",
            "【故事大纲】",
            self.outline[:400] + "..." if len(self.outline) > 400 else self.outline,
            "",
            "【评审意见】",
            self.review[:400] + "..." if len(self.review) > 400 else self.review,
        ]
        return "\n".join(lines)

    @property
    def final_story(self) -> str:
        return self.polished


def _parse_coordinator_output(output: str) -> dict[str, str]:
    """Parse Coordinator's final output into structured sections.

    Coordinator outputs:
    【小说正文】
    <story>
    【发布方案】
    <publish plan>
    """
    result = {"story": "", "synthesis": ""}

    STORY_MARKER = "【小说正文】"
    SYNTH_MARKER = "【发布方案】"

    story_start = output.find(STORY_MARKER)
    synth_start = output.find(SYNTH_MARKER)

    if story_start >= 0 and synth_start >= 0:
        result["story"] = output[story_start + len(STORY_MARKER):synth_start].strip()
        result["synthesis"] = output[synth_start + len(SYNTH_MARKER):].strip()
    elif story_start >= 0:
        result["story"] = output[story_start + len(STORY_MARKER):].strip()
    else:
        result["story"] = output

    return result


def run_coordinator(
    llm,
    coordinator,
    topic: str,
    hot_trends: str = "",
    genre: str | None = None,
    revision_feedback: str = "",
    stream_callback: callable | None = None,
) -> WorkflowResult:
    """Run the Coordinator DeepAgent to create a fiction from topic.

    Args:
        stream_callback: If provided, called with dict events:
            {"type": "tool_call", "name": str, "args": dict}
            {"type": "tool_result", "name": str, "content": str}
            {"type": "ai_text", "content": str}
    """
    feedback_section = ""
    if revision_feedback:
        feedback_section = f"\n\n【修改要求】上一轮评审未达标，请根据以下反馈重新创作：\n{revision_feedback}"

    prompt = f"""请创作一篇关于以下主题的知乎爆款小说：{topic}

当前知乎热榜趋势参考：
{hot_trends or '暂无热榜数据，请根据你的知识判断选题方向'}

请按照标准工作流程完成创作：选题分析 → 大纲规划 → 初稿创作 → 润色优化 → 发布方案整合。
最终用【小说正文】和【发布方案】两个标记分别输出。{feedback_section}"""

    resolved_genre = genre or "未指定"
    input_msg = {"messages": [{"role": "user", "content": prompt}]}

    if stream_callback is None:
        result = coordinator.invoke(input_msg)
        messages = result.get("messages", [])
    else:
        messages = []
        for chunk in coordinator.stream(input_msg, stream_mode="messages"):
            # chunk can be a message, a (message, metadata) tuple, or a list
            items = chunk if isinstance(chunk, list) else [chunk]
            for msg in items:
                # Normalize: msg can be a LangChain message object or a dict
                if isinstance(msg, (tuple, list)) and len(msg) >= 1:
                    msg = msg[0]  # (message, metadata) tuple → take message

                msg_type = (getattr(msg, "type", "") if not isinstance(msg, dict) else msg.get("type", ""))
                msg_content = (getattr(msg, "content", "") if not isinstance(msg, dict) else msg.get("content", ""))
                msg_name = (getattr(msg, "name", "") if not isinstance(msg, dict) else msg.get("name", ""))
                msg_tool_calls = (getattr(msg, "tool_calls", None) if not isinstance(msg, dict) else msg.get("tool_calls"))

                content_str = normalize_content(msg_content or "")

                if msg_type == "ai":
                    if msg_tool_calls:
                        for tc in msg_tool_calls:
                            tc_name = tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "")
                            tc_args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
                            stream_callback({"type": "tool_call", "name": tc_name, "args": tc_args})
                    elif content_str:
                        stream_callback({"type": "ai_text", "content": content_str})

                elif msg_type == "tool":
                    stream_callback({"type": "tool_result", "name": msg_name, "content": content_str})

                messages.append(msg)

    if not messages:
        return WorkflowResult(
            topic=topic, genre=resolved_genre,
            topic_analysis="", outline="", draft="",
            polished="", review="", synthesis="",
        )

    # Reverse-search for the final AI message containing the story markers.
    # DeepAgents injects write_todos calls, so messages[-1] is often a
    # tool result, not the final Coordinator summary.
    output = ""
    for msg in reversed(messages):
        content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
        content = normalize_content(content or "")
        if "【小说正文】" in content:
            output = content
            break
    if not output:
        # Fallback: use the last AI-type message
        for msg in reversed(messages):
            msg_type = msg.get("type", "") if isinstance(msg, dict) else getattr(msg, "type", "")
            if msg_type == "ai":
                content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
                output = normalize_content(content or "")
                if output:
                    break
    if not output:
        # Last resort: try the very last message
        last = messages[-1]
        output = normalize_content(
            (last.get("content", "") if isinstance(last, dict) else getattr(last, "content", "")) or ""
        )
    parsed = _parse_coordinator_output(output)

    return WorkflowResult(
        topic=topic, genre=resolved_genre,
        topic_analysis="", outline="", draft="",
        polished=parsed["story"], review="",
        synthesis=parsed["synthesis"],
    )


def create_orchestrator(
    settings: Settings,
    skills_store: SkillsStore | None = None,
    genre: str | None = None,
):
    """Create the Coordinator and ReviewerAgent for the given settings.

    Returns a tuple of (coordinator, reviewer, llm).
    """
    llm = create_llm(settings)
    coordinator = create_coordinator(llm, skills_store=skills_store, genre=genre)
    reviewer = ReviewerAgent(llm)
    return coordinator, reviewer, llm


class OrchestratorCompat:
    """Backward-compatible wrapper so old CLI commands (/create, /fast, etc) keep working.

    Delegates to run_coordinator under the hood.
    """

    def __init__(
        self,
        settings: Settings,
        skills_store: SkillsStore | None = None,
        coordinator=None,
        reviewer=None,
        llm=None,
    ) -> None:
        """Construct the wrapper, creating the internal Coordinator/Reviewer/LLM automatically.

        This signature matches the old ``Orchestrator(settings, skills_store=...)``
        so existing CLI and test code continues to work unchanged.

        When ``coordinator``, ``reviewer``, or ``llm`` are provided they take
        precedence over auto-created instances (used by Pipeline).
        """
        from .llm import create_llm
        from .agents import create_coordinator, ReviewerAgent

        self.settings = settings
        self.skills = skills_store
        self._llm = llm or create_llm(settings)
        self._coordinator = coordinator or create_coordinator(self._llm, skills_store=skills_store)
        self._reviewer = reviewer or ReviewerAgent(self._llm)

    def solve_fast(self, topic: str, genre: str | None = None, memory=None) -> WorkflowResult:
        return run_coordinator(self._llm, self._coordinator, topic=topic, genre=genre)

    def solve_full(self, topic: str, genre: str | None = None, max_review_rounds=2, memory=None) -> WorkflowResult:
        return run_coordinator(self._llm, self._coordinator, topic=topic, genre=genre)

    def solve_polish(self, topic: str, genre: str | None = None, max_review_rounds=2, memory=None) -> WorkflowResult:
        return run_coordinator(self._llm, self._coordinator, topic=topic, genre=genre)

    def solve_stream(
        self,
        topic: str,
        genre: str | None = None,
        on_topic_token=None,
        on_outline_token=None,
        on_draft_token=None,
        on_polish_token=None,
        on_synthesis_token=None,
    ) -> WorkflowResult:
        return run_coordinator(self._llm, self._coordinator, topic=topic, genre=genre)

    def continue_story(
        self,
        existing_story: str,
        topic: str,
        genre: str | None = None,
        chapter_count: int = 1,
    ) -> str:
        prompt = (
            f"创作主题：{topic}\n\n"
            f"已有故事：\n{existing_story}\n\n"
            f"请续写第 {chapter_count + 1} 章，保持文风一致，2000-4000 字，章末留悬念。"
        )
        result = self._coordinator.invoke({
            "messages": [{"role": "user", "content": prompt}],
        })
        return normalize_content(result["messages"][-1].content)


# Backward-compatible alias so ``from .orchestrator import Orchestrator`` still works.
Orchestrator = OrchestratorCompat