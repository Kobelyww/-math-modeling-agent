"""发布导出协调器。

协调所有平台的格式化和元数据生成，统一输出发布包。
"""

from __future__ import annotations

from pathlib import Path

from langchain_core.language_models import BaseChatModel

from .core.config import APP_ROOT
from .fiction.orchestrator import WorkflowResult
from .publishers.base import PlatformMeta
from .publishers.fanqie import FanqiePublisher
from .publishers.qidian import QidianPublisher
from .publishers.zhihu import ZhihuSaltPublisher

DEFAULT_PLATFORMS = ["zhihu", "qidian", "fanqie"]

METADATA_PROMPT = """你是多平台小说运营专家。请为以下小说生成三个平台（知乎盐选、起点中文网、番茄小说）的发布元数据。

小说主题：{title}
题材类型：{genre}

小说正文（前1500字，用于判断风格和内容）：
{story_preview}

请按以下格式输出（用 [平台名] 标记分段，每项一行）：

[知乎盐选]
标题：
副标题：
话题标签（5个，#开头，逗号分隔）：
推荐语（30字内）：

[起点中文网]
书名（10-15字，网文风格）：
分类：
长篇简介（150-200字）：
短简介（50字内）：
标签（5个，逗号分隔）：
卖点关键词（3个，逗号分隔）：

[番茄小说]
书名（15-25字，含有流量关键词）：
分类：
简介（30-100字，前30字必须有钩子）：
标签（5个，逗号分隔）：
一句话卖点（10字内）："""


def _parse_metadata_section(text: str, platform: str) -> PlatformMeta | None:
    """从 LLM 返回的文本中解析指定平台的元数据。"""
    marker = f"[{platform}]"
    sections = text.split("[")
    target = ""
    for sec in sections:
        if sec.startswith(platform + "]"):
            target = sec.split("]", 1)[1] if "]" in sec else sec
            break

    if not target:
        return None

    def extract(key: str, default: str = "") -> str:
        for line in target.split("\n"):
            line = line.strip()
            if not line:
                continue
            content = line.split("：", 1)[-1].split(":", 1)[-1] if "：" in line or ":" in line else ""
            label = line.split("：")[0].split(":")[0]
            label_clean = label.split("（")[0].split("(")[0].strip()
            if label_clean == key or key in label_clean or label_clean in key:
                return content.strip()
        return default

    book_title = extract("书名") or extract("标题")
    synopsis = extract("简介") or extract("长篇简介")
    short_synopsis = extract("短简介")
    if short_synopsis:
        synopsis = f"{short_synopsis}\n\n{synopsis}" if synopsis else short_synopsis

    category = extract("分类", "其他")
    tags_str = extract("标签") or extract("话题标签")
    raw_tags = tags_str.replace("，", ",").replace("#", " ").replace("、", ",").split(",")
    tags = []
    for t in raw_tags:
        for sub in t.strip().split():
            sub = sub.strip()
            if sub and sub not in tags:
                tags.append(sub)

    keyword_str = extract("卖点关键词") or extract("一句话卖点")
    if keyword_str and keyword_str not in synopsis:
        pass

    return PlatformMeta(
        book_title=book_title or "未命名",
        synopsis=synopsis or "精彩故事，敬请期待",
        category=category,
        tags=tags[:8],
        author_note=keyword_str,
    )


def _generate_all_metadata(llm: BaseChatModel, story_text: str, title: str, genre: str) -> dict[str, PlatformMeta]:
    """调用 LLM 一次性生成三个平台的元数据。"""
    prompt = METADATA_PROMPT.format(
        title=title,
        genre=genre or "未指定",
        story_preview=story_text[:1500],
    )

    response = llm.invoke(prompt)
    content = response.content if hasattr(response, "content") else str(response)
    if isinstance(content, list):
        content = "".join(
            str(item.get("text", item)) if isinstance(item, dict) else str(item)
            for item in content
        )

    result: dict[str, PlatformMeta] = {}
    for platform, platform_name in [
        ("zhihu", "知乎盐选"),
        ("qidian", "起点中文网"),
        ("fanqie", "番茄小说"),
    ]:
        meta = _parse_metadata_section(content, platform_name)
        if meta is None:
            meta = PlatformMeta(
                book_title=title,
                synopsis=story_text[:200] + "...",
                category=genre or "其他",
                tags=[genre] if genre else [],
            )
        result[platform] = meta

    return result


class Exporter:
    """发布导出协调器"""

    def __init__(self, llm: BaseChatModel) -> None:
        self.zhihu = ZhihuSaltPublisher()
        self.qidian = QidianPublisher()
        self.fanqie = FanqiePublisher()
        self.llm = llm
        self._last_result: WorkflowResult | None = None
        self._last_packages: dict[str, object] = {}

    def export(
        self,
        result: WorkflowResult,
        platforms: list[str] | None = None,
    ) -> dict[str, str]:
        """对 WorkflowResult 执行多平台发布导出。

        Returns:
            {platform_key: output_dir_path}
        """
        self._last_result = result
        platforms = platforms or DEFAULT_PLATFORMS

        full_text = result.final_story
        title = result.topic
        genre = result.genre

        metadata_map = _generate_all_metadata(self.llm, full_text, title, genre)

        safe_topic = "".join(c for c in result.topic if c.isalnum() or c in ("-", "_", " "))[:40]
        safe_topic = safe_topic.strip().replace(" ", "_")
        base_dir = APP_ROOT / "output" / safe_topic
        base_dir.mkdir(parents=True, exist_ok=True)

        output_dirs: dict[str, str] = {}

        publishers = {
            "zhihu": (self.zhihu, "知乎盐选"),
            "qidian": (self.qidian, "起点中文网"),
            "fanqie": (self.fanqie, "番茄小说"),
        }

        for key in platforms:
            if key not in publishers:
                continue

            publisher, dir_name = publishers[key]
            platform_dir = base_dir / dir_name
            platform_dir.mkdir(parents=True, exist_ok=True)

            meta = metadata_map.get(key)
            package = publisher.generate_export(full_text, title, genre, meta)

            content_file = platform_dir / "发布内容.md"
            content_file.write_text(package.full_text, encoding="utf-8")

            guide_file = platform_dir / "发布指引.md"
            guide_file.write_text(package.publish_guide, encoding="utf-8")

            metadata_file = platform_dir / "元数据.md"
            metadata_lines = [
                f"# {package.platform} 元数据",
                "",
                f"书名：{package.metadata.book_title}",
                f"分类：{package.metadata.category}",
                f"标签：{', '.join(package.metadata.tags)}",
                f"简介：{package.metadata.synopsis}",
            ]
            if package.metadata.author_note:
                metadata_lines.append(f"备注：{package.metadata.author_note}")
            metadata_file.write_text("\n\n".join(metadata_lines), encoding="utf-8")

            for rel_path, content in package.extra_files.items():
                extra_file = platform_dir / rel_path
                extra_file.parent.mkdir(parents=True, exist_ok=True)
                extra_file.write_text(content, encoding="utf-8")

            chapters_dir = platform_dir / "卷1"
            for ch in package.chapters:
                ch_path = chapters_dir / f"第{ch.index + 1}章_{ch.title}.md"
                chapters_dir.mkdir(parents=True, exist_ok=True)
                ch_path.write_text(f"# 第{ch.index + 1}章 {ch.title}\n\n{ch.content}", encoding="utf-8")

            output_dirs[key] = str(platform_dir)

        self._last_packages = {k: publishers[k][0] for k in platforms if k in publishers}
        return output_dirs

    def auto_publish(
        self,
        result: WorkflowResult | None = None,
        platforms: list[str] | None = None,
    ) -> dict[str, bool]:
        """通过浏览器自动化直接发布到各平台。

        首次使用会弹出浏览器窗口让用户手动登录，之后自动保存 session。

        Args:
            result: 创作结果。如果为 None，使用上次 export 的结果。
            platforms: 目标平台列表，默认全部。

        Returns:
            {platform_key: success}
        """
        from .automator import Automator

        target = result or self._last_result
        if target is None:
            raise ValueError("没有可发布的创作结果")

        full_text = target.final_story
        title = target.topic
        genre = target.genre
        platforms = platforms or DEFAULT_PLATFORMS

        print(f"\n[自动发布] 主题: {title}")
        print(f"[自动发布] 目标平台: {', '.join(platforms)}")
        print(f"[自动发布] 开始生成元数据...")

        metadata_map = _generate_all_metadata(self.llm, full_text, title, genre)
        metadata_dict = {}
        for key, meta in metadata_map.items():
            metadata_dict[key] = {
                "book_title": meta.book_title,
                "synopsis": meta.synopsis,
                "category": meta.category,
                "tags": meta.tags,
                "author_note": meta.author_note,
            }

        chapters_map = {}
        for key in platforms:
            if key == "zhihu":
                continue
            elif key == "qidian":
                qd = QidianPublisher()
                cleaned = qd.format_content(full_text, title)
                chapters_map["qidian"] = [
                    {"title": ch.title, "content": ch.content, "index": ch.index}
                    for ch in qd._split_chapters(cleaned)
                ]
            elif key == "fanqie":
                fq = FanqiePublisher()
                cleaned = fq.format_content(full_text, title)
                chapters_map["fanqie"] = [
                    {"title": ch.title, "content": ch.content, "index": ch.index}
                    for ch in fq._split_chapters(cleaned)
                ]

        automator = Automator(headless=False, slow_mo=200)
        try:
            results = automator.publish_all(
                title=title,
                content=full_text,
                genre=genre,
                metadata_map=metadata_dict,
                chapters_map=chapters_map,
                platforms=platforms,
            )
        finally:
            automator.cleanup()

        return results

    @property
    def last_result(self) -> WorkflowResult | None:
        return self._last_result
