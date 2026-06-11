from __future__ import annotations

from pathlib import Path

from agent_app.services.code_execution import CodeExecutionService
from agent_app.services.latex_service import LatexService
from agent_app.services.literature_service import LiteratureService
from agent_app.services.rag_service import RagService


def test_code_execution_service_runs_in_working_directory(tmp_path):
    service = CodeExecutionService(timeout=10)
    result = service.execute_code("print('hello paper')", cwd=tmp_path)

    assert result.execution_status == "success"
    assert "hello paper" in result.stdout


def test_code_execution_service_writes_code_file(tmp_path):
    service = CodeExecutionService(timeout=10)
    code_path = service.write_code(tmp_path, "print(1)")

    assert code_path.name == "solve.py"
    assert code_path.read_text(encoding="utf-8") == "print(1)\n"


def test_latex_service_reports_missing_binary_without_crashing(tmp_path, monkeypatch):
    tex = tmp_path / "paper.tex"
    tex.write_text("\\documentclass{article}\\begin{document}Hi\\end{document}", encoding="utf-8")
    monkeypatch.setattr("shutil.which", lambda name: None)

    result = LatexService().compile(tex)

    assert result["compiled"] is False
    assert "not found" in result["diagnostics"].lower()


def test_literature_service_can_format_raw_results():
    service = LiteratureService()
    formatted = service.format_results(
        [
            {
                "source": "crossref",
                "title": "Traffic flow model",
                "authors": ["A. Author"],
                "year": "2024",
                "abstract": "A model.",
                "page_url": "https://doi.org/example",
            }
        ]
    )

    assert "Traffic flow model" in formatted
    assert "2024" in formatted


def test_rag_service_indexes_run_references(tmp_path):
    ref_dir = tmp_path / "refs"
    ref_dir.mkdir()
    (ref_dir / "paper.md").write_text("层次分析法 可用于评价问题", encoding="utf-8")

    service = RagService(index_root=tmp_path / "index")
    stats = service.build_index(ref_dir, run_id="run_test")
    hits = service.query("评价问题", run_id="run_test", top_k=1)

    assert stats["chunks"] >= 1
    assert hits
