from __future__ import annotations

from pathlib import Path

from agent_app.domain.models import RunSpec, RunStatus
from agent_app.web.paper_stream import PaperChatRequest, PaperChatStreamer, build_followup_question


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

    streamer = PaperChatStreamer(output_root=tmp_path / "runs")
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
