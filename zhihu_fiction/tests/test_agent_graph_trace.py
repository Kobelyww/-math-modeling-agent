from pathlib import Path

from zhihu_fiction.ip_memory.agent_graph import node_for_stage, workflow_nodes
from zhihu_fiction.ip_memory.trace import AgentTraceEvent, AgentTraceStore


def test_workflow_nodes_includes_drama_storyboard_contract():
    nodes = workflow_nodes()

    storyboard = nodes["drama.storyboard"]

    assert storyboard.node_id == "drama.storyboard"
    assert "CharacterCard" in storyboard.required_memory
    assert "review_stage_output" in storyboard.tools
    assert storyboard.human_review_policy == "required"


def test_node_for_stage_maps_existing_drama_stage_names():
    assert node_for_stage("script").node_id == "drama.script"
    assert node_for_stage("storyboard").node_id == "drama.storyboard"


def test_agent_trace_store_appends_and_reads_metadata(tmp_path: Path):
    store = AgentTraceStore(tmp_path)
    event = AgentTraceEvent(
        run_id="run/中文:001",
        node_id="drama.storyboard",
        stage="storyboard",
        event="completed",
        tool_calls=[{"name": "review_stage_output", "status": "ok"}],
        review={"score": 0.92},
        human_decision={"decision": "approved"},
        metadata={"note": "保留中文", "shot_count": 3},
    )

    store.append(event)
    restored = store.list("run/中文:001")

    assert len(restored) == 1
    assert restored[0].run_id == "run/中文:001"
    assert restored[0].metadata == {"note": "保留中文", "shot_count": 3}
    assert restored[0].tool_calls == [{"name": "review_stage_output", "status": "ok"}]
