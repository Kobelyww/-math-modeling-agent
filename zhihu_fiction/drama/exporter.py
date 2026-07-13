"""Export short-drama projects as prompt packages."""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from ..core.config import APP_ROOT
from .models import DramaProject


def safe_filename(value: str, default: str = "short_drama") -> str:
    cleaned = "".join(char for char in value if char.isalnum() or char in ("-", "_", " "))
    cleaned = cleaned.strip().replace(" ", "_")
    return cleaned[:60] or default


class DramaExporter:
    """Write human-readable and machine-readable short-drama prompt packages."""

    def __init__(self, output_root: Path | None = None, now_fn=None) -> None:
        self.output_root = output_root or APP_ROOT / "output"
        self.now_fn = now_fn or (lambda: datetime.now().strftime("%Y%m%d_%H%M%S"))

    def export(self, project: DramaProject) -> Path:
        project.validate()
        base_dir = self.output_root / safe_filename(project.source_title or project.title)
        package_dir = self._unique_package_dir(base_dir / f"短剧视频Prompt包_{self.now_fn()}")
        package_dir.mkdir(parents=True, exist_ok=False)

        (package_dir / "manifest.json").write_text(
            json.dumps(self._manifest(project), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (package_dir / "改编方案.md").write_text(self._render_plan(project), encoding="utf-8")
        (package_dir / "角色一致性设定.md").write_text(self._render_consistency(project), encoding="utf-8")
        (package_dir / "分集剧本.md").write_text(self._render_scripts(project), encoding="utf-8")
        (package_dir / "镜头表.json").write_text(
            json.dumps(self._shot_table(project), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (package_dir / "视频生成Prompts.md").write_text(self._render_video_prompts(project), encoding="utf-8")
        return package_dir

    def export_failure(self, source_title: str, raw_output: str, error: str) -> Path:
        base_dir = self.output_root / safe_filename(source_title)
        package_dir = self._unique_package_dir(base_dir / f"短剧视频Prompt包_{self.now_fn()}_失败")
        package_dir.mkdir(parents=True, exist_ok=False)
        (package_dir / "raw_output.txt").write_text(raw_output, encoding="utf-8")
        (package_dir / "error.txt").write_text(error, encoding="utf-8")
        return package_dir

    @staticmethod
    def _unique_package_dir(path: Path) -> Path:
        if not path.exists():
            return path
        counter = 2
        while True:
            candidate = path.with_name(f"{path.name}_{counter}")
            if not candidate.exists():
                return candidate
            counter += 1

    @staticmethod
    def _manifest(project: DramaProject) -> dict:
        return {
            "title": project.title,
            "source_title": project.source_title,
            "genre": project.genre,
            "logline": project.logline,
            "audience": project.audience,
            "episode_count": project.episode_count,
            "shot_count": project.total_shots,
            "files": {
                "adaptation_plan": "改编方案.md",
                "consistency": "角色一致性设定.md",
                "scripts": "分集剧本.md",
                "shot_table": "镜头表.json",
                "video_prompts": "视频生成Prompts.md",
            },
            "project": project.to_dict(),
        }

    @staticmethod
    def _shot_table(project: DramaProject) -> list[dict]:
        rows = []
        for episode in project.episodes:
            for shot in episode.shots:
                row = asdict(shot)
                row["episode_title"] = episode.title
                rows.append(row)
        return rows

    @staticmethod
    def _render_plan(project: DramaProject) -> str:
        lines = [
            f"# {project.title}",
            "",
            f"原小说：{project.source_title}",
            f"题材：{project.genre}",
            f"一句话卖点：{project.logline}",
            f"目标观众：{project.audience}",
            f"分集数量：{project.episode_count}",
            f"镜头数量：{project.total_shots}",
            "",
            "## 改编策略",
        ]
        lines.extend(f"- {note}" for note in project.adaptation_notes)
        lines.extend(["", "## 风险提示"])
        lines.extend(f"- {note}" for note in project.risk_notes)
        return "\n".join(lines).strip() + "\n"

    @staticmethod
    def _render_consistency(project: DramaProject) -> str:
        lines = [f"# {project.title} 角色一致性设定", "", "## 角色"]
        for character in project.characters:
            lines.extend(
                [
                    "",
                    f"### {character.name} ({character.id})",
                    f"- 功能：{character.role}",
                    f"- 年龄：{character.age_range}",
                    f"- 外貌：{character.appearance}",
                    f"- 服装：{character.costume}",
                    f"- 性格：{character.personality}",
                    f"- 动机：{character.motivation}",
                    f"- 一致性 Prompt：{character.consistency_prompt}",
                ]
            )
        lines.extend(["", "## 场景"])
        for location in project.locations:
            lines.extend(
                [
                    "",
                    f"### {location.name} ({location.id})",
                    f"- 视觉风格：{location.visual_style}",
                    f"- 时代背景：{location.time_period}",
                    f"- 灯光：{location.lighting}",
                    f"- 一致性 Prompt：{location.consistency_prompt}",
                ]
            )
        return "\n".join(lines).strip() + "\n"

    @staticmethod
    def _render_scripts(project: DramaProject) -> str:
        lines = [f"# {project.title} 分集剧本"]
        for episode in project.episodes:
            lines.extend(
                [
                    "",
                    f"## 第 {episode.index} 集：{episode.title}",
                    "",
                    f"开场钩子：{episode.hook}",
                    f"剧情简介：{episode.synopsis}",
                    f"结尾悬念：{episode.cliffhanger}",
                    "",
                    "### 镜头",
                ]
            )
            for shot in episode.shots:
                lines.extend(
                    [
                        "",
                        f"#### {shot.id}",
                        f"- 时长：{shot.duration_seconds}s",
                        f"- 场景：{shot.location_id}",
                        f"- 角色：{', '.join(shot.character_ids)}",
                        f"- 动作：{shot.action}",
                        f"- 对白：{shot.dialogue}",
                        f"- 情绪：{shot.emotion}",
                        f"- 镜头：{shot.camera}",
                    ]
                )
        return "\n".join(lines).strip() + "\n"

    @staticmethod
    def _render_video_prompts(project: DramaProject) -> str:
        lines = [f"# {project.title} 视频生成 Prompts"]
        for episode in project.episodes:
            lines.extend(["", f"## 第 {episode.index} 集：{episode.title}"])
            for shot in episode.shots:
                lines.extend(
                    [
                        "",
                        f"### {shot.id}",
                        f"- Duration: {shot.duration_seconds}s",
                        f"- Camera: {shot.camera}",
                        f"- Visual Prompt: {shot.visual_prompt}",
                        f"- Negative Prompt: {shot.negative_prompt}",
                        f"- Consistency Refs: {', '.join(shot.consistency_refs)}",
                        f"- Dialogue: {shot.dialogue}",
                        f"- Action: {shot.action}",
                    ]
                )
        return "\n".join(lines).strip() + "\n"
