from __future__ import annotations

from pathlib import Path

from agent_app.config import Settings
from agent_app.domain.models import RunSpec, RunStatus
from agent_app.web.paper_stream import (
    EventDrivingCoordinator,
    PaperChatRequest,
    PaperChatStreamer,
    build_followup_question,
)


class EventCollector:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def __call__(self, event: dict) -> None:
        self.events.append(event)


def test_paper_chat_stream_emits_stage_tool_artifact_and_done_events(tmp_path):
    data_file = tmp_path / "traffic.csv"
    data_file.write_text("flow,speed\n10,40\n", encoding="utf-8")
    reference_file = tmp_path / "ref.md"
    reference_file.write_text("层次分析法可用于评价问题。", encoding="utf-8")
    collector = EventCollector()

    streamer = PaperChatStreamer(
        output_root=tmp_path / "runs",
        coordinator_factory=lambda run_store, **_: EventDrivingCoordinator(run_store, collector),
    )
    result = streamer.run(
        RunSpec(
            question="建立交通流预测模型",
            data_files=[data_file],
            reference_files=[reference_file],
        ),
        emit=collector,
    )

    event_types = [event["type"] for event in collector.events]
    assert event_types[0] == "start"
    assert "stage" in event_types
    assert "tool" in event_types
    assert "artifact" in event_types
    assert event_types[-1] == "done"
    assert result.status == RunStatus.COMPLETED
    assert any(event.get("stage") == "draft_paper" for event in collector.events)
    assert any(event.get("name") == "paper.tex" for event in collector.events)


def test_paper_chat_streamer_default_uses_real_runner_path(tmp_path, monkeypatch):
    collector = EventCollector()
    captured = {}

    class RecordingRunner:
        def __init__(self, output_root=None, settings=None, coordinator_factory=None):
            captured["settings"] = settings
            captured["coordinator_factory"] = coordinator_factory
            captured["output_root"] = output_root

        def run(self, spec):
            from agent_app.domain.models import RunResult, RunStage

            captured["question"] = spec.question
            return RunResult(
                run_id="run_real",
                status=RunStatus.COMPLETED,
                stage=RunStage.PACKAGE_SUBMISSION,
                summary="real runner completed",
            )

    monkeypatch.setattr("agent_app.web.paper_stream.CompetitionPaperRunner", RecordingRunner)
    settings = Settings(api_key="key", api_base=None, model="deepseek-v4-pro", temperature=0.3)

    streamer = PaperChatStreamer(output_root=tmp_path / "runs", settings=settings)
    result = streamer.run(RunSpec(question="建立真实模型"), emit=collector)

    assert result.run_id == "run_real"
    assert captured["settings"] is settings
    assert captured["coordinator_factory"] is None
    assert not any(event.get("type") == "tool" for event in collector.events)


def test_build_followup_question_includes_recent_assistant_context():
    request = PaperChatRequest(
        question="补充灵敏度分析",
        messages=[
            {"role": "user", "content": "建立交通流预测模型"},
            {"role": "assistant", "content": "已生成初稿和模型代码。"},
        ],
    )

    question = build_followup_question(request)

    assert "补充灵敏度分析" in question
    assert "建立交通流预测模型" in question
    assert "已生成初稿和模型代码" in question


def test_paper_chat_start_endpoint_rejects_empty_question():
    from fastapi.testclient import TestClient

    from agent_app.web.main import app

    client = TestClient(app)

    response = client.post("/api/paper/chat/start", json={"question": ""})

    assert response.status_code == 400
    assert response.json()["error"] == "问题不能为空"
