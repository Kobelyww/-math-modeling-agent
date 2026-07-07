"""Agent DAG metadata for unified fiction and short-drama production."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class AgentGraphNode:
    node_id: str
    stage: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    required_memory: tuple[str, ...]
    tools: tuple[str, ...]
    quality_gates: tuple[str, ...]
    human_review_policy: str
    retry_policy: str
    cost_policy: str
    next_nodes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "stage": self.stage,
            "inputs": list(self.inputs),
            "outputs": list(self.outputs),
            "required_memory": list(self.required_memory),
            "tools": list(self.tools),
            "quality_gates": list(self.quality_gates),
            "human_review_policy": self.human_review_policy,
            "retry_policy": self.retry_policy,
            "cost_policy": self.cost_policy,
            "next_nodes": list(self.next_nodes),
        }


def workflow_nodes() -> dict[str, AgentGraphNode]:
    return {node.node_id: node for node in _WORKFLOW_NODES}


def node_for_stage(stage: str) -> AgentGraphNode:
    try:
        node_id = _DRAMA_STAGE_NODE_IDS[stage]
    except KeyError as exc:
        raise KeyError(f"Unknown agent graph stage: {stage}") from exc
    return workflow_nodes()[node_id]


def _node(
    node_id: str,
    stage: str,
    *,
    inputs: tuple[str, ...] = (),
    outputs: tuple[str, ...] = (),
    required_memory: tuple[str, ...] = (),
    tools: tuple[str, ...] = (),
    quality_gates: tuple[str, ...] = (),
    human_review_policy: str = "optional",
    retry_policy: str = "retry",
    cost_policy: str = "free",
    next_nodes: tuple[str, ...] = (),
) -> AgentGraphNode:
    return AgentGraphNode(
        node_id=node_id,
        stage=stage,
        inputs=inputs,
        outputs=outputs,
        required_memory=required_memory,
        tools=tools,
        quality_gates=quality_gates,
        human_review_policy=human_review_policy,
        retry_policy=retry_policy,
        cost_policy=cost_policy,
        next_nodes=next_nodes,
    )


_WORKFLOW_NODES: tuple[AgentGraphNode, ...] = (
    _node(
        "fiction.topic_intake",
        "topic_intake",
        inputs=("topic",),
        outputs=("topic_card",),
        tools=("generate_stage_draft",),
        quality_gates=("topic_safety",),
        next_nodes=("fiction.story_bible",),
    ),
    _node(
        "fiction.story_bible",
        "story_bible",
        inputs=("topic_card",),
        outputs=("StoryBible",),
        tools=("generate_stage_draft", "write_ip_memory_patch"),
        quality_gates=("memory_completeness",),
        human_review_policy="required",
        retry_policy="new_version",
        next_nodes=("fiction.outline",),
    ),
    _node(
        "fiction.outline",
        "outline",
        inputs=("StoryBible",),
        outputs=("outline", "Foreshadowing"),
        required_memory=("StoryBible",),
        tools=("generate_stage_draft",),
        quality_gates=("continuity_checker",),
        human_review_policy="required",
        retry_policy="new_version",
        next_nodes=("fiction.chapter",),
    ),
    _node(
        "fiction.chapter",
        "chapter",
        inputs=("outline", "memory"),
        outputs=("story_text",),
        required_memory=("StoryBible", "CharacterCard", "WorldFact"),
        tools=("generate_stage_draft",),
        quality_gates=("chapter_quality",),
        human_review_policy="required",
        retry_policy="new_version",
        next_nodes=("fiction.review",),
    ),
    _node(
        "fiction.review",
        "review",
        inputs=("story_text", "memory"),
        outputs=("review",),
        required_memory=("StoryBible",),
        tools=("review_stage_output",),
        quality_gates=("continuity_checker",),
        human_review_policy="required",
        next_nodes=("fiction.memory_extract",),
    ),
    _node(
        "fiction.memory_extract",
        "memory_extract",
        inputs=("story_text",),
        outputs=("IPMemory",),
        tools=("write_ip_memory_patch",),
        quality_gates=("memory_completeness",),
        next_nodes=("drama.adaptation_blueprint",),
    ),
    _node(
        "drama.adaptation_blueprint",
        "adaptation_blueprint",
        inputs=("story", "IPMemory"),
        outputs=("blueprint",),
        required_memory=("StoryBible", "CharacterCard"),
        tools=("inspect_ip_memory", "generate_stage_draft"),
        quality_gates=("short_drama_pacing",),
        human_review_policy="required",
        retry_policy="new_version",
        next_nodes=("drama.episode_plot",),
    ),
    _node(
        "drama.episode_plot",
        "plot",
        inputs=("blueprint", "IPMemory"),
        outputs=("plot",),
        required_memory=("StoryBible", "Foreshadowing"),
        tools=("generate_stage_draft", "review_stage_output"),
        quality_gates=("continuity_checker",),
        human_review_policy="required",
        retry_policy="new_version",
        next_nodes=("drama.script",),
    ),
    _node(
        "drama.script",
        "script",
        inputs=("plot", "IPMemory"),
        outputs=("script",),
        required_memory=("StoryBible", "CharacterCard"),
        tools=("generate_stage_draft", "review_stage_output"),
        quality_gates=("short_drama_pacing",),
        human_review_policy="required",
        retry_policy="new_version",
        next_nodes=("drama.style",),
    ),
    _node(
        "drama.style",
        "style",
        inputs=("script", "IPMemory"),
        outputs=("StyleGuide",),
        required_memory=("StoryBible",),
        tools=("generate_stage_draft", "write_ip_memory_patch"),
        quality_gates=("style_compatibility",),
        human_review_policy="required",
        retry_policy="new_version",
        next_nodes=("drama.consistency",),
    ),
    _node(
        "drama.consistency",
        "consistency",
        inputs=("style", "IPMemory"),
        outputs=("consistency_report",),
        required_memory=("StoryBible", "CharacterCard", "WorldFact"),
        tools=("review_stage_output",),
        quality_gates=("continuity_checker",),
        human_review_policy="required",
        next_nodes=("drama.character_reference",),
    ),
    _node(
        "drama.character_reference",
        "character_refs",
        inputs=("IPMemory",),
        outputs=("character_reference_prompts",),
        required_memory=("CharacterCard", "StyleGuide"),
        tools=("generate_stage_draft",),
        quality_gates=("bailian_video_prompt_guard",),
        human_review_policy="required",
        retry_policy="new_version",
        next_nodes=("drama.storyboard",),
    ),
    _node(
        "drama.storyboard",
        "storyboard",
        inputs=("script", "style", "IPMemory"),
        outputs=("storyboard",),
        required_memory=("StoryBible", "CharacterCard", "WorldFact", "StyleGuide"),
        tools=("generate_stage_draft", "review_stage_output"),
        quality_gates=("continuity_checker", "shot_prompt_builder"),
        human_review_policy="required",
        retry_policy="new_version",
        next_nodes=("drama.video_prompt_package",),
    ),
    _node(
        "drama.video_prompt_package",
        "video_prompt_package",
        inputs=("storyboard", "IPMemory"),
        outputs=("video_prompts",),
        required_memory=("CharacterCard", "StyleGuide"),
        tools=("generate_stage_draft", "review_stage_output"),
        quality_gates=("bailian_video_prompt_guard",),
        human_review_policy="required",
        retry_policy="new_version",
        next_nodes=("video.cost_confirmation",),
    ),
    _node(
        "video.cost_confirmation",
        "video",
        inputs=("video_prompts",),
        outputs=("cost_estimate",),
        tools=("request_human_review",),
        quality_gates=("budget_limit",),
        human_review_policy="required",
        cost_policy="paid_confirmation",
        next_nodes=("video.submit_jobs",),
    ),
    _node(
        "video.submit_jobs",
        "video_submit",
        inputs=("cost_confirmation",),
        outputs=("video_jobs",),
        tools=("advance_agent_graph",),
        quality_gates=("provider_status",),
        human_review_policy="required",
        retry_policy="shot_retry",
        cost_policy="paid",
    ),
)

_DRAMA_STAGE_NODE_IDS = {
    "plot": "drama.episode_plot",
    "script": "drama.script",
    "style": "drama.style",
    "character_refs": "drama.character_reference",
    "storyboard": "drama.storyboard",
    "video": "video.cost_confirmation",
}
