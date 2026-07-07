from pathlib import Path

from zhihu_fiction.ip_memory.agent_graph import node_for_stage, workflow_nodes
from zhihu_fiction.ip_memory.trace import AgentTraceEvent, AgentTraceStore


def test_workflow_nodes_includes_drama_storyboard_contract():
    nodes = workflow_nodes()

    assert set(nodes) == {
        "fiction.topic_intake",
        "fiction.story_bible",
        "fiction.outline",
        "fiction.chapter",
        "fiction.review",
        "fiction.memory_extract",
        "drama.adaptation_blueprint",
        "drama.episode_plot",
        "drama.script",
        "drama.style",
        "drama.consistency",
        "drama.character_reference",
        "drama.storyboard",
        "drama.video_prompt_package",
        "video.cost_confirmation",
        "video.submit_jobs",
    }

    storyboard = nodes["drama.storyboard"]

    assert storyboard.node_id == "drama.storyboard"
    assert "CharacterCard" in storyboard.required_memory
    assert "review_stage_output" in storyboard.tools
    assert storyboard.human_review_policy == "required"
    assert storyboard.next_nodes == ("drama.video_prompt_package",)


def test_workflow_nodes_use_spec_policy_strings():
    nodes = workflow_nodes()

    assert nodes["video.cost_confirmation"].retry_policy == "retry"
    assert nodes["video.cost_confirmation"].cost_policy == "paid_confirmation"
    assert nodes["video.submit_jobs"].retry_policy == "shot_retry"
    assert nodes["video.submit_jobs"].cost_policy == "paid"

    for node in nodes.values():
        assert isinstance(node.retry_policy, str)
        assert isinstance(node.cost_policy, str)


def test_node_for_stage_maps_existing_drama_stage_names():
    assert node_for_stage("plot").node_id == "drama.episode_plot"
    assert node_for_stage("script").node_id == "drama.script"
    assert node_for_stage("style").node_id == "drama.style"
    assert node_for_stage("character_refs").node_id == "drama.character_reference"
    assert node_for_stage("storyboard").node_id == "drama.storyboard"
    assert node_for_stage("video").node_id == "video.cost_confirmation"


def test_node_for_stage_rejects_unknown_stage_with_clear_message():
    try:
        node_for_stage("unknown")
    except KeyError as exc:
        assert exc.args == ("Unknown agent graph stage: unknown",)
    else:
        raise AssertionError("expected KeyError")


def test_agent_graph_node_to_dict_preserves_manifest_shapes():
    node = workflow_nodes()["video.cost_confirmation"]
    payload = node.to_dict()

    assert payload["inputs"] == ["video_prompts"]
    assert payload["outputs"] == ["cost_estimate"]
    assert payload["required_memory"] == []
    assert payload["tools"] == ["request_human_review"]
    assert payload["quality_gates"] == ["budget_limit"]
    assert payload["retry_policy"] == "retry"
    assert payload["cost_policy"] == "paid_confirmation"
    assert payload["next_nodes"] == ["video.submit_jobs"]


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
