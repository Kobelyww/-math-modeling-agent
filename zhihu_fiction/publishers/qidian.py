"""起点中文网发布适配器。

起点发布结构：
- 创建新书 → 填写书籍信息（书名、简介、分类、标签）
- 创建分卷 → 在卷下添加章节
- 正文为纯文本，章节字数建议 2000-4000 字
"""

from __future__ import annotations

from .base import BasePublisher, Chapter, PlatformMeta

QIDIAN_CATEGORIES = [
    "玄幻", "奇幻", "武侠", "仙侠", "都市", "现实", "历史",
    "军事", "游戏", "体育", "科幻", "悬疑", "轻小说", "短篇",
]

QIDIAN_PUBLISH_GUIDE = """## 起点中文网发布步骤

### 前提条件
- 注册起点作家账号：writer.qq.com 或 起点读书App「作家专区」
- 完成实名认证

### 第一步：创建新书
1. 登录作家专区 → 点击「创建新书」
2. 填写书籍信息（见下方「书籍信息.md」）
3. 选择分类（务必选对，影响推荐曝光）
4. 上传封面（可用 Canva 制作或 AI 生成）
5. 提交审核（通常 24-48 小时）

### 第二步：创建分卷
1. 审核通过后 → 进入「作品管理」
2. 点击「新建分卷」→ 命名为「第一卷」
3. 在卷下点击「新建章节」

### 第三步：发布章节
1. 按顺序逐章发布（见 `卷1/` 目录下的章节文件）
2. 每章发布后建议间隔 10-30 分钟再发下一章（模拟真实更新）
3. 首日建议发布 3-5 章，之后每天 1-2 章

### 起点特有注意事项
- 每章字数建议 2000-4000，低于 1000 字无法发布
- 章节标题不要有特殊符号
- 简介不能有外链和联系方式
- 开头 3 章决定留存率，务必精修
"""


class QidianPublisher(BasePublisher):
    platform_name = "起点中文网"

    def format_content(self, full_text: str, title: str) -> str:
        lines = full_text.split("\n")
        cleaned: list[str] = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(">") or stripped.startswith("![") or stripped.startswith("---"):
                if stripped.startswith("> 原"):
                    continue
                cleaned.append(stripped)
            else:
                cleaned.append(stripped)
        return "\n".join(cleaned).strip()

    def get_platform_meta_prompt(self, story_text: str, title: str, genre: str) -> str:
        return f"""你是起点中文网资深编辑。请为以下小说生成起点平台的书籍元数据。

小说主题：{title}
题材类型：{genre}
可选分类：{', '.join(QIDIAN_CATEGORIES)}

小说正文（前1200字）：
{story_text[:1200]}

请输出以下元数据（每行一个，简洁准确）：
起点书名（10-15字，要有网文风格，可加「之」「录」「纪」等字）：
分类（从可选分类中选一个最匹配的）：
长篇简介（150-200字，包含世界观、主角设定、核心冲突、爽点）：
短简介（50字以内，用于搜索结果展示）：
标签（5个，逗号分隔，如：系统流,穿越,无脑爽,扮猪吃虎,金手指）：
卖点关键词（3个，如：神医穿越、反转打脸、悬疑破案）："""

    def get_publish_guide(self) -> str:
        return QIDIAN_PUBLISH_GUIDE

    def _split_chapters(self, text: str, min_chapter_length: int = 800) -> list[Chapter]:
        chapters = super()._split_chapters(text, min_chapter_length=min_chapter_length)
        validated: list[Chapter] = []
        for ch in chapters:
            content = ch.content.strip()
            word_count = len(content)
            if word_count < 100:
                continue
            if word_count < 400 and validated:
                validated[-1].content += "\n\n" + ch.title + "\n" + content
                continue
            if word_count > 4000:
                parts = self._split_long_chapter(content)
                for i, part in enumerate(parts):
                    validated.append(
                        Chapter(
                            title=f"{ch.title}（{i + 1}）" if len(parts) > 1 else ch.title,
                            content=part,
                            index=len(validated),
                        )
                    )
                continue
            validated.append(Chapter(title=ch.title, content=content, index=len(validated)))
        return validated

    @staticmethod
    def _split_long_chapter(content: str, max_len: int = 3800) -> list[str]:
        paragraphs = content.split("\n\n")
        parts: list[str] = []
        current: list[str] = []
        current_len = 0
        for p in paragraphs:
            p_len = len(p)
            if current_len + p_len > max_len and current:
                parts.append("\n\n".join(current))
                current = [p]
                current_len = p_len
            else:
                current.append(p)
                current_len += p_len
        if current:
            parts.append("\n\n".join(current))
        return parts or [content]

    def generate_export(self, full_text: str, title: str, genre: str, metadata: PlatformMeta | None = None):
        if metadata is None:
            metadata = PlatformMeta(
                book_title=title,
                synopsis=full_text[:200] + "..." if len(full_text) > 200 else full_text,
                category=genre or "玄幻",
                tags=[genre] if genre else [],
            )

        cleaned = self.format_content(full_text, title)
        chapters = self._split_chapters(cleaned)

        from .base import ExportPackage

        book_info = (
            f"书名：{metadata.book_title}\n"
            f"分类：{metadata.category}\n"
            f"标签：{', '.join(metadata.tags)}\n"
            f"作者备注：{metadata.author_note}\n\n"
            f"## 长篇简介\n{metadata.synopsis}\n"
        )

        chapter_files: dict[str, str] = {}
        for ch in chapters:
            chapter_files[f"卷1/第{ch.index + 1}章_{ch.title}.md"] = (
                f"# 第{ch.index + 1}章 {ch.title}\n\n{ch.content}"
            )

        chapter_list = "\n".join(
            f"{ch.index + 1}. {ch.title} ({len(ch.content)}字)" for ch in chapters
        )
        chapter_files["卷1/章节列表.md"] = f"# 第一卷 章节列表\n\n共 {len(chapters)} 章\n\n{chapter_list}"

        return ExportPackage(
            platform=self.platform_name,
            metadata=metadata,
            chapters=chapters,
            full_text=cleaned,
            publish_guide=self.get_publish_guide(),
            extra_files={"书籍信息.md": book_info, **chapter_files},
        )
