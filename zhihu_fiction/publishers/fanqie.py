
"""番茄小说发布适配器。

番茄小说特点：
- 字节跳动旗下，算法推荐驱动
- 书名偏长（15-25字），需要引发好奇
- 简介要求 30-100 字，精炼有力
- 标签体系偏轻松，偏爽文标签
- 首章开篇极其重要（留存率决定推荐量）
"""

from __future__ import annotations

from .base import BasePublisher, Chapter, PlatformMeta

FANQIE_CATEGORIES = [
    "都市", "玄幻", "仙侠", "历史", "科幻", "悬疑",
    "言情", "穿越", "重生", "系统", "种田", "脑洞",
    "职场", "校园", "都市情感", "推理", "恐怖",
]

FANQIE_TAG_POOL = [
    "爽文", "系统流", "穿越", "重生", "逆袭", "打脸", "扮猪吃虎",
    "金手指", "神医", "鉴宝", "悬疑", "反转", "甜宠", "虐恋",
    "先婚后爱", "替身", "和亲", "种田", "基建", "商战", "修仙",
    "末世", "无限流", "规则怪谈", "密室逃脱", "AI", "脑洞",
]

FANQIE_PUBLISH_GUIDE = """## 番茄小说发布步骤

### 前提条件
- 下载「番茄作家助手」App（手机端）或访问 novelist.toutiao.com
- 注册并完成实名认证

### 第一步：创建新书
1. 打开番茄作家助手 → 点击「创建作品」
2. 填写作品信息（见下方「书籍信息.md」）
3. 选择分类和标签（标签影响推荐精准度，务必认真选）
4. 上传封面（可用「番茄封面制作」功能自动生成）
5. 提交审核

### 第二步：发布章节
1. 审核通过后（通常 24 小时内）→ 进入「章节管理」
2. 逐章发布（见 `章节/` 目录下的文件）
3. 番茄首章要求在 2000 字以上

### 第三步：签约与推荐
1. 满 2 万字后可申请签约
2. 签约通过后进入推荐池
3. 番茄推荐完全由算法驱动，前 3 章的读完率决定生死

### 番茄特有注意事项
- 书名要长！15-25 字，带关键词（如「穿越」「重生」「系统」）
- 简介要炸！前 30 字必须抓眼球
- 标签决定推荐人群，选错标签 = 推给错的人
- 番茄读者耐心极低，前 500 字必须有冲突或悬念
- 番茄审核比起点严格，严禁色情、政治敏感内容
"""


class FanqiePublisher(BasePublisher):
    platform_name = "番茄小说"

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
        return f"""你是番茄小说资深编辑。请为以下小说生成番茄平台的书籍元数据。

小说主题：{title}
题材类型：{genre}
可选分类：{', '.join(FANQIE_CATEGORIES)}
可选标签池：{', '.join(FANQIE_TAG_POOL)}

小说正文（前1200字）：
{story_text[:1200]}

请输出以下元数据（每行一个，简洁准确）：

番茄书名（15-25字，必须长且有吸引力，包含如「穿越」「重生」「系统」等流量关键词）：
分类（从可选分类中选一个最匹配的）：
短简介（30-100字，前30字必须有钩子，直接抛出核心冲突或爽点。番茄简介不是摘要，是广告语）：
标签（5个，从标签池中选择，逗号分隔。前2个最重要，影响推荐精准度）：
一句话卖点（10字以内，用于封面或推广位，如「开局满级神医吊打穿越者」）：
开篇钩子描述（前500字最吸引人的点是什么，20字以内）："""

    def get_publish_guide(self) -> str:
        return FANQIE_PUBLISH_GUIDE

    def _split_chapters(self, text: str, min_chapter_length: int = 1200) -> list[Chapter]:
        chapters = super()._split_chapters(text, min_chapter_length=min_chapter_length)
        validated: list[Chapter] = []
        for ch in chapters:
            content = ch.content.strip()
            word_count = len(content)
            if word_count < 200:
                continue
            if word_count < 800 and validated:
                validated[-1].content += "\n\n" + ch.title + "\n" + content
                continue
            if word_count > 5000:
                paragraphs = content.split("\n\n")
                mid = len(paragraphs) // 2
                part1 = "\n\n".join(paragraphs[:mid])
                part2 = "\n\n".join(paragraphs[mid:])
                validated.append(Chapter(title=f"{ch.title}（上）", content=part1, index=len(validated)))
                validated.append(Chapter(title=f"{ch.title}（下）", content=part2, index=len(validated)))
                continue
            validated.append(Chapter(title=ch.title, content=content, index=len(validated)))
        return validated

    def generate_export(self, full_text: str, title: str, genre: str, metadata: PlatformMeta | None = None):
        if metadata is None:
            metadata = PlatformMeta(
                book_title=title,
                synopsis=full_text[:100] + "..." if len(full_text) > 100 else full_text,
                category=genre or "都市",
                tags=[genre] if genre else [],
            )

        cleaned = self.format_content(full_text, title)
        chapters = self._split_chapters(cleaned)

        from .base import ExportPackage

        book_info = (
            f"书名：{metadata.book_title}\n"
            f"分类：{metadata.category}\n"
            f"标签：{', '.join(metadata.tags)}\n\n"
            f"## 简介\n{metadata.synopsis}\n\n"
            f"作者备注：{metadata.author_note}\n"
        )

        chapter_files: dict[str, str] = {}
        for ch in chapters:
            safe_title = "".join(c for c in ch.title if c.isalnum() or c in ("-", "_", " "))
            chapter_files[f"章节/第{ch.index + 1}章_{safe_title}.md"] = (
                f"# 第{ch.index + 1}章 {ch.title}\n\n{ch.content}"
            )

        return ExportPackage(
            platform=self.platform_name,
            metadata=metadata,
            chapters=chapters,
            full_text=cleaned,
            publish_guide=self.get_publish_guide(),
            extra_files={"书籍信息.md": book_info, **chapter_files},
        )
