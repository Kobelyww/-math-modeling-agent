from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from agent_app import literature
from agent_app.sandbox import docker_sandbox as sandbox_mod
from agent_app.sandbox import _fallback_exec
from agent_app.services.code_execution import CodeExecutionService
from agent_app.services.latex_service import LatexService
from agent_app.services.literature_service import LiteratureService
from agent_app.services.rag_service import RagService


def test_code_execution_service_runs_in_working_directory(tmp_path):
    service = CodeExecutionService(timeout=10)
    result = service.execute_code(
        "with open('relative.txt', 'w', encoding='utf-8') as fp:\n"
        "    fp.write('hello paper')\n"
        "with open('relative.txt', 'r', encoding='utf-8') as fp:\n"
        "    print(fp.read())",
        cwd=tmp_path,
    )

    assert result.execution_status == "success"
    assert "hello paper" in result.stdout
    assert (tmp_path / "relative.txt").read_text(encoding="utf-8") == "hello paper"


def test_fallback_exec_respects_working_directory(tmp_path):
    result = _fallback_exec(
        "with open('fallback.txt', 'w', encoding='utf-8') as fp:\n"
        "    fp.write('fallback cwd')\n"
        "with open('fallback.txt', 'r', encoding='utf-8') as fp:\n"
        "    print(fp.read())",
        timeout=10,
        cwd=tmp_path,
    )

    assert result.success is True
    assert "fallback cwd" in result.stdout
    assert (tmp_path / "fallback.txt").exists()


def test_fallback_exec_blocks_reading_outside_working_directory(tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    cwd = tmp_path / "work"
    cwd.mkdir()

    result = _fallback_exec(
        "with open('../outside.txt', 'r', encoding='utf-8') as fp:\n"
        "    print(fp.read())",
        timeout=10,
        cwd=cwd,
    )

    assert result.success is False
    assert "outside sandbox blocked" in result.stderr.lower()


def test_fallback_exec_blocks_prefix_collision_sibling_write(tmp_path):
    cwd = tmp_path / "work"
    sibling = tmp_path / "work_escape"
    cwd.mkdir()
    sibling.mkdir()

    result = _fallback_exec(
        "with open('../work_escape/escape.txt', 'w', encoding='utf-8') as fp:\n"
        "    fp.write('escaped')",
        timeout=10,
        cwd=cwd,
    )

    assert result.success is False
    assert "outside sandbox blocked" in result.stderr.lower()
    assert not (sibling / "escape.txt").exists()


def test_safe_execute_does_not_fallback_for_docker_user_exit_code(monkeypatch, tmp_path):
    class FakeDockerSandbox:
        @property
        def available(self):
            return True

        def run(self, code, timeout=None, cwd=None):
            return sandbox_mod.SandboxResult(
                success=False,
                stdout="",
                stderr="user exited",
                exit_code=127,
            )

    def forbidden_fallback(code, timeout=sandbox_mod.PYTHON_TIMEOUT, cwd=None):
        raise AssertionError("host fallback must not run for user exit code 127")

    monkeypatch.setattr(sandbox_mod, "DockerSandbox", FakeDockerSandbox)
    monkeypatch.setattr(sandbox_mod, "_fallback_exec", forbidden_fallback)

    result = sandbox_mod.safe_execute("import sys; sys.exit(127)", timeout=10, cwd=tmp_path)

    assert result.exit_code == 127
    assert result.stderr == "user exited"


def test_safe_execute_does_not_fallback_for_user_docker_like_stderr(monkeypatch, tmp_path):
    class FakeDockerSandbox:
        @property
        def available(self):
            return True

        def run(self, code, timeout=None, cwd=None):
            return sandbox_mod.SandboxResult(
                success=False,
                stdout="",
                stderr="cannot connect to docker daemon",
                exit_code=1,
            )

    def forbidden_fallback(code, timeout=sandbox_mod.PYTHON_TIMEOUT, cwd=None):
        raise AssertionError("host fallback must not run for user stderr")

    monkeypatch.setattr(sandbox_mod, "DockerSandbox", FakeDockerSandbox)
    monkeypatch.setattr(sandbox_mod, "_fallback_exec", forbidden_fallback)

    result = sandbox_mod.safe_execute("raise SystemExit(1)", timeout=10, cwd=tmp_path)

    assert result.exit_code == 1
    assert "docker daemon" in result.stderr


def test_safe_execute_fallbacks_for_docker_infrastructure_failure(monkeypatch, tmp_path):
    class FakeDockerSandbox:
        @property
        def available(self):
            return True

        def run(self, code, timeout=None, cwd=None):
            return sandbox_mod.SandboxResult(
                success=False,
                stdout="",
                stderr="docker: Error response from daemon: no such image",
                exit_code=125,
            )

    called = {}

    def fake_fallback(code, timeout=sandbox_mod.PYTHON_TIMEOUT, cwd=None):
        called["cwd"] = cwd
        return sandbox_mod.SandboxResult(success=True, stdout="fallback", stderr="", exit_code=0)

    monkeypatch.setattr(sandbox_mod, "DockerSandbox", FakeDockerSandbox)
    monkeypatch.setattr(sandbox_mod, "_fallback_exec", fake_fallback)

    result = sandbox_mod.safe_execute("print('ok')", timeout=10, cwd=tmp_path)

    assert result.success is True
    assert result.stdout == "fallback"
    assert called["cwd"] == tmp_path


def test_docker_sandbox_keeps_code_file_outside_writable_work_dir(monkeypatch, tmp_path):
    captured: dict[str, list[str]] = {}

    def fake_run(cmd, capture_output, text, timeout, cwd=None):
        if cmd[:2] == ["docker", "run"]:
            captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(sandbox_mod.shutil, "which", lambda name: "/usr/bin/docker")
    monkeypatch.setattr(sandbox_mod.subprocess, "run", fake_run)

    result = sandbox_mod.DockerSandbox().run("print('ok')", timeout=10, cwd=tmp_path)

    assert result.success is True
    code_mount = next(part for part in captured["cmd"] if part.endswith(":/workspace/code.py:ro"))
    host_code_path = Path(code_mount.split(":", 1)[0]).resolve()
    with pytest.raises(ValueError):
        host_code_path.relative_to(tmp_path.resolve())


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


def test_latex_service_reports_timeout_without_crashing(tmp_path, monkeypatch):
    tex = tmp_path / "paper.tex"
    log = tmp_path / "paper.log"
    tex.write_text("\\documentclass{article}\\begin{document}Hi\\end{document}", encoding="utf-8")
    log.write_text("partial log", encoding="utf-8")
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/pdflatex")

    def raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=60)

    monkeypatch.setattr(subprocess, "run", raise_timeout)

    result = LatexService().compile(tex)

    assert result["compiled"] is False
    assert result["pdf_path"] == ""
    assert result["log_path"] == str(log)
    assert "timed out" in result["diagnostics"].lower()


def test_latex_service_reports_subprocess_error_without_crashing(tmp_path, monkeypatch):
    tex = tmp_path / "paper.tex"
    tex.write_text("\\documentclass{article}\\begin{document}Hi\\end{document}", encoding="utf-8")
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/pdflatex")
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("boom")))

    result = LatexService().compile(tex)

    assert result["compiled"] is False
    assert result["pdf_path"] == ""
    assert "boom" in result["diagnostics"]


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


def test_literature_service_filters_error_rows_after_valid_rows(monkeypatch):
    def mixed_results(query: str, max_results: int = 5):
        return [
            {"source": "crossref", "title": "Valid first"},
            {"error": "late source failure"},
            {"source": "crossref", "title": "Valid second"},
        ]

    monkeypatch.setattr(literature, "_search_crossref_raw", mixed_results)
    monkeypatch.setattr(literature, "_search_s2_raw", lambda query, max_results=5: [])
    monkeypatch.setattr(literature, "_search_arxiv_raw", lambda query, max_results=5: [{"source": "arxiv", "title": "Valid third"}])

    results = LiteratureService().search("traffic", max_results=2)

    assert [paper["title"] for paper in results] == ["Valid first", "Valid second"]
    assert all("error" not in paper for paper in results)


def test_literature_service_skips_provider_exceptions(monkeypatch):
    def broken_provider(query: str, max_results: int = 5):
        raise RuntimeError("provider failed")

    monkeypatch.setattr(literature, "_search_crossref_raw", broken_provider)
    monkeypatch.setattr(literature, "_search_s2_raw", lambda query, max_results=5: [{"source": "s2", "title": "Recovered"}])
    monkeypatch.setattr(literature, "_search_arxiv_raw", lambda query, max_results=5: [])

    results = LiteratureService().search("traffic", max_results=5)

    assert [paper["title"] for paper in results] == ["Recovered"]


def test_rag_service_indexes_run_references(tmp_path):
    ref_dir = tmp_path / "refs"
    ref_dir.mkdir()
    (ref_dir / "paper.md").write_text("层次分析法 可用于评价问题", encoding="utf-8")

    service = RagService(index_root=tmp_path / "index")
    stats = service.build_index(ref_dir, run_id="run_test")
    hits = service.query("评价问题", run_id="run_test", top_k=1)

    assert stats["chunks"] >= 1
    assert hits


def test_rag_service_queries_reloaded_index_from_fresh_instance(tmp_path):
    ref_dir = tmp_path / "refs"
    ref_dir.mkdir()
    (ref_dir / "paper.md").write_text("层次分析法 可用于评价问题", encoding="utf-8")

    index_root = tmp_path / "index"
    first = RagService(index_root=index_root)
    first.build_index(ref_dir, run_id="run_test")
    second = RagService(index_root=index_root)

    hits = second.query("评价问题", run_id="run_test", top_k=1)

    assert hits


def test_rag_service_rejects_unsafe_run_id(tmp_path):
    ref_dir = tmp_path / "refs"
    ref_dir.mkdir()
    (ref_dir / "paper.md").write_text("层次分析法 可用于评价问题", encoding="utf-8")
    index_root = tmp_path / "index"
    service = RagService(index_root=index_root)

    with pytest.raises(ValueError):
        service.build_index(ref_dir, run_id="../escape")
    with pytest.raises(ValueError):
        service.query("评价问题", run_id="../escape", top_k=1)

    assert not (tmp_path / "escape_rag.pkl").exists()
