from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Chapter:
    title: str
    content: str
    index: int


@dataclass
class PlatformMeta:
    book_title: str
    synopsis: str
    category: str
    tags: list[str]
    author_note: str = ""


@dataclass
class ExportPackage:
    platform: str
    metadata: PlatformMeta
    chapters: list[Chapter]
    full_text: str
    publish_guide: str
    extra_files: dict[str, str] = field(default_factory=dict)


class BasePublisher(ABC):
    platform_name: str = ""

    def __init__(self) -> None:
        pass

    @staticmethod
    def _extract_title(text: str) -> str:
        for line in text.split("\n"):
            stripped = line.strip()
            if stripped.startswith("# ") and not stripped.startswith("## "):
                return stripped[2:].strip()
            if stripped and not stripped.startswith("#"):
                return stripped[:80]
        return "未命名"

    @staticmethod
    def _split_chapters(text: str, min_chapter_length: int = 200) -> list[Chapter]:
        chapters: list[Chapter] = []
        sections = re.split(r"\n(?=##\s)", text)

        if len(sections) <= 1:
            paras = text.strip().split("\n\n")
            chunk_size = max(1, len(paras) // max(1, (len(text) // 2500)))
            for i in range(0, len(paras), chunk_size):
                chunk = "\n\n".join(paras[i : i + chunk_size]).strip()
                if chunk:
                    chapters.append(
                        Chapter(title=f"第{len(chapters) + 1}章", content=chunk, index=len(chapters))
                    )
            return chapters

        for section in sections:
            section = section.strip()
            if not section:
                continue
            lines = section.split("\n", 1)
            title = lines[0].lstrip("#").strip()
            body = lines[1].strip() if len(lines) > 1 else ""
            if len(body) < min_chapter_length and chapters:
                chapters[-1].content += "\n\n" + section
            else:
                chapters.append(Chapter(title=title, content=body, index=len(chapters)))

        if not chapters:
            chapters.append(Chapter(title="正文", content=text, index=0))

        return chapters

    @abstractmethod
    def format_content(self, full_text: str, title: str) -> str:
        ...

    @abstractmethod
    def get_platform_meta_prompt(self, story_text: str, title: str, genre: str) -> str:
        ...

    @abstractmethod
    def get_publish_guide(self) -> str:
        ...

    def generate_export(
        self,
        full_text: str,
        title: str,
        genre: str,
        metadata: PlatformMeta | None = None,
    ) -> ExportPackage:
        if metadata is None:
            metadata = PlatformMeta(
                book_title=title,
                synopsis=full_text[:200] + "...",
                category=genre or "其他",
                tags=[genre] if genre else [],
            )

        formatted = self.format_content(full_text, title)
        chapters = self._split_chapters(formatted)
        guide = self.get_publish_guide()

        return ExportPackage(
            platform=self.platform_name,
            metadata=metadata,
            chapters=chapters,
            full_text=formatted,
            publish_guide=guide,
        )
