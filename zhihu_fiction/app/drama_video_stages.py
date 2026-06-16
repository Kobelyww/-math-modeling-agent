"""Short-drama production stage definitions."""
from __future__ import annotations

from fastapi import HTTPException

STAGE_LABELS = {
    "script": "剧本",
    "style": "风格设计",
    "plot": "剧情设计",
    "character_refs": "人物参考图",
    "storyboard": "分镜",
    "video": "视频生成",
}

DEEPAGENT_STAGES = ("script", "style", "plot", "character_refs", "storyboard")

TEXT_STAGE_INSTRUCTIONS = {
    "script": (
        "把小说转化为短剧剧本。输出集数规划、场次、主要对白、冲突推进、"
        "每集开场钩子和结尾悬念。"
    ),
    "style": (
        "完成短剧风格设计。输出视觉基调、色彩、灯光、服化道、镜头语言、"
        "角色和场景一致性规则、负面风格约束。"
    ),
    "plot": (
        "完成剧情设计。输出每集节奏、反转点、情绪曲线、爽点、信息揭露顺序、"
        "适合短视频观看的压缩策略。"
    ),
    "character_refs": (
        "生成人物参考图设计。输出主角和重要配角的外貌、年龄、服装、气质、"
        "表情范围、参考图 Prompt 和一致性 Prompt。"
    ),
    "storyboard": (
        "生成分镜方案。输出镜头编号、场景、人物、动作、对白、情绪、镜头运动、"
        "时长和视频生成 Prompt。"
    ),
}


def parse_shot_limit(value) -> int:
    try:
        limit = int(value)
    except (TypeError, ValueError):
        limit = 1
    return max(1, min(limit, 20))


def parse_stage_drafts(value) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}

    drafts: dict[str, str] = {}
    for stage_id in STAGE_LABELS:
        raw = value.get(stage_id)
        if not isinstance(raw, str):
            continue
        text = raw.strip()
        if text:
            drafts[stage_id] = text[:12000]
    return drafts


def next_unconfirmed_stage(spec: dict) -> str | None:
    confirmed = set(spec.get("confirmed_stages") or [])
    for stage in DEEPAGENT_STAGES:
        if stage not in confirmed:
            return stage
    return None


def assert_previous_stages_confirmed(spec: dict, stage: str) -> None:
    confirmed = set(spec.get("confirmed_stages") or [])
    stage_index = DEEPAGENT_STAGES.index(stage)
    missing = [item for item in DEEPAGENT_STAGES[:stage_index] if item not in confirmed]
    if missing:
        raise HTTPException(409, f"请先确认{STAGE_LABELS[missing[0]]}")
