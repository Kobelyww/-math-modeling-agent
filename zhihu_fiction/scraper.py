"""知乎内容抓取器：热榜 API、话题搜索、高赞内容采集。

数据源优先级:
1. 知乎移动端 API（热榜）—— 最稳定，优先使用
2. 知乎网页端 —— 需要 cookie，反爬严格
3. 手动输入 —— 作为最终兜底方案

所有抓取结果缓存 1 小时。
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import requests

from .config import APP_ROOT

SCRAPED_DIR = APP_ROOT / "data" / "scraped"
CACHE_DIR = SCRAPED_DIR / ".cache"
CACHE_TTL = timedelta(hours=1)

# 知乎移动端 API base
ZHIHU_API_BASE = "https://api.zhihu.com"

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/16.0 Mobile/15E148 Safari/604.1"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh-Hans;q=0.9",
    "X-Requested-With": "fetch",
    "x-api-version": "3.0.40",
})

REQUEST_DELAY = 1.5  # seconds between requests


def _gen_x_zse_96(api_url: str) -> str:
    """生成简化的 x-zse-96 签名。

    注意: 完全逆向知乎的 x-zse-96 签名算法很复杂(WebAssembly V8 沙箱),
    这里提供一个不完整版本。对于热榜 API，大部分情况下不需要签名也能访问。
    如果被要求签名，回退到手动输入方案。
    """
    return "2.0_" + hashlib.md5(f"{api_url}+{uuid.uuid4().hex[:8]}".encode()).hexdigest()


def _cache_key(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


def _cache_get(url: str) -> dict | None:
    key = _cache_key(url)
    cache_file = CACHE_DIR / f"{key}.json"
    if not cache_file.exists():
        return None
    try:
        data = json.loads(cache_file.read_text())
        cached_at = datetime.fromisoformat(data["cached_at"])
        if datetime.now() - cached_at < CACHE_TTL:
            return data["content"]
    except (json.JSONDecodeError, KeyError, ValueError):
        pass
    return None


def _cache_set(url: str, content: list[dict]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = _cache_key(url)
    cache_file = CACHE_DIR / f"{key}.json"
    cache_file.write_text(json.dumps({
        "url": url,
        "cached_at": datetime.now().isoformat(),
        "content": content,
    }, ensure_ascii=False, indent=2))


def _api_get(path: str, params: dict | None = None, need_sign: bool = False) -> dict | None:
    """调用知乎 API"""
    url = f"{ZHIHU_API_BASE}{path}"
    headers = {}
    if need_sign:
        headers["x-zse-96"] = _gen_x_zse_96(path)
        headers["x-zse-93"] = "101_3_3.0"

    try:
        time.sleep(REQUEST_DELAY)
        resp = SESSION.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        print(f"[scraper] API 请求失败: {path} — {exc}")
        return None


def _html_get(url: str, params: dict | None = None) -> str | None:
    """直接请求网页（需要处理反爬）"""
    from bs4 import BeautifulSoup

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://www.zhihu.com/",
    }
    try:
        time.sleep(REQUEST_DELAY * 2)
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        return resp.text
    except requests.RequestException as exc:
        print(f"[scraper] 网页请求失败: {url} — {exc}")
        return None


# ============================================================
# 热榜抓取 (API 优先)
# ============================================================

def scrape_zhihu_hot(limit: int = 50) -> list[dict]:
    """抓取知乎热榜。

    使用知乎公开 API (api.zhihu.com/topstory/hot-list), 无需认证。
    返回话题标题、热度、摘要和链接。
    """
    cache_key = "zhihu_hot_list"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    # 方案一: 公开热榜 API (无需认证)
    data = _api_get("/topstory/hot-list", params={"limit": limit})
    if data:
        items = _parse_hotlist_v2(data)
        if items:
            _cache_set(cache_key, items)
            return items

    # 方案二: 老版热榜 API
    data = _api_get("/feed/topstory/hot-lists/total", params={"limit": limit})
    if data:
        items = _parse_hotlist_v1(data)
        if items:
            _cache_set(cache_key, items)
            return items

    # 方案三: 网页端降级
    html = _html_get("https://www.zhihu.com/hot")
    if html:
        items = _parse_hotlist_html(html)
        if items:
            _cache_set(cache_key, items)
            return items

    # 兜底提示
    return [{
        "title": "知乎热榜抓取失败",
        "url": "",
        "hot_score": 0,
        "excerpt": (
            "知乎反爬保护已触发。建议：\n"
            "1. 将知乎 App 热榜截图手动抄录到 data/scraped/ 目录\n"
            "2. 使用 /manual 命令手动输入热门话题\n"
            "3. 安装 playwright 后使用浏览器自动化抓取"
        ),
        "source": "fallback",
        "scraped_at": datetime.now().isoformat(),
    }]


def _parse_hotlist_v2(data: dict) -> list[dict]:
    """解析新版热榜 API (/topstory/hot-list) 返回数据"""
    items: list[dict] = []
    entries = data.get("data", [])

    for entry in entries:
        target = entry.get("target", {})
        title = target.get("title", "") or target.get("title_area", {}).get("text", "")
        excerpt = target.get("excerpt", "") or target.get("excerpt_area", {}).get("text", "")

        # 热度来自 detail_text 或 metrics_area
        metric = entry.get("detail_text", "")
        metrics_area = target.get("metrics_area", {})
        if isinstance(metrics_area, dict):
            metric = metrics_area.get("text", metric)

        q_id = target.get("id", "")
        q_type = target.get("type", "")
        if q_type == "question":
            page_url = f"https://www.zhihu.com/question/{q_id}"
        elif q_type == "article":
            page_url = f"https://zhuanlan.zhihu.com/p/{q_id}"
        else:
            page_url = f"https://www.zhihu.com/question/{q_id}"

        if title:
            items.append({
                "title": title,
                "url": page_url,
                "hot_score": _parse_metric(metric) or float(len(items) + 1),
                "excerpt": excerpt[:500] if excerpt else "",
                "source": "zhihu_hot_v2",
                "scraped_at": datetime.now().isoformat(),
            })

    return items


def _parse_hotlist_v1(data: dict) -> list[dict]:
    """解析老版热榜 API (/feed/topstory/hot-lists/total) 返回数据"""
    items: list[dict] = []
    entries = data.get("data", [])

    for entry in entries:
        target = entry.get("target", {})
        title = target.get("title", "") or target.get("title_area", {}).get("text", "")
        excerpt = target.get("excerpt", "") or target.get("excerpt_area", {}).get("text", "")
        metric = target.get("metrics_area", {}).get("text", "")
        if not metric:
            metric = entry.get("detail_text", "")

        q_id = target.get("id", "")
        page_url = f"https://www.zhihu.com/question/{q_id}" if q_id else ""

        if title:
            items.append({
                "title": title,
                "url": page_url,
                "hot_score": _parse_metric(metric),
                "excerpt": excerpt[:300] if excerpt else "",
                "source": "zhihu_hot_v1",
                "scraped_at": datetime.now().isoformat(),
            })

    return items


def _parse_hotlist_html(html: str) -> list[dict]:
    """解析热榜网页 HTML"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    items: list[dict] = []

    for card in soup.select(".HotItem, .HotList-item"):
        title_el = card.select_one(".HotItem-title, h2")
        excerpt_el = card.select_one(".HotItem-excerpt, p")
        metrics_el = card.select_one(".HotItem-metrics, .HotItem-action")

        title = title_el.get_text(strip=True) if title_el else ""
        excerpt = excerpt_el.get_text(strip=True) if excerpt_el else ""
        metric = metrics_el.get_text(strip=True) if metrics_el else "0"

        link_el = title_el.find("a") if title_el else None
        link = link_el.get("href", "") if link_el else ""
        if link and not link.startswith("http"):
            link = "https://www.zhihu.com" + link

        if title:
            items.append({
                "title": title,
                "url": link,
                "hot_score": _parse_metric(metric),
                "excerpt": excerpt[:300],
                "source": "zhihu_hot_html",
                "scraped_at": datetime.now().isoformat(),
            })

    return items


def _parse_metric(text: str) -> float:
    """解析热度/点赞数: '1234 万热度' → 12340000, '567 回答' → 567"""
    import re
    text = text.strip().replace(",", "")
    match = re.match(r"([\d.]+)\s*万?", text)
    if not match:
        return 0.0
    num = float(match.group(1))
    return num * 10000 if "万" in text else num


# ============================================================
# 话题/问答搜索
# ============================================================

def search_zhihu_topic(keyword: str, max_results: int = 20) -> list[dict]:
    """搜索知乎问题/话题，获取高赞问题列表。

    使用知乎搜索建议 API: /search/suggest
    """
    cache_url = f"zhihu_search:{keyword}"
    cached = _cache_get(cache_url)
    if cached:
        return cached[:max_results]

    # 搜索建议 API
    data = _api_get("/search/suggest", params={"q": keyword, "limit": min(max_results, 20)})
    if data:
        items = _parse_search_suggest(data, keyword)
        if items:
            _cache_set(cache_url, items)
            return items

    # 网页端降级
    html = _html_get("https://www.zhihu.com/search", params={"type": "content", "q": keyword})
    if html:
        items = _parse_search_html(html, keyword)
        if items:
            _cache_set(cache_url, items)
            return items

    return [{
        "title": f"搜索 '{keyword}' 失败",
        "url": "",
        "excerpt": "API 和网页请求均被拦截，请稍后重试或使用手动输入。",
        "source": "error",
        "scraped_at": datetime.now().isoformat(),
    }]


def _parse_search_suggest(data: dict, keyword: str) -> list[dict]:
    """解析搜索建议 API 返回"""
    items: list[dict] = []
    entries = data.get("suggest", [])

    for entry in entries:
        query = entry.get("query", "")
        if query and query != keyword:
            items.append({
                "title": query,
                "url": f"https://www.zhihu.com/search?q={query}&type=topic",
                "hot_score": 0,
                "excerpt": f"知乎热搜话题: {query}",
                "source": "zhihu_suggest",
                "keyword": keyword,
                "scraped_at": datetime.now().isoformat(),
            })

    return items


def _parse_search_html(html: str, keyword: str = "") -> list[dict]:
    """解析搜索页 HTML"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    items: list[dict] = []

    for card in soup.select(".List-item, .SearchResultCard"):
        title_el = card.select_one("h2, .ContentItem-title a")
        excerpt_el = card.select_one(".RichText, .SearchResult-excerpt")
        vote_el = card.select_one(".VoteButton--up, .ContentItem-vote")

        title = title_el.get_text(strip=True) if title_el else ""
        excerpt = excerpt_el.get_text(strip=True)[:500] if excerpt_el else ""
        votes = _parse_metric(vote_el.get_text(strip=True) if vote_el else "0")

        if title:
            items.append({
                "title": title,
                "url": "",
                "votes": votes,
                "excerpt": excerpt,
                "keyword": keyword,
                "source": "zhihu_search_html",
                "scraped_at": datetime.now().isoformat(),
            })

    return items


# ============================================================
# 高赞回答抓取（需要 cookie，提示用户配置）
# ============================================================

def fetch_question_answers(question_id: str, limit: int = 10) -> list[dict]:
    """获取指定问题的答案列表（按赞同数排序）。

    注意: 此接口需要有效的知乎 cookie 才能获取完整数据。
    可在项目根目录 .env 中设置 ZHIHU_COOKIE 变量。
    """
    import os
    cookie = os.getenv("ZHIHU_COOKIE", "")
    if not cookie:
        print("[scraper] 未设置 ZHIHU_COOKIE, 尝试无认证访问...")

    url = f"{ZHIHU_API_BASE}/v4/questions/{question_id}/feeds"
    params = {
        "include": "content,excerpt,voteup_count,comment_count",
        "limit": limit,
        "offset": 0,
    }
    headers = {}
    if cookie:
        headers["Cookie"] = cookie

    try:
        time.sleep(REQUEST_DELAY)
        resp = SESSION.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        items: list[dict] = []
        for entry in data.get("data", []):
            target = entry.get("target", {})
            content = target.get("content", "")
            excerpt = target.get("excerpt", "")
            voteup = entry.get("voteup_count", target.get("voteup_count", 0))

            # 清理 HTML
            clean_excerpt = _strip_html(excerpt or content)[:500]

            items.append({
                "title": target.get("question", {}).get("title", "")[:80],
                "url": f"https://www.zhihu.com/question/{question_id}/answer/{target.get('id', '')}",
                "votes": voteup,
                "excerpt": clean_excerpt,
                "content": _strip_html(content)[:2000] if content else clean_excerpt,
                "source": "zhihu_answer",
                "scraped_at": datetime.now().isoformat(),
            })
        return items
    except Exception as exc:
        print(f"[scraper] 获取回答失败: {exc}")
        return []


def _strip_html(text: str) -> str:
    """去除 HTML 标签"""
    import re
    text = re.sub(r"<[^>]+>", "", text or "")
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return " ".join(text.split())


# ============================================================
# 文件管理
# ============================================================

def save_scraped_content(items: list[dict], filename: str) -> str:
    """将抓取的内容保存到 data/scraped/ 目录"""
    SCRAPED_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(c for c in filename if c.isalnum() or c in ("-", "_"))
    filepath = SCRAPED_DIR / f"{safe_name}.json"
    filepath.write_text(json.dumps(items, ensure_ascii=False, indent=2))
    return str(filepath)


def list_scraped_files() -> list[Path]:
    """列出所有已抓取的内容文件"""
    if not SCRAPED_DIR.exists():
        return []
    return sorted(SCRAPED_DIR.glob("*.json"))


def load_scraped_file(filepath: str | Path) -> list[dict]:
    """加载已抓取的内容文件"""
    path = Path(filepath)
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"[scraper] 加载失败: {path} — {exc}")
        return []


# ============================================================
# 手动输入入口
# ============================================================

def manual_entry(title: str, excerpt: str = "", hot_score: float = 0) -> str:
    """手动添加一篇热门文章"""
    item = {
        "title": title,
        "url": "",
        "hot_score": hot_score,
        "excerpt": excerpt,
        "source": "manual",
        "scraped_at": datetime.now().isoformat(),
    }
    return save_scraped_content([item], f"manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
