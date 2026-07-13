"""Standalone LangChain tools for the fiction production workflow."""

from __future__ import annotations

from datetime import datetime

from langchain_core.tools import tool

from zhihu_fiction.core.config import APP_ROOT
from zhihu_fiction.fiction.scraper import (
    list_scraped_files,
    load_scraped_file,
    save_scraped_content,
    scrape_zhihu_hot,
    search_zhihu_topic,
)
from zhihu_fiction.fiction.skills_store import SkillsStore

OUTPUT_DIR = APP_ROOT / "output"


@tool
def scrape_hot() -> str:
    """抓取知乎热榜，返回当前最热门的话题列表（含热度和摘要）。"""
    items = scrape_zhihu_hot()
    if not items:
        return "抓取失败，知乎可能进行了反爬保护。请稍后重试或手动输入内容。"

    saved_path = save_scraped_content(items, f"hot_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    lines = [f"抓取到 {len(items)} 条热门话题，已保存至 {saved_path}\n"]
    for i, item in enumerate(items[:15], 1):
        lines.append(f"{i}. [{item.get('hot_score', 0):.0f}] {item['title']}")
        if item.get("excerpt"):
            lines.append(f"   {item['excerpt'][:100]}")
    return "\n".join(lines)


@tool
def search_topic(keyword: str) -> str:
    """搜索知乎特定关键词的话题和内容。"""
    items = search_zhihu_topic(keyword)
    if not items:
        return f"未找到与 '{keyword}' 相关的内容，或请求被反爬拦截。"

    saved_path = save_scraped_content(items, f"search_{keyword}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    lines = [f"搜索 '{keyword}' 找到 {len(items)} 条结果，已保存至 {saved_path}\n"]
    for i, item in enumerate(items[:10], 1):
        lines.append(f"{i}. {item['title']}")
        if item.get("excerpt"):
            lines.append(f"   {item['excerpt'][:100]}")
    return "\n".join(lines)


@tool
def list_scraped() -> str:
    """列出所有已抓取的内容文件。"""
    files = list_scraped_files()
    if not files:
        return "暂无已抓取的内容。使用 scrape_hot 或 search_topic 抓取内容。"
    lines = [f"已抓取 {len(files)} 个文件:\n"]
    for f in files:
        size_kb = f.stat().st_size / 1024
        lines.append(f"  - {f.name} ({size_kb:.1f} KB)")
    return "\n".join(lines)


@tool
def read_scraped(filename: str) -> str:
    """读取已抓取的内容文件，返回前 20 条记录的摘要。"""
    path = APP_ROOT / "data" / "scraped" / filename
    if not path.exists():
        return f"文件不存在: {filename}"
    items = load_scraped_file(path)
    if not items:
        return "文件为空或格式错误。"
    lines = [f"文件: {filename} ({len(items)} 条记录)\n"]
    for i, item in enumerate(items[:20], 1):
        lines.append(f"{i}. {item.get('title', '?')}")
        excerpt = item.get("excerpt", "")
        if excerpt:
            lines.append(f"   {excerpt[:150]}")
    return "\n".join(lines)


@tool
def save_article(title: str, content: str) -> str:
    """保存生成的小说文章到 output 目录。"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    safe_title = "".join(c for c in title if c.isalnum() or c in ("-", "_", " "))
    safe_title = safe_title.strip().replace(" ", "_")[:80]
    if not safe_title:
        safe_title = "untitled"
    filepath = OUTPUT_DIR / f"{safe_title}.md"
    filepath.write_text(content.strip() + "\n", encoding="utf-8")
    return f"文章已保存: {filepath}"


@tool
def read_skill(genre: str) -> str:
    """读取指定题材的创作技能卡。例如: read_skill('悬疑')"""
    store = SkillsStore()
    skill = store.get_skill(genre)
    if skill is None:
        available = store.list_genres()
        return f"未找到 [{genre}] 题材的技能卡。可用题材: {', '.join(available) if available else '无'}"
    return skill


@tool
def list_skills() -> str:
    """列出所有已蒸馏的创作技能卡题材。"""
    store = SkillsStore()
    genres = store.list_genres()
    if not genres:
        return "技能库为空。请先抓取知乎内容，再运行蒸馏流程生成技能卡。"
    return f"已掌握 {len(genres)} 个题材的创作技能:\n" + "\n".join(f"  - {g}" for g in genres)


@tool
def current_time() -> str:
    """获取当前时间。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


TOOLS = [
    scrape_hot,
    search_topic,
    list_scraped,
    read_scraped,
    save_article,
    read_skill,
    list_skills,
    current_time,
]

__all__ = [
    "OUTPUT_DIR",
    "TOOLS",
    "current_time",
    "list_scraped",
    "list_skills",
    "read_scraped",
    "read_skill",
    "save_article",
    "scrape_hot",
    "search_topic",
]
