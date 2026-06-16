from __future__ import annotations

from pathlib import Path

from agent_app.domain.models import RunSpec
from agent_app.interfaces.cli import AttachmentBuffer, build_run_spec
from agent_app.interfaces.web import resolve_paper_input_paths, serialize_run_result


def test_attachment_buffer_builds_run_spec(tmp_path):
    data = tmp_path / "data.csv"
    data.write_text("x,y\n1,2\n", encoding="utf-8")
    ref = tmp_path / "ref.md"
    ref.write_text("reference", encoding="utf-8")

    buffer = AttachmentBuffer()
    buffer.attach(data)
    buffer.attach(ref)

    spec = build_run_spec("建立模型", buffer)

    assert spec.question == "建立模型"
    assert spec.data_files == [data]
    assert spec.reference_files == [ref]


def test_attachment_buffer_classifies_pdf_as_reference(tmp_path):
    pdf = tmp_path / "problem.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    buffer = AttachmentBuffer()
    buffer.attach(pdf)

    spec = build_run_spec("建立模型", buffer)

    assert spec.data_files == []
    assert spec.reference_files == [pdf]


def test_serialize_run_result_for_web():
    from agent_app.domain.models import ArtifactRef, RunResult, RunStage, RunStatus

    result = RunResult(
        run_id="run_1",
        status=RunStatus.COMPLETED,
        stage=RunStage.PACKAGE_SUBMISSION,
        artifacts=[ArtifactRef(name="paper.tex", path=Path("paper.tex"), kind="tex")],
        summary="done",
    )

    payload = serialize_run_result(result)

    assert payload["run_id"] == "run_1"
    assert payload["status"] == "completed"
    assert payload["artifacts"][0]["name"] == "paper.tex"


def test_resolve_paper_input_paths_keeps_relative_paths_under_allowed_root(tmp_path):
    allowed_root = tmp_path / "paper_inputs"

    paths = resolve_paper_input_paths(["data/example.csv", "refs/ref.md"], allowed_root)

    assert paths == [
        allowed_root.resolve() / "data" / "example.csv",
        allowed_root.resolve() / "refs" / "ref.md",
    ]


def test_resolve_paper_input_paths_rejects_outside_absolute_path(tmp_path):
    allowed_root = tmp_path / "paper_inputs"
    outside = tmp_path / "outside.csv"

    try:
        resolve_paper_input_paths([outside], allowed_root)
    except ValueError as exc:
        assert "outside allowed input directory" in str(exc)
    else:
        raise AssertionError("Expected outside absolute path to be rejected")


def test_resolve_paper_input_paths_rejects_parent_traversal(tmp_path):
    allowed_root = tmp_path / "paper_inputs"

    try:
        resolve_paper_input_paths(["../outside.csv"], allowed_root)
    except ValueError as exc:
        assert "outside allowed input directory" in str(exc)
    else:
        raise AssertionError("Expected parent traversal to be rejected")
