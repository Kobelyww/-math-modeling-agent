"""Normalize short-drama stage drafts into structured assets."""
from __future__ import annotations

import re
from typing import Any


def normalize_stage_asset(stage: str, content: str) -> dict[str, Any]:
    raw = str(content or "").strip()
    asset: dict[str, Any] = {"stage": stage, "raw": raw}
    if stage == "storyboard":
        asset["shots"] = _parse_storyboard_shots(raw)
    else:
        asset["sections"] = _parse_colon_sections(raw)
    return asset


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
