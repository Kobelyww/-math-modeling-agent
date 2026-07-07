"""Thin wrapper around DeepAgent Coordinator invocation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .agents import create_coordinator, create_drama_video_coordinator, ReviewerAgent
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
    import logging
    _log = logging.getLogger(__name__)
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
        _log.warning("【小说正文】 marker not found — using entire output as story")
        for sep in ("\n# 发布方案", "\n## 发布方案", "\n【发布方案】", "\n---\n"):
            idx = output.find(sep)
            if idx > 500:
                result["story"] = output[:idx].strip()
                result["synthesis"] = output[idx:].strip()
                _log.info("Heuristic split at offset %d using %r", idx, sep)
                break
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
    memory_context: str = "",
) -> WorkflowResult:
    """Run the Coordinator DeepAgent.

    Args:
        stream_callback: SSE event callback
        chapter_index: Current chapter (1-based)
        total_chapters: Total planned chapters
        existing_story: Previous chapters content (continuation mode)
    """
    memory_section = ""
    if memory_context.strip():
        memory_section = (
            "\n\n【创作记忆】\n"
            "以下是本 IP 已沉淀的创作记忆。请严格遵守其中的角色、世界观、"
            "伏笔和风格约束，保持前后连续，不要改写已建立设定。\n"
            f"{memory_context.strip()}"
        )

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

    if revision_feedback:
        prompt = (
            f"【修改任务】请根据以下评审意见修改小说。\n\n"
            f"创作主题：{topic}\n\n"
            f"评审意见：\n{revision_feedback}\n\n"
            f"重要：你只需要针对评审意见修改小说正文，不需要重新做选题分析和大纲规划。"
            f"直接调用 write_draft（传入 revision_feedback）和 polish_draft 即可。"
            f"最终用【小说正文】和【发布方案】两个标记分别输出。{chapter_info}{memory_section}"
        )
    else:
        prompt = (
            f"请创作一篇关于以下主题的知乎爆款小说：{topic}\n\n"
            f"当前知乎热榜趋势参考：\n"
            f"{hot_trends or '暂无热榜数据，请根据你的知识判断选题方向'}\n\n"
            f"请按照标准工作流程完成创作：选题分析 → 大纲规划 → 初稿创作 → 润色优化 → 发布方案整合。\n"
            f"最终用【小说正文】和【发布方案】两个标记分别输出。{chapter_info}{feedback_section}{memory_section}"
        )

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


def _format_drama_video_stage_context(stage_drafts: dict[str, str]) -> str:
    labels = {
        "script": "剧本",
        "style": "风格设计",
        "plot": "剧情设计",
        "character_refs": "人物参考图",
        "storyboard": "分镜",
    }
    sections: list[str] = []
    for stage_id, label in labels.items():
        draft = stage_drafts.get(stage_id)
        if draft:
            sections.append(f"【{label}已确认稿】\n{draft}")
    return "\n\n".join(sections)


def _parse_drama_video_stage_output(output: str) -> str:
    marker = "【阶段草稿】"
    if marker in output:
        return output.split(marker, 1)[1].strip()
    return output.strip()


def run_drama_video_coordinator(
    coordinator,
    *,
    result: WorkflowResult,
    stage: str,
    stage_drafts: dict[str, str],
    current_draft: str = "",
    human_feedback: str = "",
    memory_context: str = "",
    stream_callback: callable | None = None,
) -> dict[str, Any]:
    """Run the drama-video DeepAgent Coordinator for one confirmed stage."""
    stage_labels = {
        "script": "剧本",
        "style": "风格设计",
        "plot": "剧情设计",
        "character_refs": "人物参考图",
        "storyboard": "分镜",
    }
    tool_names = {
        "script": "write_drama_script",
        "style": "design_drama_style",
        "plot": "design_drama_plot",
        "character_refs": "generate_character_refs",
        "storyboard": "build_storyboard",
    }
    if stage not in stage_labels:
        raise ValueError("stage must be one of script, style, plot, character_refs, storyboard")

    label = stage_labels[stage]
    revision_section = ""
    if current_draft or human_feedback:
        revision_section = (
            "\n\n【Human Loop 调整】\n"
            f"当前阶段草稿：\n{current_draft or '无'}\n\n"
            f"人类反馈：\n{human_feedback or '无'}\n\n"
            "请保留已确认方向，只针对人类反馈重写当前阶段草稿。"
        )

    prompt = (
        f"请完成短剧视频生产阶段：{label}\n\n"
        f"请调用 {tool_names[stage]} 工具，参数包含：\n"
        f"- story_title: {result.topic}\n"
        f"- genre: {result.genre}\n"
        f"- story: 小说正文\n"
        f"- confirmed_context: 前序已确认稿\n"
        f"- publishing_reference: 发布方案参考\n\n"
        "工具返回后，请整合为最终阶段草稿，并使用【阶段草稿】标记输出。\n\n"
        f"小说正文：\n{result.final_story}\n\n"
        f"前序已确认稿：\n{_format_drama_video_stage_context(stage_drafts) or '无'}\n\n"
        f"统一IP记忆：\n{memory_context.strip() or '暂无'}\n\n"
        f"发布方案参考：\n{result.synthesis or '无'}"
        f"{revision_section}"
    )
    input_msg = {"messages": [{"role": "user", "content": prompt}]}
    events: list[dict[str, Any]] = []

    if stream_callback is None:
        state = coordinator.invoke(input_msg)
        messages = state.get("messages", []) if isinstance(state, dict) else []
    else:
        last_state = None
        for chunk in coordinator.stream(input_msg, stream_mode="values"):
            last_state = chunk
            msgs = chunk.get("messages", []) if isinstance(chunk, dict) else []
            if not msgs:
                continue
            last_msg = msgs[-1]
            msg_type = (last_msg.get("type", "") if isinstance(last_msg, dict)
                        else getattr(last_msg, "type", ""))
            msg_name = (last_msg.get("name", "") if isinstance(last_msg, dict)
                        else getattr(last_msg, "name", ""))
            content = (last_msg.get("content", "") if isinstance(last_msg, dict)
                       else normalize_content(getattr(last_msg, "content", "") or ""))
            if msg_type == "ai":
                tool_calls = (last_msg.get("tool_calls", None) if isinstance(last_msg, dict)
                              else getattr(last_msg, "tool_calls", None))
                if tool_calls:
                    for tool_call in tool_calls:
                        name = tool_call.get("name", "") if isinstance(tool_call, dict) else getattr(tool_call, "name", "")
                        args = tool_call.get("args", {}) if isinstance(tool_call, dict) else getattr(tool_call, "args", {})
                        event = {"type": "tool_call", "name": name, "args": args}
                        events.append(event)
                        stream_callback(event)
                elif content:
                    event = {"type": "ai_text", "content": content}
                    events.append(event)
                    stream_callback(event)
            elif msg_type == "tool":
                event = {"type": "tool_result", "name": msg_name, "content": content}
                events.append(event)
                stream_callback(event)
        messages = last_state.get("messages", []) if last_state else []

    output = ""
    for msg in reversed(messages):
        content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
        content = normalize_content(content or "")
        if "【阶段草稿】" in content:
            output = content
            break
    if not output:
        for msg in reversed(messages):
            msg_type = msg.get("type", "") if isinstance(msg, dict) else getattr(msg, "type", "")
            if msg_type == "ai":
                output = normalize_content(
                    (msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")) or ""
                )
                if output:
                    break
    return {"content": _parse_drama_video_stage_output(output), "events": events}


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
