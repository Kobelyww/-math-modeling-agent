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
    chapter_index: int = 1,
    total_chapters: int = 1,
    existing_story: str = "",
) -> WorkflowResult:
    """Run the Coordinator DeepAgent.

    Args:
        stream_callback: SSE event callback
        chapter_index: Current chapter (1-based)
        total_chapters: Total planned chapters
        existing_story: Previous chapters content (continuation mode)
    """
    feedback_section = ""
    if revision_feedback:
        feedback_section = f"\n\n【修改要求】上一轮评审未达标，请根据以下反馈重新创作：\n{revision_feedback}"

    chapter_info = ""
    if total_chapters > 1:
        chapter_info = (
            f"\n\n【章节信息】\n这是第 {chapter_index}/{total_chapters} 章。\n"
            + (f"已有前文：\n{existing_story[-2000:]}\n" if existing_story else "")
            + "请调用 write_draft(chapter_index={0}, total_chapters={1}) 创作本章。".format(chapter_index, total_chapters)
        )
    elif existing_story:
        chapter_info = f"\n\n【续写模式】已有前文，请续写下一章：\n{existing_story[-2000:]}\n"

    prompt = f"""请创作一篇关于以下主题的知乎爆款小说：{topic}

当前知乎热榜趋势参考：
{hot_trends or '暂无热榜数据，请根据你的知识判断选题方向'}

请按照标准工作流程完成创作：选题分析 → 大纲规划 → 初稿创作 → 润色优化 → 发布方案整合。
最终用【小说正文】和【发布方案】两个标记分别输出。{chapter_info}{feedback_section}"""

    resolved_genre = genre or "未指定"
    input_msg = {"messages": [{"role": "user", "content": prompt}]}

    if stream_callback is None:
        result = coordinator.invoke(input_msg)
        messages = result.get("messages", [])
    else:
        # Use stream_mode="values" to get complete state snapshots (not token chunks).
        # stream_mode="messages" returns AIMessageChunk with empty content.
        last_state = None
        for chunk in coordinator.stream(input_msg, stream_mode="values"):
            last_state = chunk
            # Extract tool call events from the latest messages for the frontend
            msgs = chunk.get("messages", []) if isinstance(chunk, dict) else []
            if msgs:
                last_msg = msgs[-1]
                msg_type = (last_msg.get("type", "") if isinstance(last_msg, dict)
                            else getattr(last_msg, "type", ""))
                msg_name = (last_msg.get("name", "") if isinstance(last_msg, dict)
                            else getattr(last_msg, "name", ""))
                content = (last_msg.get("content", "") if isinstance(last_msg, dict)
                           else normalize_content(getattr(last_msg, "content", "") or ""))

                if msg_type == "ai":
                    tc = (last_msg.get("tool_calls", None) if isinstance(last_msg, dict)
                          else getattr(last_msg, "tool_calls", None))
                    if tc:
                        for t in tc:
                            t_name = t.get("name", "") if isinstance(t, dict) else getattr(t, "name", "")
                            t_args = t.get("args", {}) if isinstance(t, dict) else getattr(t, "args", {})
                            stream_callback({"type": "tool_call", "name": t_name, "args": t_args})
                    elif content:
                        stream_callback({"type": "ai_text", "content": content})

                elif msg_type == "tool":
                    stream_callback({"type": "tool_result", "name": msg_name, "content": content})

        messages = last_state.get("messages", []) if last_state else []

    if not messages:
        return WorkflowResult(
            topic=topic, genre=resolved_genre,
            topic_analysis="", outline="", draft="",
            polished="", review="", synthesis="",
        )

    # Debug: dump all message types to help trace the 0-word issue
    import logging
    _log = logging.getLogger(__name__)
    for i, m in enumerate(messages):
        mt = m.get("type", "?") if isinstance(m, dict) else getattr(m, "type", "?")
        mc = (m.get("content", "") if isinstance(m, dict) else getattr(m, "content", "")) or ""
        mc = (mc[:80] + "...") if len(str(mc)) > 80 else str(mc)
        mn = (m.get("name", "") if isinstance(m, dict) else getattr(m, "name", ""))
        extra = f" name={mn}" if mn else ""
        _log.debug("msg[%d] type=%s content=%s%s", i, mt, repr(mc), extra)

    # Reverse-search for the final AI message containing the story markers.
    output = ""
    for msg in reversed(messages):
        content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
        content = normalize_content(content or "")
        if "【小说正文】" in content:
            output = content
            _log.info("Found 【小说正文】 at reversed position")
            break
    if not output:
        for msg in reversed(messages):
            msg_type = msg.get("type", "") if isinstance(msg, dict) else getattr(msg, "type", "")
            if msg_type == "ai":
                content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
                output = normalize_content(content or "")
                if output:
                    _log.info("Fallback to ai message, content_len=%d", len(output))
                    break
    if not output:
        last = messages[-1]
        output = normalize_content(
            (last.get("content", "") if isinstance(last, dict) else getattr(last, "content", "")) or ""
        )
        _log.warning("Last resort — no 【小说正文】 found, using messages[-1]")
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