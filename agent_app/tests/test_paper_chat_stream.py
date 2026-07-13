from __future__ import annotations

from pathlib import Path

from agent_app.config import Settings
from agent_app.domain.models import RunSpec, RunStatus
from agent_app.services.run_store import RunStore
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
        def __init__(self, output_root=None, settings=None, coordinator_factory=None, event_handler=None):
            captured["settings"] = settings
            captured["coordinator_factory"] = coordinator_factory
            captured["output_root"] = output_root
            captured["event_handler"] = event_handler

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
    assert captured["event_handler"] is collector
    assert not any(event.get("type") == "tool" for event in collector.events)


def test_paper_chat_streamer_passes_event_handler_to_real_runner(tmp_path, monkeypatch):
    collector = EventCollector()
    captured = {}

    class RecordingRunner:
        def __init__(self, output_root=None, settings=None, coordinator_factory=None, event_handler=None):
            captured["event_handler"] = event_handler

        def run(self, spec):
            from agent_app.domain.models import RunResult, RunStage

            captured["event_handler"]({"type": "tool", "stage": "ingest_inputs", "name": "ingest_inputs", "status": "running"})
            return RunResult(
                run_id="run_real",
                status=RunStatus.PARTIAL,
                stage=RunStage.INGEST_INPUTS,
                summary="needs input",
            )

    monkeypatch.setattr("agent_app.web.paper_stream.CompetitionPaperRunner", RecordingRunner)
    settings = Settings(api_key="key", api_base=None, model="deepseek-v4-pro", temperature=0.3)

    streamer = PaperChatStreamer(output_root=tmp_path / "runs", settings=settings)
    streamer.run(RunSpec(question="建立真实模型"), emit=collector)

    assert captured["event_handler"] is collector
    assert any(event.get("type") == "tool" and event.get("stage") == "ingest_inputs" for event in collector.events)


def test_paper_chat_streamer_does_not_mark_deepagent_stage_complete_for_partial_result(tmp_path, monkeypatch):
    collector = EventCollector()

    class PartialRunner:
        def __init__(self, output_root=None, settings=None, coordinator_factory=None, event_handler=None):
            pass

        def run(self, spec):
            from agent_app.domain.models import RunResult, RunStage

            return RunResult(
                run_id="run_partial",
                status=RunStatus.PARTIAL,
                stage=RunStage.CREATED,
                summary="请补充完整赛题和数据文件。",
            )

    monkeypatch.setattr("agent_app.web.paper_stream.CompetitionPaperRunner", PartialRunner)
    settings = Settings(api_key="key", api_base=None, model="deepseek-v4-pro", temperature=0.3)

    streamer = PaperChatStreamer(output_root=tmp_path / "runs", settings=settings)
    result = streamer.run(RunSpec(question="建立真实模型"), emit=collector)

    assert result.status == RunStatus.PARTIAL
    deepagent_events = [
        event
        for event in collector.events
        if event.get("type") == "stage" and event.get("stage") == "deepagent_reasoning"
    ]
    assert [event["status"] for event in deepagent_events] == ["running", "partial"]


def test_paper_stream_emits_section_writing_events(tmp_path):
    events = []

    class FakeCoordinator:
        def __init__(self, run_store, settings=None, event_handler=None):
            self.run_store = run_store
            self.event_handler = event_handler

        def invoke(self, payload):
            run_dir = self.run_store.run_dir(payload["run_id"])
            section = run_dir / "paper" / "sections" / "04_model_building.md"
            section.parent.mkdir(parents=True, exist_ok=True)
            section.write_text("# 模型建立\n", encoding="utf-8")
            self.event_handler(
                {
                    "type": "section",
                    "stage": "draft_paper",
                    "name": "04_model_building.md",
                    "status": "completed",
                    "path": str(section),
                }
            )
            return {"messages": [{"content": str(section)}]}

    streamer = PaperChatStreamer(output_root=tmp_path, coordinator_factory=FakeCoordinator)
    streamer.run(RunSpec(question="建立模型"), events.append)

    assert any(event.get("type") == "section" and event.get("name") == "04_model_building.md" for event in events)


def test_event_driving_coordinator_emits_section_events_from_draft_result(tmp_path):
    store = RunStore(output_root=tmp_path)
    events = []
    coordinator = EventDrivingCoordinator(store, events.append)
    section = tmp_path / "run" / "paper" / "sections" / "04_model_building.md"
    coordinator.tools = {
        "draft_competition_paper": type(
            "Tool",
            (),
            {"invoke": lambda self, payload: {"paper_section_paths": [str(section)]}},
        )()
    }

    coordinator._stage("draft_paper", "起草论文", "draft_competition_paper", {})

    assert any(event.get("type") == "section" and event.get("path") == str(section) for event in events)


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
