"""DeepAgent stage generation service for short-drama production."""
from __future__ import annotations

import inspect
import logging
import re
from dataclasses import replace
from types import SimpleNamespace

from fastapi import HTTPException

from ...core.base import normalize_content
from ...core.llm import create_llm
from ...fiction.orchestrator import create_drama_video_coordinator, run_drama_video_coordinator
from ...ip_memory.rendering import render_memory_context
from ..drama_video_stages import STAGE_LABELS, TEXT_STAGE_INSTRUCTIONS
from .story_library import safe_story_file, story_result_from_file


logger = logging.getLogger(__name__)
_PIPELINE_RUN_ID_RE = re.compile(r"\d{8}_\d{6}")


def deepseek_v4pro_settings(settings):
    if getattr(settings, "model", "") == "deepseek-v4-pro":
        return settings
    try:
        return replace(settings, model="deepseek-v4-pro")
    except TypeError:
        data = dict(getattr(settings, "__dict__", {}))
        data["model"] = "deepseek-v4-pro"
        return SimpleNamespace(**data)


def format_stage_context(stage_drafts: dict[str, str]) -> str:
    sections: list[str] = []
    for stage_id, label in STAGE_LABELS.items():
        if stage_id == "video":
            continue
        draft = stage_drafts.get(stage_id)
        if draft:
            sections.append(f"【{label}已确认稿】\n{draft}")
    return "\n\n".join(sections) if sections else "无"


def format_ip_memory_context(ip_memory) -> str:
    if ip_memory is None:
        return "【IP记忆】\n暂无已保存记忆。"
    return render_memory_context(ip_memory)


def build_stage_prompt(result, stage: str, stage_drafts: dict[str, str], ip_memory=None) -> str:
    label = STAGE_LABELS[stage]
    instruction = TEXT_STAGE_INSTRUCTIONS[stage]
    memory_context = format_ip_memory_context(ip_memory)
    return f"""你是 DeepSeek V4 Pro，负责把知乎/网文小说开发成可生产短剧的视频前置资产。

当前要创作的生产阶段：{label}
阶段任务：{instruction}

要求：
- 只输出当前阶段内容，不要输出寒暄。
- 内容要能直接被短剧制作工作台编辑和确认。
- 保持人物、剧情、风格和前序确认稿一致。
- 如果当前阶段是人物参考图或分镜，请输出可直接给图像/视频模型使用的 Prompt。
- 不要调用视频生成模型。

小说标题：{result.topic}
题材：{result.genre}

前序已确认稿：
{format_stage_context(stage_drafts)}

{memory_context}

发布方案参考：
{result.synthesis or "无"}

小说正文：
{result.final_story}
"""


def memory_project_candidates(story_path: str, story_file, result) -> list[str]:
    candidates: list[str] = []

    def add(value) -> None:
        text = str(value or "").strip()
        if text and text not in candidates:
            candidates.append(text)

    add(story_path)
    add(story_file)
    add(_pipeline_run_id_from_text(story_path))
    add(_pipeline_run_id_from_text(getattr(story_file, "parent", "")))
    add(_pipeline_run_id_from_text(story_file))
    add(getattr(result, "topic", ""))
    return candidates


def _pipeline_run_id_from_text(value) -> str:
    match = _PIPELINE_RUN_ID_RE.search(str(value or ""))
    return match.group(0) if match else ""


def _runner_accepts_memory_context(coordinator_runner) -> bool:
    try:
        signature = inspect.signature(coordinator_runner)
    except (TypeError, ValueError):
        return True
    parameters = signature.parameters
    return "memory_context" in parameters or any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters.values()
    )


def _run_coordinator_compat(coordinator_runner, coordinator, *, memory_context: str, **kwargs):
    if _runner_accepts_memory_context(coordinator_runner):
        kwargs["memory_context"] = memory_context
    return coordinator_runner(coordinator, **kwargs)


def run_stage_deepagent(
    dependencies,
    story_path: str,
    stage: str,
    stage_drafts: dict[str, str],
    *,
    current_draft: str = "",
    human_feedback: str = "",
    compat_attr=lambda name, default=None: default,
) -> dict:
    if stage not in TEXT_STAGE_INSTRUCTIONS:
        raise HTTPException(400, "stage must be one of script, style, plot, character_refs, storyboard")

    story_file = safe_story_file(story_path)
    result = story_result_from_file(story_file)
    ip_memory = None
    ip_memory_repo = getattr(dependencies, "ip_memory_repo", None)
    if ip_memory_repo is not None:
        for project_id in memory_project_candidates(story_path, story_file, result):
            try:
                ip_memory = ip_memory_repo.load(str(project_id))
            except Exception:
                logger.warning("Failed to load IP memory for drama stage generation", exc_info=True)
                ip_memory = None
                break
            if ip_memory is not None:
                break
    memory_context = format_ip_memory_context(ip_memory)
    settings = compat_attr("settings", dependencies.settings)
    llm_settings = deepseek_v4pro_settings(settings)
    llm_factory = compat_attr("create_llm", create_llm)
    coordinator_factory = compat_attr("create_drama_video_coordinator", create_drama_video_coordinator)
    coordinator_runner = compat_attr("run_drama_video_coordinator", run_drama_video_coordinator)
    llm = llm_factory(llm_settings, temperature=0.4)
    coordinator = coordinator_factory(llm, stage)
    output = _run_coordinator_compat(
        coordinator_runner,
        coordinator,
        result=result,
        stage=stage,
        stage_drafts=stage_drafts,
        current_draft=current_draft,
        human_feedback=human_feedback,
        memory_context=memory_context,
    )
    content = normalize_content(output.get("content", "")).strip()
    if not content:
        raise HTTPException(502, "DeepAgent returned empty content")

    return {
        "status": "ok",
        "stage": stage,
        "label": STAGE_LABELS[stage],
        "model": "deepseek-v4-pro",
        "agent": "deepagent",
        "content": content,
        "events": output.get("events", []),
    }
