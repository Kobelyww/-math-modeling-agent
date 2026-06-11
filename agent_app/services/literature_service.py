from __future__ import annotations

from typing import Any

from agent_app import literature


class LiteratureService:
    def search(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for fn in [
            literature._search_crossref_raw,
            literature._search_s2_raw,
            literature._search_arxiv_raw,
        ]:
            raw = fn(query, max_results=max_results)
            if raw:
                results.extend(row for row in raw if "error" not in row)
        return results[:max_results]

    def format_results(self, papers: list[dict[str, Any]]) -> str:
        lines = ["# 文献证据", ""]
        for index, paper in enumerate(papers, 1):
            authors = ", ".join(paper.get("authors", [])[:3])
            lines.append(f"## [{index}] {paper.get('title', '')}")
            lines.append(f"- Authors: {authors}")
            lines.append(f"- Year: {paper.get('year', '')}")
            lines.append(f"- Source: {paper.get('source', '')}")
            lines.append(f"- URL: {paper.get('page_url', '') or paper.get('pdf_url', '')}")
            abstract = (paper.get("abstract", "") or "").replace("\n", " ")
            if abstract:
                lines.append(f"- Abstract: {abstract[:800]}")
            lines.append("")
        return "\n".join(lines)
