from __future__ import annotations

from pathlib import Path

from agent_app.domain.models import RunSpec
from agent_app.interfaces.cli import AttachmentBuffer, build_run_spec
from agent_app.interfaces.web import serialize_run_result


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
