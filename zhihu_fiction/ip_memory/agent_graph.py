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
    retry_policy: dict[str, Any]
    cost_policy: dict[str, Any]
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
            "retry_policy": dict(self.retry_policy),
            "cost_policy": dict(self.cost_policy),
            "next_nodes": list(self.next_nodes),
        }


def workflow_nodes() -> dict[str, AgentGraphNode]:
    return {node.node_id: node for node in _WORKFLOW_NODES}


def node_for_stage(stage: str) -> AgentGraphNode:
    node_id = _DRAMA_STAGE_NODE_IDS[stage]
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
    retry_policy: dict[str, Any] | None = None,
    cost_policy: dict[str, Any] | None = None,
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
        retry_policy=retry_policy or {"max_attempts": 2},
        cost_policy=cost_policy or {"budget": "standard"},
        next_nodes=next_nodes,
    )


_WORKFLOW_NODES: tuple[AgentGraphNode, ...] = (
    _node(
        "fiction.topic_intake",
        "topic_intake",
        outputs=("TopicBrief",),
        next_nodes=("fiction.story_bible",),
    ),
    _node(
        "fiction.story_bible",
        "story_bible",
        inputs=("TopicBrief",),
        outputs=("StoryBible",),
        required_memory=("StoryBible",),
        next_nodes=("fiction.outline",),
    ),
    _node(
        "fiction.outline",
        "outline",
        inputs=("StoryBible",),
        outputs=("Outline",),
        required_memory=("StoryBible", "NarrativeMemory"),
        next_nodes=("fiction.chapter",),
    ),
    _node(
        "fiction.chapter",
        "chapter",
        inputs=("Outline",),
        outputs=("ChapterDraft",),
        required_memory=("StoryBible", "CharacterCard", "WorldFact"),
        quality_gates=("continuity",),
        next_nodes=("fiction.review",),
    ),
    _node(
        "fiction.review",
        "review",
        inputs=("ChapterDraft",),
        outputs=("ReviewReport",),
        tools=("review_stage_output",),
        quality_gates=("quality_score", "continuity"),
        human_review_policy="optional",
        next_nodes=("fiction.memory_extract",),
    ),
    _node(
        "fiction.memory_extract",
        "memory_extract",
        inputs=("ChapterDraft", "ReviewReport"),
        outputs=("IPMemoryPatch",),
        tools=("extract_ip_memory",),
        next_nodes=("drama.adaptation_blueprint",),
    ),
    _node(
        "drama.adaptation_blueprint",
        "blueprint",
        inputs=("IPMemory",),
        outputs=("AdaptationBlueprint",),
        required_memory=("StoryBible", "CharacterCard", "WorldFact"),
        next_nodes=("drama.episode_plot",),
    ),
    _node(
        "drama.episode_plot",
        "plot",
        inputs=("AdaptationBlueprint",),
        outputs=("EpisodePlot",),
        required_memory=("StoryBible", "NarrativeMemory"),
        next_nodes=("drama.script",),
    ),
    _node(
        "drama.script",
        "script",
        inputs=("EpisodePlot",),
        outputs=("DramaScript",),
        required_memory=("CharacterCard", "StyleGuide", "NarrativeMemory"),
        tools=("review_stage_output",),
        quality_gates=("dialogue_consistency", "continuity"),
        human_review_policy="required",
        next_nodes=("drama.style",),
    ),
    _node(
        "drama.style",
        "style",
        inputs=("DramaScript",),
        outputs=("StyleGuide",),
        required_memory=("StyleGuide",),
        tools=("review_stage_output",),
        human_review_policy="required",
        next_nodes=("drama.consistency",),
    ),
    _node(
        "drama.consistency",
        "consistency",
        inputs=("DramaScript", "StyleGuide"),
        outputs=("ConsistencyReport",),
        required_memory=("IPMemory",),
        tools=("review_stage_output",),
        quality_gates=("ip_consistency",),
        next_nodes=("drama.character_reference",),
    ),
    _node(
        "drama.character_reference",
        "character_refs",
        inputs=("StyleGuide",),
        outputs=("CharacterReference",),
        required_memory=("CharacterCard", "AssetBinding"),
        tools=("review_stage_output",),
        human_review_policy="required",
        next_nodes=("drama.storyboard",),
    ),
    _node(
        "drama.storyboard",
        "storyboard",
        inputs=("DramaScript", "CharacterReference"),
        outputs=("Storyboard",),
        required_memory=("CharacterCard", "WorldFact", "StyleGuide"),
        tools=("review_stage_output",),
        quality_gates=("visual_consistency", "shot_count"),
        human_review_policy="required",
        next_nodes=("drama.video_prompt_package",),
    ),
    _node(
        "drama.video_prompt_package",
        "video",
        inputs=("Storyboard",),
        outputs=("VideoPromptPackage",),
        required_memory=("CharacterCard", "StyleGuide", "AssetBinding"),
        tools=("review_stage_output",),
        quality_gates=("prompt_safety",),
        human_review_policy="required",
        next_nodes=("video.cost_confirmation",),
    ),
    _node(
        "video.cost_confirmation",
        "cost_confirmation",
        inputs=("VideoPromptPackage",),
        outputs=("CostApproval",),
        tools=("confirm_video_cost",),
        human_review_policy="required",
        cost_policy={"budget": "explicit_confirmation_required"},
        next_nodes=("video.submit_jobs",),
    ),
    _node(
        "video.submit_jobs",
        "submit_jobs",
        inputs=("VideoPromptPackage", "CostApproval"),
        outputs=("VideoJobBatch",),
        tools=("submit_video_jobs",),
        retry_policy={"max_attempts": 3, "backoff": "linear"},
        cost_policy={"budget": "approved_only"},
    ),
)

_DRAMA_STAGE_NODE_IDS = {
    "plot": "drama.episode_plot",
    "script": "drama.script",
    "style": "drama.style",
    "character_refs": "drama.character_reference",
    "storyboard": "drama.storyboard",
    "video": "drama.video_prompt_package",
}
