"""Normalize short-drama stage drafts into structured assets."""
from __future__ import annotations

import re
from typing import Any


STAGE_QUALITY_RULES = {
    "script": {
        "label": "剧本",
        "min_chars": 120,
        "required_any": (
            ("集数规划", "第一集", "第1集", "场次", "场景"),
            ("对白", "台词"),
            ("冲突", "钩子", "悬念"),
        ),
    },
    "style": {
        "label": "风格设计",
        "min_chars": 90,
        "required_any": (
            ("视觉", "视觉基调", "色彩"),
            ("灯光", "镜头语言", "镜头"),
            ("一致性", "负面约束", "服化道"),
        ),
    },
    "plot": {
        "label": "剧情设计",
        "min_chars": 140,
        "required_any": (
            ("每集", "第一集", "第1集", "集数"),
            ("反转", "冲突", "信息揭露"),
            ("情绪", "爽点", "节奏"),
        ),
    },
    "character_refs": {
        "label": "人物参考图",
        "min_chars": 140,
        "required_any": (
            ("角色", "人物", "主角"),
            ("外貌", "年龄", "服装", "气质"),
            ("Prompt", "prompt", "提示词", "一致性"),
        ),
    },
    "storyboard": {
        "label": "分镜",
        "min_chars": 120,
        "required_any": (
            ("场景",),
            ("人物", "角色"),
            ("动作", "镜头"),
            ("Prompt", "prompt", "视频生成"),
        ),
    },
}

PLACEHOLDER_PATTERNS = (
    "script",
    "style",
    "plot",
    "refs",
    "reference",
    "storyboard",
    "draft",
    "confirmed",
    "确认剧本",
    "确认稿",
    "不太好的小说",
)


def normalize_stage_asset(stage: str, content: str) -> dict[str, Any]:
    raw = str(content or "").strip()
    asset: dict[str, Any] = {"stage": stage, "raw": raw}
    if stage == "storyboard":
        asset["shots"] = _parse_storyboard_shots(raw)
    else:
        asset["sections"] = _parse_colon_sections(raw)
    return asset


def validate_stage_asset(stage: str, content: str) -> dict[str, Any]:
    """Return a production-readiness report for one short-drama stage draft."""
    raw = str(content or "").strip()
    rule = STAGE_QUALITY_RULES.get(stage, {"label": stage, "min_chars": 80, "required_any": ()})
    errors: list[str] = []
    warnings: list[str] = []

    if len(raw) < int(rule["min_chars"]):
        errors.append("内容过短")

    if _looks_like_placeholder(raw):
        errors.append("疑似占位稿")

    missing_groups = [
        tuple(group)
        for group in rule.get("required_any", ())
        if not _contains_any(raw, group)
    ]
    if missing_groups:
        errors.append(f"缺少{rule['label']}结构")

    asset = normalize_stage_asset(stage, raw)
    summary: dict[str, Any] = {"char_count": len(raw)}
    if stage == "storyboard":
        shots = asset.get("shots") or []
        summary["shot_count"] = len(shots)
        if not shots:
            errors.append("缺少可解析镜头")
        else:
            incomplete = [
                shot.get("index")
                for shot in shots
                if not shot.get("scene") or not shot.get("action") or not shot.get("camera")
            ]
            if incomplete:
                errors.append("镜头字段不完整")
            prompt_count = sum(1 for block in _split_numbered_blocks(raw) if "prompt" in block["body"].lower() or "视频生成" in block["body"])
            summary["prompt_count"] = prompt_count
            if prompt_count < len(shots):
                warnings.append("部分镜头缺少视频生成Prompt")
    else:
        sections = asset.get("sections") or {}
        summary["section_count"] = len(sections)
        if len(sections) < 2:
            warnings.append("结构化小节偏少")

    score = _quality_score(errors, warnings, summary)
    return {
        "stage": stage,
        "label": rule["label"],
        "valid": not errors,
        "score": score,
        "errors": errors,
        "warnings": warnings,
        "summary": summary,
    }


def estimate_video_cost(
    *,
    shot_count: int,
    seconds_per_shot: int = 6,
    unit_price_cny: float = 0.0,
) -> dict[str, Any]:
    safe_shot_count = max(0, int(shot_count or 0))
    safe_seconds = max(1, int(seconds_per_shot or 1))
    estimated_seconds = safe_shot_count * safe_seconds
    unit_price = float(unit_price_cny or 0.0)
    return {
        "currency": "CNY",
        "shot_count": safe_shot_count,
        "seconds_per_shot": safe_seconds,
        "estimated_seconds": estimated_seconds,
        "unit_price_cny": unit_price,
        "estimated_total_cny": round(safe_shot_count * unit_price, 2),
    }


def _looks_like_placeholder(raw: str) -> bool:
    compact = re.sub(r"[\s_\-：:。.!！]+", "", raw).lower()
    if not compact:
        return True
    if compact in {re.sub(r"[\s_\-：:。.!！]+", "", item).lower() for item in PLACEHOLDER_PATTERNS}:
        return True
    return bool(re.fullmatch(r"(script|style|plot|refs|storyboard)(draft|confirmed|稿|确认)?", compact))


def _contains_any(raw: str, needles: tuple[str, ...]) -> bool:
    return any(needle in raw for needle in needles)


def _quality_score(errors: list[str], warnings: list[str], summary: dict[str, Any]) -> float:
    if errors:
        return 0.0
    score = 1.0
    score -= 0.1 * len(warnings)
    if summary.get("char_count", 0) < 240:
        score -= 0.1
    return round(max(0.0, min(1.0, score)), 2)


def _parse_storyboard_shots(raw: str) -> list[dict[str, Any]]:
    blocks = _split_numbered_blocks(raw)
    shots: list[dict[str, Any]] = []
    for fallback_index, block in enumerate(blocks, start=1):
        header = block["header"]
        fields = _parse_colon_sections(block["body"])
        index = _first_int(header) or fallback_index
        shot = {
            "index": index,
            "scene": fields.get("场景", ""),
            "characters": _split_names(fields.get("人物", "")),
            "action": fields.get("动作", ""),
            "dialogue": fields.get("对白", ""),
            "camera": fields.get("镜头", ""),
            "duration_seconds": _first_int(fields.get("时长", "")) or 6,
        }
        if any(value for key, value in shot.items() if key not in {"index", "duration_seconds"}):
            shots.append(shot)
    return shots


def _split_numbered_blocks(raw: str) -> list[dict[str, str]]:
    matches = list(re.finditer(r"(?m)^\s*(\d+)[\.、)]\s*(.*)$", raw))
    if not matches:
        return [{"header": "", "body": raw}]

    blocks: list[dict[str, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(raw)
        header = f"{match.group(1)} {match.group(2)}".strip()
        header_body = match.group(2).strip()
        body = raw[start:end].strip()
        if header_body:
            body = f"{header_body}\n{body}".strip()
        blocks.append({"header": header, "body": body})
    return blocks


def _parse_colon_sections(raw: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current_key = ""
    for line in raw.splitlines():
        stripped = line.strip().lstrip("-").strip()
        if not stripped:
            continue
        if "：" in stripped:
            key, value = stripped.split("：", 1)
        elif ":" in stripped:
            key, value = stripped.split(":", 1)
        else:
            if current_key:
                sections[current_key] = f"{sections[current_key]}\n{stripped}".strip()
            continue
        current_key = key.strip()
        if current_key:
            sections[current_key] = value.strip()
    return sections


def _split_names(value: str) -> list[str]:
    return [
        item.strip()
        for item in re.split(r"[,，、/ ]+", value or "")
        if item.strip()
    ]


def _first_int(value: str) -> int | None:
    match = re.search(r"\d+", str(value or ""))
    return int(match.group(0)) if match else None
