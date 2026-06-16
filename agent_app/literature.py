"""Literature search tools: arXiv, Semantic Scholar, and paper download.

All APIs are free and require no API key.
"""

from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from langchain_core.tools import tool

from .config import APP_ROOT

KNOWLEDGE_DIR = APP_ROOT.parent / "knowledge_base"

# ---------------------------------------------------------------------------
# arXiv API
# ---------------------------------------------------------------------------

ARXIV_API = "http://export.arxiv.org/api/query"
ARXIV_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


def _extract_text(parent: ET.Element, tag: str) -> str:
    el = parent.find(tag, ARXIV_NS)
    return " ".join(el.itertext()).strip() if el is not None else ""


def _search_arxiv_raw(query: str, max_results: int = 10) -> list[dict]:
    params = urllib.parse.urlencode({
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
    })
    url = f"{ARXIV_API}?{params}"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            root = ET.fromstring(resp.read())
    except Exception as exc:
        return [{"error": f"arXiv API request failed: {exc}"}]

    papers: list[dict] = []
    for entry in root.findall("atom:entry", ARXIV_NS):
        authors = [
            _extract_text(a, "atom:name") for a in entry.findall("atom:author", ARXIV_NS)
        ]
        pdf_url = ""
        for link in entry.findall("atom:link", ARXIV_NS):
            if link.get("title") == "pdf":
                pdf_url = link.get("href", "")
        arxiv_id = _extract_text(entry, "atom:id").split("/abs/")[-1]
        papers.append({
            "source": "arxiv",
            "id": arxiv_id,
            "title": _extract_text(entry, "atom:title"),
            "authors": authors,
            "year": _extract_text(entry, "atom:published")[:4],
            "abstract": _extract_text(entry, "atom:summary"),
            "pdf_url": pdf_url,
            "page_url": f"https://arxiv.org/abs/{arxiv_id}",
        })
    return papers


# ---------------------------------------------------------------------------
# Semantic Scholar API
# ---------------------------------------------------------------------------

S2_API = "https://api.semanticscholar.org/graph/v1/paper/search"


def _search_s2_raw(query: str, max_results: int = 10, retry: bool = True) -> list[dict]:
    fields = "title,authors,abstract,year,externalIds,url,openAccessPdf"
    params = urllib.parse.urlencode({"query": query, "limit": max_results, "fields": fields})
    url = f"{S2_API}?{params}"
    import json
    import time

    for attempt in range(2 if retry else 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "AgentApp/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt == 0:
                time.sleep(2)
                continue
            return [{"error": f"Semantic Scholar API error: {exc}"}]
        except Exception as exc:
            return [{"error": f"Semantic Scholar API request failed: {exc}"}]

    papers: list[dict] = []
    for p in data.get("data", []):
        authors = [a.get("name", "") for a in p.get("authors", [])]
        pdf_url = ""
        oa = p.get("openAccessPdf")
        if oa and oa.get("url"):
            pdf_url = oa["url"]
        papers.append({
            "source": "semantic_scholar",
            "id": p.get("paperId", ""),
            "title": p.get("title", ""),
            "authors": authors,
            "year": str(p.get("year", "")) if p.get("year") else "",
            "abstract": p.get("abstract", "") or "",
            "pdf_url": pdf_url,
            "page_url": p.get("url", ""),
        })
    return papers


# ---------------------------------------------------------------------------
# Crossref API  (free, no key, generous rate limits)
# ---------------------------------------------------------------------------

CROSSREF_API = "https://api.crossref.org/works"


def _search_crossref_raw(query: str, max_results: int = 10) -> list[dict]:
    import json
    import time

    params = urllib.parse.urlencode({"query": query, "rows": max_results})
    url = f"{CROSSREF_API}?{params}"
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "AgentApp/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt == 0:
                time.sleep(2)
                continue
            return [{"error": f"Crossref API error: {exc}"}]
        except Exception as exc:
            return [{"error": f"Crossref API request failed: {exc}"}]

    papers: list[dict] = []
    for item in data.get("message", {}).get("items", []):
        authors = [
            a.get("given", "") + " " + a.get("family", "")
            for a in item.get("author", [])
        ]
        title = item.get("title", [""])[0] if item.get("title") else ""
        abstract = _strip_xml_tags(item.get("abstract", ""))
        year = str(item.get("published-print", {}).get("date-parts", [[0]])[0][0])
        papers.append({
            "source": "crossref",
            "id": item.get("DOI", ""),
            "title": _strip_xml_tags(title),
            "authors": authors,
            "year": year,
            "abstract": abstract[:800] if abstract else "",
            "pdf_url": "",
            "page_url": f"https://doi.org/{item.get('DOI', '')}" if item.get("DOI") else "",
        })
    return papers


# ---------------------------------------------------------------------------
# Language-switch helper
# ---------------------------------------------------------------------------


def _detect_lang(query: str) -> str:
    """Rough detection: returns 'zh' or 'en'."""
    zh_count = sum(1 for c in query if "一" <= c <= "鿿")
    return "zh" if zh_count > len(query) * 0.3 else "en"


def _choose_query(original: str) -> tuple[str, str]:
    """Return (arxiv_query, s2_query). arXiv is better for English, so for Chinese
    queries we also search English-translatable terms via S2."""
    lang = _detect_lang(original)
    if lang == "zh":
        # for Chinese queries, search both sources with original text
        # S2 handles Chinese better; arXiv needs English
        return original, original
    return original, original


# ---------------------------------------------------------------------------
# Paper download & KB integration
# ---------------------------------------------------------------------------


def _download_pdf(url: str, filename: str) -> Path | None:
    """Download a PDF and save to knowledge_base. Returns the saved path."""
    safe_name = "".join(c for c in filename if c.isalnum() or c in ("-", "_", " "))
    safe_name = safe_name.strip().replace(" ", "_")[:100]
    if not safe_name:
        safe_name = "downloaded_paper"
    path = KNOWLEDGE_DIR / f"{safe_name}.pdf"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AgentApp/1.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            path.write_bytes(resp.read())
        return path
    except Exception:
        return None


# ===================== LangChain tools =====================


def _strip_xml_tags(text: str) -> str:
    """Remove XML/HTML tags from text."""
    import re
    return re.sub(r"<[^>]+>", "", text).strip()


@tool
def search_crossref(query: str, max_results: int = 10) -> str:
    """Search Crossref for academic papers by keyword. Returns title, authors,
    year, abstract, and DOI link. Free and open, supports both English
    and Chinese queries. Good fallback when other sources are rate-limited.

    Example: search_crossref('traffic flow optimization')
    """
    if max_results > 20:
        max_results = 20
    papers = _search_crossref_raw(query, max_results=max_results)
    if not papers:
        return "No results found."
    if "error" in papers[0]:
        return papers[0]["error"]

    lines = [f"Crossref results for: {query}  ({len(papers)} papers)\n"]
    for i, p in enumerate(papers, 1):
        authors = ", ".join(p["authors"][:3])
        if len(p["authors"]) > 3:
            authors += " et al."
        lines.append(f"--- {i} ---")
        lines.append(f"Title: {p['title']}")
        lines.append(f"Authors: {authors}")
        lines.append(f"Year: {p['year']}")
        abstract = _strip_xml_tags(p["abstract"].replace("\n", " "))[:400]
        lines.append(f"Abstract: {abstract}")
        if p["page_url"]:
            lines.append(f"DOI: {p['page_url']}")
        lines.append("")
    return "\n".join(lines)[:4000]


@tool
def search_arxiv(query: str, max_results: int = 10) -> str:
    """Search arXiv for academic papers by keyword. Returns title, authors,
    year, abstract, and PDF download link for each result. Best for English
    queries in math, CS, physics, and related fields.

    Example: search_arxiv('traffic flow optimization model')
    """
    if max_results > 20:
        max_results = 20
    papers = _search_arxiv_raw(query, max_results=max_results)
    if not papers:
        return "No results found."
    if "error" in papers[0]:
        return papers[0]["error"]

    lines = [f"arXiv results for: {query}  ({len(papers)} papers)\n"]
    for i, p in enumerate(papers, 1):
        authors = ", ".join(p["authors"][:3])
        if len(p["authors"]) > 3:
            authors += " et al."
        lines.append(f"--- {i} ---")
        lines.append(f"Title: {p['title']}")
        lines.append(f"Authors: {authors}")
        lines.append(f"Year: {p['year']}")
        abstract = p["abstract"].replace("\n", " ")[:400]
        lines.append(f"Abstract: {abstract}")
        if p["pdf_url"]:
            lines.append(f"PDF: {p['pdf_url']}")
        lines.append(f"Page: {p['page_url']}")
        lines.append("")
    return "\n".join(lines)[:4000]


@tool
def search_semantic_scholar(query: str, max_results: int = 10) -> str:
    """Search Semantic Scholar for academic papers by keyword. Returns title,
    authors, year, abstract, and open-access PDF link (when available).
    Supports both English and Chinese queries.

    Example: search_semantic_scholar('充电站布局优化')
    """
    if max_results > 20:
        max_results = 20
    papers = _search_s2_raw(query, max_results=max_results)
    if not papers:
        return "No results found."
    if "error" in papers[0]:
        return papers[0]["error"]

    lines = [f"Semantic Scholar results for: {query}  ({len(papers)} papers)\n"]
    for i, p in enumerate(papers, 1):
        authors = ", ".join(p["authors"][:3])
        if len(p["authors"]) > 3:
            authors += " et al."
        lines.append(f"--- {i} ---")
        lines.append(f"Title: {p['title']}")
        lines.append(f"Authors: {authors}")
        lines.append(f"Year: {p['year']}")
        abstract = p["abstract"].replace("\n", " ")[:400]
        lines.append(f"Abstract: {abstract}")
        if p["pdf_url"]:
            lines.append(f"OpenAccess PDF: {p['pdf_url']}")
        lines.append(f"Page: {p['page_url']}")
        lines.append("")
    return "\n".join(lines)[:4000]


@tool
def fetch_paper_to_kb(pdf_url: str, title: str = "downloaded_paper") -> str:
    """Download an academic paper PDF and save it to the knowledge base
    for RAG indexing. Provide the direct PDF URL and a short title.

    After downloading, rebuild the RAG index to make it searchable.
    Example: fetch_paper_to_kb('https://arxiv.org/pdf/2401.12345.pdf', 'TrafficFlowOptimization')
    """
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    path = _download_pdf(pdf_url, title)
    if path is None:
        return f"Failed to download PDF from: {pdf_url}"
    return (
        f"Downloaded: {path.name}  ({path.stat().st_size} bytes)\n"
        f"Saved to: {path}\n\n"
        f"To make it searchable, rebuild the RAG index via the sidebar or call build_index()."
    )