"""Story file listing and loading services."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import HTTPException

from ...base import extract_story_body
from ...config import APP_ROOT
from ...orchestrator import StageResult, WorkflowResult
from ..legacy_compat import server_path_attr

OUTPUT_DIR = APP_ROOT / "output"


def app_root() -> Path:
    return server_path_attr("APP_ROOT", APP_ROOT)


def output_dir() -> Path:
    return server_path_attr("OUTPUT_DIR", OUTPUT_DIR)


def list_story_dirs() -> list[dict]:
    root = app_root()
    directory_root = output_dir()
    if not directory_root.exists():
        return []
    stories: list[dict] = []
    for directory in sorted(directory_root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if directory.is_dir() and not directory.name.startswith("."):
            story_file = directory / "小说正文.md"
            if story_file.exists():
                content = story_file.read_text(encoding="utf-8")
                lines = content.strip().split("\n")
                excerpt = next(
                    (
                        line
                        for line in lines
                        if line.strip() and not line.startswith("#") and not line.startswith(">")
                    ),
                    "",
                )[:200]
                stories.append({
                    "name": directory.name,
                    "path": str(story_file.relative_to(root)),
                    "excerpt": excerpt,
                    "created_at": datetime.fromtimestamp(story_file.stat().st_mtime).isoformat(),
                })
    return stories


def extract_web_story_body(text: str) -> tuple[str, str]:
    story, synthesis = extract_story_body(text)
    if story:
        return story, synthesis

    story_lines: list[str] = []
    synth_lines: list[str] = []
    in_synthesis = False
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped == "# 发布方案":
            in_synthesis = True
            continue
        if in_synthesis:
            synth_lines.append(line)
            continue
        if stripped.startswith("# ") or stripped.startswith(">"):
            continue
        story_lines.append(line)
    return "\n".join(story_lines).strip(), "\n".join(synth_lines).strip()


def story_result_from_file(story_file: Path) -> WorkflowResult:
    text = story_file.read_text(encoding="utf-8")
    topic = story_file.parent.name
    genre = ""
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("# ") and topic == story_file.parent.name:
            topic = stripped[2:].strip() or topic
        elif stripped.startswith("> 题材：") and not genre:
            genre = stripped.removeprefix("> 题材：").strip()
        if topic and genre:
            break

    story, synthesis = extract_web_story_body(text)
    return WorkflowResult(
        topic=topic,
        genre=genre or "未知",
        topic_analysis=StageResult("选题分析智能体", ""),
        outline=StageResult("大纲规划智能体", ""),
        draft=StageResult("初稿创作智能体", ""),
        polished=story,
        review="从 Web 作品加载",
        synthesis=synthesis or "从 Web 作品加载",
    )


def safe_story_file(story_path: str) -> Path:
    root = app_root()
    full_path = (root / story_path).resolve()
    resolved_root = root.resolve()
    try:
        full_path.relative_to(resolved_root)
    except ValueError as exc:
        raise HTTPException(400, "非法故事路径") from exc
    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(404, "故事未找到")
    return full_path
