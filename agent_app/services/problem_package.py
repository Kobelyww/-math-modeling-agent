from __future__ import annotations

from typing import Any

from agent_app.services.artifact_service import ArtifactService


def build_problem_package(
    artifacts: ArtifactService,
    question: str,
    tables: list[dict[str, Any]] | None = None,
    figures: list[dict[str, Any]] | None = None,
) -> dict[str, str]:
    """Persist conservative structured problem artifacts for downstream agents."""
    table_extraction_status = _extraction_status(tables)
    figure_extraction_status = _extraction_status(figures)
    normalized_tables = [
        _normalize_table(table, index)
        for index, table in enumerate(tables or [], start=1)
    ]
    normalized_figures = [
        _normalize_figure(figure, index)
        for index, figure in enumerate(figures or [], start=1)
    ]

    problem_spec_path = artifacts.write_json(
        "problem_spec.json",
        {
            "background": _extract_background(question),
            "subproblems": [],
            "objectives": [],
            "constraints": [],
            "deliverables": ["modeling_report.md", "solve.py", "paper.md", "paper.tex"],
        },
    )
    tables_path = artifacts.write_json("tables.json", {"tables": normalized_tables})
    figures_path = artifacts.write_json("figures.json", {"figures": normalized_figures})
    source_map_path = artifacts.write_json(
        "source_map.json",
        {
            "sources": _build_source_entries(normalized_tables, normalized_figures),
            "extraction_status": {
                "tables": {"status": table_extraction_status, "count": len(normalized_tables)},
                "figures": {"status": figure_extraction_status, "count": len(normalized_figures)},
            },
        },
    )

    return {
        "problem_spec_path": str(problem_spec_path),
        "tables_path": str(tables_path),
        "figures_path": str(figures_path),
        "source_map_path": str(source_map_path),
    }


def _extract_background(question: str) -> str:
    clean_question = " ".join(question.strip().split())
    if not clean_question:
        return ""
    for separator in ("。", ".", "\n"):
        if separator in clean_question:
            return clean_question.split(separator, 1)[0].strip()
    return clean_question[:300]


def _source_from(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "page": item.get("page"),
        "method": item.get("method"),
        "confidence": item.get("confidence"),
    }


def _extraction_status(items: list[dict[str, Any]] | None) -> str:
    if items is None:
        return "not_attempted"
    if items:
        return "provided"
    return "attempted_empty"


def _normalize_table(table: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "id": table.get("id") or f"table_{index}",
        "title": table.get("title") or f"Table {index}",
        "headers": table.get("headers") or [],
        "rows": table.get("rows") or [],
        "source": _source_from(table),
    }


def _normalize_figure(figure: dict[str, Any], index: int) -> dict[str, Any]:
    normalized = {
        "id": figure.get("id") or f"figure_{index}",
        "title": figure.get("title") or f"Figure {index}",
        "description": figure.get("description", ""),
        "source": _source_from(figure),
    }
    if figure.get("path"):
        normalized["path"] = figure["path"]
    return normalized


def _build_source_entries(
    tables: list[dict[str, Any]],
    figures: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = [
        {
            "artifact": "question.md",
            "type": "question",
            "source_id": "question",
            "method": "user_input",
            "confidence": 1.0,
        }
    ]
    sources.extend(
        _source_entry("tables.json", "table", table, index)
        for index, table in enumerate(tables, start=1)
    )
    sources.extend(
        _source_entry("figures.json", "figure", figure, index)
        for index, figure in enumerate(figures, start=1)
    )
    return sources


def _source_entry(
    artifact: str,
    source_type: str,
    item: dict[str, Any],
    index: int,
) -> dict[str, Any]:
    source = item.get("source", {})
    return {
        "artifact": artifact,
        "type": source_type,
        "source_id": item.get("id") or f"{source_type}_{index}",
        "title": item.get("title", ""),
        "page": source.get("page"),
        "method": source.get("method"),
        "confidence": source.get("confidence"),
    }
