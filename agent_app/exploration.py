"""Exploration tools — inspired by Claude Code's file/workspace exploration capabilities.

These tools give agents the ability to explore their environment before
committing to solutions, enabling a "measure twice, cut once" workflow.

Tool categories:
  - File system: read_file, search_files, search_content, list_directory
  - Web: web_search (DuckDuckGo, no API key), web_fetch (urllib)
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from langchain_core.tools import tool


# ============================================================================
# File System Exploration Tools
# ============================================================================

MAX_FILE_SIZE = 1_000_000  # 1MB
DEFAULT_READ_LIMIT = 2000  # lines


@tool
def read_file(filepath: str, offset: int = 0, limit: int = DEFAULT_READ_LIMIT) -> str:
    """Read a file from the local filesystem. Returns file content with line numbers.

    Args:
        filepath: Absolute or relative path to the file
        offset: Line number to start reading from (0-indexed, default 0)
        limit: Maximum number of lines to read (default 2000)

    Returns:
        File content with line number prefixes, or an error message.

    Example: read_file('/path/to/file.py', offset=100, limit=50)
    """
    path = Path(filepath).expanduser().resolve()

    if not path.exists():
        return f"File not found: {filepath}"

    if path.is_dir():
        return f"Path is a directory, not a file: {filepath}"

    if path.stat().st_size > MAX_FILE_SIZE:
        return (
            f"File too large: {path.stat().st_size} bytes (max {MAX_FILE_SIZE}). "
            f"Use offset and limit to read specific sections."
        )

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception as exc:
        return f"Failed to read file: {exc}"

    total_lines = len(lines)
    if offset >= total_lines:
        return f"Offset {offset} exceeds total lines {total_lines}."

    end = min(offset + limit, total_lines)
    selected = lines[offset:end]

    if not selected:
        return "(empty file)"

    # Format with line numbers
    out_lines = []
    for i, line in enumerate(selected, start=offset + 1):
        out_lines.append(f"{i:6d}\t{line.rstrip()}")

    header = f"File: {path} (lines {offset + 1}-{end} of {total_lines})"
    return header + "\n" + "\n".join(out_lines)


@tool
def search_files(pattern: str, directory: str = ".", recursive: bool = True) -> str:
    """Find files matching a glob pattern in a directory.

    Like Claude Code's Bash(find) approach — uses fnmatch for pattern matching.

    Args:
        pattern: Glob pattern to match (e.g., '*.py', '**/test_*.py', '*.md')
        directory: Directory to search in (default: current directory)
        recursive: Whether to search subdirectories (default: True)

    Returns:
        Sorted list of matching file paths, or an error message.

    Example: search_files('*.py', '.')
    Example: search_files('test_*.py', 'src/', recursive=True)
    """
    base = Path(directory).expanduser().resolve()

    if not base.exists():
        return f"Directory not found: {directory}"

    if not base.is_dir():
        return f"Not a directory: {directory}"

    matches: list[str] = []
    try:
        if recursive:
            for root, _, files in os.walk(base):
                for fname in files:
                    if fnmatch.fnmatch(fname, pattern):
                        rel = Path(root) / fname
                        matches.append(str(rel.relative_to(base)))
        else:
            for fname in base.iterdir():
                if fname.is_file() and fnmatch.fnmatch(fname.name, pattern):
                    matches.append(fname.name)
    except PermissionError as exc:
        return f"Permission denied: {exc}"

    if not matches:
        return f"No files matching '{pattern}' found in {base}."

    matches.sort()
    count = len(matches)
    result = "\n".join(matches[:500])  # cap output
    suffix = f"\n... and {count - 500} more" if count > 500 else ""
    return f"Found {count} files matching '{pattern}' in {base}:\n{result}{suffix}"


@tool
def search_content(
    query: str,
    directory: str = ".",
    file_pattern: str = "*",
    max_results: int = 50,
    case_sensitive: bool = False,
) -> str:
    """Search for text content within files. Like grep over a directory.

    Args:
        query: Text or regex pattern to search for
        directory: Directory to search in (default: current directory)
        file_pattern: Only search files matching this glob (e.g., '*.py', '*.md')
        max_results: Maximum number of matches to return (default: 50)
        case_sensitive: Whether search is case-sensitive (default: False)

    Returns:
        Matching lines with file path and line number, or an error message.

    Example: search_content('def solve', '.', '*.py')
    Example: search_content('TODO', 'src/', '*.py', max_results=20)
    """
    base = Path(directory).expanduser().resolve()

    if not base.exists():
        return f"Directory not found: {directory}"

    flags = re.IGNORECASE if not case_sensitive else 0

    # Build regex: if query looks like raw text, escape it
    try:
        # Try compiling as-is first (user might pass regex)
        pattern = re.compile(query, flags)
    except re.error:
        # Escape for literal search
        pattern = re.compile(re.escape(query), flags)

    matches: list[str] = []
    files_scanned = 0

    try:
        for filepath in base.rglob(file_pattern):
            if not filepath.is_file():
                continue
            if filepath.stat().st_size > MAX_FILE_SIZE:
                continue
            try:
                files_scanned += 1
                content = filepath.read_text(encoding="utf-8", errors="replace")
                for line_no, line in enumerate(content.splitlines(), 1):
                    if pattern.search(line):
                        rel = filepath.relative_to(base)
                        matches.append(f"{rel}:{line_no}: {line.strip()[:200]}")
                        if len(matches) >= max_results:
                            break
            except Exception:
                continue
            if len(matches) >= max_results:
                break
    except PermissionError:
        pass

    if not matches:
        return f"No matches for '{query}' in {base} (scanned {files_scanned} files)."

    result = "\n".join(matches)
    truncated = f" (truncated at {max_results})" if len(matches) >= max_results else ""
    return f"Found {len(matches)} matches in {base}{truncated} (scanned {files_scanned} files):\n{result}"


@tool
def list_directory(path: str = ".", depth: int = 1) -> str:
    """List the contents of a directory. Shows files and subdirectories.

    Args:
        path: Directory path to list (default: current directory)
        depth: How many levels deep to show (default: 1, max: 3)

    Returns:
        Directory listing with file sizes and type indicators.

    Example: list_directory('.')
    Example: list_directory('output/', depth=2)
    """
    base = Path(path).expanduser().resolve()

    if not base.exists():
        return f"Directory not found: {path}"

    if not base.is_dir():
        return f"Not a directory: {path}"

    depth = min(depth, 3)  # cap depth

    lines = [f"Directory: {base}"]
    _list_recursive(base, base, depth, 0, lines)
    return "\n".join(lines)


def _list_recursive(root: Path, current: Path, max_depth: int, current_depth: int, lines: list[str]) -> None:
    if current_depth > max_depth:
        return

    try:
        entries = sorted(current.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except PermissionError:
        lines.append(f"{'  ' * current_depth}  [permission denied]")
        return

    prefix = "  " * current_depth
    dir_count = 0
    file_count = 0

    for entry in entries:
        if entry.name.startswith(".") and entry.name not in (".",):
            continue  # skip hidden files
        try:
            if entry.is_dir():
                dir_count += 1
                lines.append(f"{prefix}📁 {entry.name}/")
                if current_depth < max_depth:
                    _list_recursive(root, entry, max_depth, current_depth + 1, lines)
            else:
                file_count += 1
                size = entry.stat().st_size
                size_str = _format_size(size)
                lines.append(f"{prefix}  {entry.name} ({size_str})")
        except PermissionError:
            continue

    if current_depth == 0:
        lines.insert(1, f"  {dir_count} dirs, {file_count} files")


def _format_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.0f}{unit}"
        size /= 1024
    return f"{size:.0f}GB"


# ============================================================================
# Web Exploration Tools
# ============================================================================

WEB_SEARCH_TIMEOUT = 15  # seconds
WEB_FETCH_TIMEOUT = 30


@tool
def web_search(query: str, max_results: int = 8) -> str:
    """Search the web using DuckDuckGo (free, no API key required).

    Returns titles, URLs, and snippets for each result. Use this when you
    need to find current information, documentation, or external references.

    Args:
        query: Search query string
        max_results: Maximum number of results (default: 8, max: 15)

    Returns:
        Formatted search results with titles, URLs, and snippets.

    Example: web_search('scipy.optimize.minimize tutorial 2025')
    Example: web_search('MCM ICM mathematical modeling guide')
    """
    max_results = min(max_results, 15)

    try:
        results = _ddg_search(query, max_results=max_results)
    except Exception as exc:
        return f"Web search failed: {exc}"

    if not results:
        return f"No results found for: {query}"

    lines = [f"Web search results for: {query} ({len(results)} results)\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"--- {i} ---")
        lines.append(f"Title: {r.get('title', 'N/A')}")
        lines.append(f"URL: {r.get('url', 'N/A')}")
        snippet = r.get("snippet", r.get("description", ""))
        if snippet:
            lines.append(f"Snippet: {snippet[:300]}")
        lines.append("")

    return "\n".join(lines)[:4000]


def _ddg_search(query: str, max_results: int = 10) -> list[dict]:
    """DuckDuckGo HTML search (no API key, respects robots.txt)."""
    url = "https://html.duckduckgo.com/html/"
    data = urllib.parse.urlencode({"q": query, "kl": "us-en"}).encode()

    req = urllib.request.Request(
        url,
        data=data,
        headers={"User-Agent": "Mozilla/5.0 (compatible; AgentApp/1.0; +https://example.com)"},
    )

    try:
        with urllib.request.urlopen(req, timeout=WEB_SEARCH_TIMEOUT) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return []

    # Parse DDG HTML results (simple regex-based extraction)
    results: list[dict] = []
    # Find result blocks
    result_blocks = re.findall(
        r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
        html, re.DOTALL | re.IGNORECASE,
    )
    snippet_blocks = re.findall(
        r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
        html, re.DOTALL | re.IGNORECASE,
    )

    for i, (href, title_raw) in enumerate(result_blocks[:max_results]):
        title = re.sub(r"<[^>]+>", "", title_raw).strip()
        snippet = ""
        if i < len(snippet_blocks):
            snippet = re.sub(r"<[^>]+>", "", snippet_blocks[i]).strip()
        if title:
            results.append({"title": title, "url": href, "snippet": snippet})

    return results


@tool
def web_fetch(url: str) -> str:
    """Fetch content from a URL and return it as text.

    Attempts to extract the main text content from HTML pages. Use this
    to read documentation, articles, or data from the web.

    Args:
        url: Full URL to fetch (HTTP/HTTPS)

    Returns:
        Page content as text (truncated at 8000 characters), or an error message.

    Example: web_fetch('https://docs.scipy.org/doc/scipy/reference/optimize.html')
    """
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AgentApp/1.0"})
        with urllib.request.urlopen(req, timeout=WEB_FETCH_TIMEOUT) as resp:
            content_type = resp.headers.get("Content-Type", "")

            # Handle text/plain
            if "text/plain" in content_type:
                raw = resp.read().decode("utf-8", errors="replace")
                return raw[:8000]

            # Handle HTML
            raw = resp.read()
            text = _extract_text_from_html(raw)
            return text[:8000] if text.strip() else "(no text content extracted)"

    except urllib.error.HTTPError as exc:
        return f"HTTP error {exc.code}: {exc.reason}"
    except urllib.error.URLError as exc:
        return f"URL error: {exc.reason}"
    except Exception as exc:
        return f"Web fetch failed: {exc}"


def _extract_text_from_html(html_bytes: bytes) -> str:
    """Extract readable text from HTML, stripping tags and scripts."""
    html = html_bytes.decode("utf-8", errors="replace")

    # Remove script/style/nav/footer/header content
    for tag in ("script", "style", "nav", "footer", "header", "aside", "noscript"):
        html = re.sub(rf"<{tag}[^>]*>.*?</{tag}>", "", html, flags=re.DOTALL | re.IGNORECASE)

    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", html)

    # Decode HTML entities
    import html as html_module
    text = html_module.unescape(text)

    # Collapse whitespace
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"\s+", " ", text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n\n".join(lines)


# ============================================================================
# Tool Registry
# ============================================================================

@tool
def write_file(filepath: str, content: str) -> str:
    """Write content to a file. Creates parent directories if needed.

    Use this to save your output as actual files on disk. The filepath
    should include the extension (.py, .tex, .md, .txt, etc).
    Files are saved under agent_app/output/ (supports subdirs like figures/plot.png).

    Args:
        filepath: Filename or relative path (e.g., 'solve.py', 'figures/plot.png')
        content: Full file content to write

    Returns:
        Confirmation with file path and size.

    Example: write_file('solve.py', 'import numpy\\nprint("hello")')
    Example: write_file('paper.tex', '\\\\documentclass{article}...')
    """
    from .config import APP_ROOT

    out_dir = (APP_ROOT / "output").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    rel = Path(filepath.strip().replace("\\", "/").lstrip("/"))
    if not rel.name or ".." in rel.parts:
        return f"Invalid filepath: {filepath}"

    path = (out_dir / rel).resolve()
    if not str(path).startswith(str(out_dir)):
        return f"Invalid filepath: {filepath}"

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")
    display = path.relative_to(out_dir)
    return f"Written: {display} ({path.stat().st_size} bytes) to output/"


EXPLORATION_TOOLS = [
    read_file,
    search_files,
    search_content,
    list_directory,
    web_search,
    web_fetch,
    write_file,
]

_all_tool_names = [t.name for t in EXPLORATION_TOOLS]


def get_exploration_tools() -> list:
    """Return all exploration tools for use with LangChain agents."""
    return EXPLORATION_TOOLS