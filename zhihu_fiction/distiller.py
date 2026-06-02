"""技能蒸馏器：从热门内容中提取创作模式，生成技能卡。

流程：
1. 读取抓取的原始热门内容
2. 调用 LLM 逐篇分析，提取创作特征
3. 按题材聚合，生成该题材的「创作技能卡」
4. 存储为标准 Markdown 格式
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from langchain_core.language_models import BaseChatModel

from .config import APP_ROOT, Settings
from .llm import create_llm
from .skills_store import SkillsStore

SKILLS_DIR = APP_ROOT / "data" / "skills"

DISTILL_SINGLE_PROMPT = """你是知乎爆款小说分析专家，请分析以下热门文章，提取其创作特征。

文章信息：
- 标题：{title}
- 点赞/热度：{score}
- 内容摘要：{excerpt}

请分析并返回以下维度的特征（用中文，简洁具体）：

1) **题材分类**：悬疑/言情/职场/古代/科幻/现实/脑洞/历史/其他（选1-2个最匹配的）
2) **开篇钩子类型**：悬念型/反转型/共鸣型/冲突型/疑问型/场景沉浸型
3) **叙事视角**：第一人称/第三人称/对话体/日记体/其他
4) **核心吸引力**：为什么读者会点赞（1-2句话）
5) **情节节奏**：短平快/层层递进/反转密集/情绪递进
6) **标题公式**：提取标题中可复用的句式模板
7) **互动技巧**：是否有引导点赞/评论/关注的手法

请以 JSON 格式输出，键名: genre, hook_type, narrative_pov, core_appeal, pace, title_formula, engagement_tactic
"""

MERGE_SKILL_PROMPT = """你是知乎爆款小说创作导师。你之前已经为「{genre}」题材总结了一份技能卡，现在又分析了新的热门文章，有了新的发现。

## 已有的技能卡

{existing_card}

## 新分析得到的发现

{new_card}

请将两者合并为一份**更完善的技能卡**。合并原则：
1. 保留两份中所有的独特洞察，不丢失任何信息
2. 重复的部分只保留更详细的那个版本
3. 如果新旧内容有矛盾，以新的为准（新数据更有参考价值）
4. 保持原有的章节结构（目标读者画像、核心吸引力、标题公式、开篇钩子模式、情节节奏模板、人物设定常用类型、结尾技巧、高赞文章共性总结）
5. 在文末增加一节「## 更新记录」，注明本次合并新增了哪些要点（列3-5条即可）
"""

DISTILL_AGGREGATE_PROMPT = """你是知乎爆款小说创作导师，请根据以下多篇「{genre}」题材的热门文章分析结果，总结该题材的创作技能卡。

多篇文章特征汇总：
{features}

请生成一份完整的创作技能卡，包含以下部分：

## 题材：{genre}

### 目标读者画像
- 主要读者群体特征
- 阅读场景（睡前/通勤/摸鱼等）
- 核心阅读动机

### 核心吸引力
- 这个题材的根本魅力在哪
- 读者为什么欲罢不能

### 标题公式
- 3-5 个可复用的标题模板（用 XX 表示可变部分）

### 开篇钩子模式
- 最有效的开篇方式及示例

### 情节节奏模板
- 推荐的故事结构
- 爆点/反转密度建议（每千字至少 X 个）

### 人物设定常用类型
- 主角/配角的常见原型

### 结尾技巧
- 如何让读者评论、转发、关注

### 高赞文章共性总结
- 最重要的 3 条规律
"""


def _parse_genre(text: str) -> str:
    """尝试从分析文本中提取题材"""
    match = re.search(r"[题材分类][：:]\s*(.+?)(?:\n|$)", text)
    if match:
        return match.group(1).strip().split("/")[0].strip()
    return "未分类"


def _try_parse_json(text: str) -> dict | None:
    """尝试从 LLM 输出中提取 JSON"""
    # 尝试匹配 JSON 块
    match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None


def distill_single(llm: BaseChatModel, article: dict) -> dict:
    """对单篇文章进行特征蒸馏"""
    title = article.get("title", "无标题")
    score = article.get("hot_score", article.get("votes", "未知"))
    excerpt = article.get("excerpt", article.get("content", ""))[:1500]

    prompt = DISTILL_SINGLE_PROMPT.format(title=title, score=score, excerpt=excerpt)
    result = llm.invoke(prompt)

    content = result.content if hasattr(result, "content") else str(result)
    if isinstance(content, list):
        content = "".join(str(item.get("text", item)) if isinstance(item, dict) else str(item) for item in content)

    parsed = _try_parse_json(content)
    if parsed:
        parsed["_title"] = title
        parsed["_score"] = str(score)
        return parsed

    return {
        "genre": _parse_genre(content),
        "hook_type": "",
        "narrative_pov": "",
        "core_appeal": "",
        "pace": "",
        "title_formula": "",
        "engagement_tactic": "",
        "_title": title,
        "_score": str(score),
        "_raw": content[:1000],
    }


def distill_aggregate(llm: BaseChatModel, genre: str, features: list[dict]) -> str:
    """聚合同题材多篇文章的特征，生成技能卡"""
    features_text = "\n\n---\n\n".join(
        f"文章 {i+1}: {f.get('_title', '未知')} (热度: {f.get('_score', '?')})\n"
        + "\n".join(f"- {k}: {v}" for k, v in f.items() if not k.startswith("_"))
        for i, f in enumerate(features)
    )

    prompt = DISTILL_AGGREGATE_PROMPT.format(genre=genre, features=features_text)
    result = llm.invoke(prompt)

    content = result.content if hasattr(result, "content") else str(result)
    if isinstance(content, list):
        content = "".join(str(item.get("text", item)) if isinstance(item, dict) else str(item) for item in content)

    return content


class Distiller:
    """技能蒸馏器，协调单篇分析和聚合生成"""

    def __init__(self, settings: Settings) -> None:
        self.llm = create_llm(settings, temperature=0.3)

    def distill_from_articles(self, articles: list[dict]) -> dict[str, list[dict]]:
        """从文章列表蒸馏技能，返回按题材分组的特征列表"""
        genre_groups: dict[str, list[dict]] = {}
        total = len(articles)
        print(f"[蒸馏] 开始分析 {total} 篇文章...")

        for i, article in enumerate(articles):
            print(f"[蒸馏] ({i + 1}/{total}) {article.get('title', '?')[:40]}...")
            try:
                feature = distill_single(self.llm, article)
                genre = feature.get("genre", "未分类")
                genre_groups.setdefault(genre, []).append(feature)
            except Exception as exc:
                print(f"[蒸馏] 分析失败: {exc}")
                continue

        print(f"[蒸馏] 分析完成，共 {len(genre_groups)} 个题材: {list(genre_groups.keys())}")
        return genre_groups

    def generate_skill_cards(self, genre_groups: dict[str, list[dict]]) -> dict[str, str]:
        """为每个题材生成技能卡"""
        skill_cards: dict[str, str] = {}
        for genre, features in genre_groups.items():
            print(f"[蒸馏] 生成 [{genre}] 技能卡（{len(features)} 篇文章）...")
            try:
                card = distill_aggregate(self.llm, genre, features)
                skill_cards[genre] = card
            except Exception as exc:
                print(f"[蒸馏] 聚合失败 [{genre}]: {exc}")
                continue

        return skill_cards

    def _merge_skill_cards(self, genre: str, existing: str, new: str) -> str:
        """用 LLM 合并已有的技能卡和新蒸馏的发现"""
        prompt = MERGE_SKILL_PROMPT.format(
            genre=genre,
            existing_card=existing,
            new_card=new,
        )
        try:
            result = self.llm.invoke(prompt)
            content = result.content if hasattr(result, "content") else str(result)
            if isinstance(content, list):
                content = "".join(
                    str(item.get("text", item)) if isinstance(item, dict) else str(item)
                    for item in content
                )
            print(f"[蒸馏] 已合并 [{genre}] 的新旧技能卡")
            return content
        except Exception as exc:
            print(f"[蒸馏] 合并 [{genre}] 失败（{exc}），使用新版本")
            return new

    def save_skill_cards(self, skill_cards: dict[str, str]) -> list[Path]:
        """将技能卡保存到 data/skills/ 目录。同名题材会自动合并而非覆盖。"""
        SKILLS_DIR.mkdir(parents=True, exist_ok=True)
        saved: list[Path] = []
        for genre, content in skill_cards.items():
            safe_genre = "".join(c for c in genre if c.isalnum() or c in ("-", "_"))
            filepath = SKILLS_DIR / f"{safe_genre}.md"

            if filepath.exists():
                existing = filepath.read_text(encoding="utf-8")
                merged = self._merge_skill_cards(genre, existing, content)
                filepath.write_text(merged, encoding="utf-8")
                print(f"[蒸馏] 已合并: {filepath.name}（该题材此前已有技能卡）")
            else:
                filepath.write_text(content, encoding="utf-8")
                print(f"[蒸馏] 已保存: {filepath.name}")

            saved.append(filepath)
        return saved

    def run_full_pipeline(self, articles: list[dict]) -> SkillsStore:
        """执行完整的蒸馏流程：分析 → 聚合 → 保存 → 返回技能库"""
        genre_groups = self.distill_from_articles(articles)
        skill_cards = self.generate_skill_cards(genre_groups)
        self.save_skill_cards(skill_cards)
        return SkillsStore()
