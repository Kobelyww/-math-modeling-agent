
"""知乎盐选发布适配器。

知乎盐选文章：
- 通常是专栏文章形式，Markdown 富文本
- 核心元数据：标题、话题标签、封面图（可选）
- 正文保留 Markdown 格式，不需分章
"""

from __future__ import annotations

from .base import BasePublisher, PlatformMeta

ZHIHU_PUBLISH_GUIDE = """## 知乎盐选发布步骤

### 方式一：发布为专栏文章（推荐）
1. 打开知乎网页版或 App，进入「创作中心」
2. 点击「写文章」→ 将下方「发布内容.md」全文粘贴到编辑器
3. 在顶部设置标题和话题标签
4. 点击「发布」→ 选择「专栏文章」

### 方式二：发布为回答
1. 搜索与小说主题相关的热门问题
2. 点击「写回答」→ 粘贴正文
3. 在文末添加引导语（如「赞同 过千更新后续」）

### 标题建议
请从下方元数据中选取最适合的标题，知乎标题推荐 15-30 字。

### 话题标签
发布时务必添加 3-5 个相关话题标签（如 #悬疑 #反转 #每日故事），这是自然流量的入口。
"""


class ZhihuSaltPublisher(BasePublisher):
    platform_name = "知乎盐选"

    def format_content(self, full_text: str, title: str) -> str:
        prefix = f"> 原标题：{title}\n\n"
        return prefix + full_text

    def get_platform_meta_prompt(self, story_text: str, title: str, genre: str) -> str:
        return f"""你是知乎盐选专栏编辑。请为以下小说生成知乎盐选发布元数据。

小说主题：{title}
题材类型：{genre}

小说正文（前800字）：
{story_text[:800]}

请输出以下元数据（每行一个，不要多余说明）：
知乎标题（15-30字，悬念型/共鸣型优先）：
副标题（10字以内，补充信息）：
推荐话题标签（5个，用#开头，逗号分隔）：
一句话推荐语（30字以内，用于社交媒体分享）：
封面建议（描述应配合什么风格的图片）："""

    def get_publish_guide(self) -> str:
        return ZHIHU_PUBLISH_GUIDE

    def generate_export(self, full_text: str, title: str, genre: str, metadata: PlatformMeta | None = None):
        if metadata is None:
            metadata = PlatformMeta(
                book_title=title,
                synopsis=full_text[:200] + "..." if len(full_text) > 200 else full_text,
                category=genre or "专栏",
                tags=[genre] if genre else [],
            )

        formatted = self.format_content(full_text, title)
        guide = self.get_publish_guide()

        from .base import ExportPackage

        return ExportPackage(
            platform=self.platform_name,
            metadata=metadata,
            chapters=[],  # 知乎不分章
            full_text=formatted,
            publish_guide=guide,
            extra_files={
                "发布标题与标签.txt": f"标题: {metadata.book_title}\n副标题: \n话题: {', '.join(metadata.tags)}\n推荐语: {metadata.synopsis}",
            },
        )
