"""Dataclass models for workspace state."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


MATERIAL_STATUSES = {"inbox", "selected", "archived"}
TOPIC_CARD_STATUSES = {"draft", "approved", "archived"}
TASK_STATUSES = {"queued", "running", "needs_review", "approved", "failed", "canceled"}
DRAFT_STATUSES = {"needs_edit", "ready_for_package", "rejected"}
PACKAGE_STATUSES = {"generated", "confirmed", "exported"}
PROJECT_STATUSES = {"active", "archived"}
STORY_STATUSES = {"draft", "generated", "approved", "archived"}
VIDEO_ASSET_KINDS = {"image", "video", "audio", "subtitle", "package", "prompt"}
VIDEO_ASSET_STATUSES = {"generated", "approved", "rejected", "archived"}
REVIEW_TARGET_KINDS = {
    "project",
    "story",
    "drama_session",
    "stage_version",
    "video_run",
    "video_asset",
    "drama_project_package",
}
REVIEW_STATUSES = {"pending", "approved", "changes_requested", "rejected"}
DRAMA_SESSION_STATUSES = {
    "started",
    "generating",
    "awaiting_confirmation",
    "ready_for_next_stage",
    "video_started",
    "completed",
    "failed",
}
DRAMA_STAGE_EVENTS = {"draft", "revision", "confirmation", "restore", "system"}
DRAMA_PACKAGE_STATUSES = {"generated", "confirmed", "exported"}
DRAMA_STAGES = {"script", "style", "plot", "character_refs", "storyboard", "video"}
DRAMA_VIDEO_RUN_STATUSES = {"queued", "running", "completed", "failed"}
DRAMA_VIDEO_JOB_KINDS = {"generate_video", "refresh_status", "retry_shot"}
DRAMA_VIDEO_JOB_STATUSES = {"queued", "running", "completed", "failed", "canceled"}
PROJECT_RELEASE_STATUSES = {"confirmed"}
OPERATION_ACTIONS = {
    "start_session",
    "generate_stage",
    "confirm_stage",
    "request_revision",
    "retry_task",
    "cancel_task",
    "recover_task",
    "submit_video",
    "confirm_cost",
    "export_package",
}
OPERATION_TARGET_KINDS = {
    "project",
    "drama_session",
    "stage_version",
    "consistency_profile",
    "video_run",
    "video_job",
    "asset",
    "cost_ledger",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _validate_status(kind: str, value: str, allowed: set[str]) -> None:
    if value not in allowed:
        allowed_text = ", ".join(sorted(allowed))
        raise ValueError(
            f"Invalid {kind}.status={value!r}; expected one of: {allowed_text}"
        )


def _validate_choice(kind: str, value: str, allowed: set[str]) -> None:
    if value not in allowed:
        allowed_text = ", ".join(sorted(allowed))
        raise ValueError(
            f"Invalid {kind}={value!r}; expected one of: {allowed_text}"
        )


@dataclass
class Material:
    id: str
    source: str
    title: str
    excerpt: str = ""
    content: str = ""
    url: str = ""
    hot_score: float = 0.0
    tags: list[str] = field(default_factory=list)
    captured_at: str = field(default_factory=utc_now_iso)
    status: str = "inbox"

    def __post_init__(self) -> None:
        _validate_status("Material", self.status, MATERIAL_STATUSES)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Material":
        return cls(**data)


@dataclass
class TopicCard:
    id: str
    title: str
    source_material_ids: list[str] = field(default_factory=list)
    genre: str = ""
    platform: str = "zhihu"
    hook: str = ""
    angle: str = ""
    risk_notes: str = ""
    target_reader: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    status: str = "draft"

    def __post_init__(self) -> None:
        _validate_status("TopicCard", self.status, TOPIC_CARD_STATUSES)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "TopicCard":
        return cls(**data)


@dataclass
class StoryTask:
    id: str
    topic_card_id: str
    topic: str
    genre: str
    platform: str = "zhihu"
    chapters: int = 1
    mode: str = "full"
    priority: int = 0
    created_at: str = field(default_factory=utc_now_iso)
    started_at: str = ""
    finished_at: str = ""
    status: str = "queued"
    error: str = ""
    failed_stage: str = ""
    retry_count: int = 0
    run_id: str = ""

    def __post_init__(self) -> None:
        if self.chapters < 1:
            raise ValueError("StoryTask.chapters must be >= 1")
        _validate_status("StoryTask", self.status, TASK_STATUSES)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "StoryTask":
        return cls(**data)


@dataclass
class ReviewDraft:
    id: str
    task_id: str
    story_path: str
    original_body: str
    title: str
    synopsis: str = ""
    tags: list[str] = field(default_factory=list)
    body: str = ""
    review_result: dict = field(default_factory=dict)
    editor_notes: str = ""
    updated_at: str = field(default_factory=utc_now_iso)
    status: str = "needs_edit"

    def __post_init__(self) -> None:
        if not self.body:
            self.body = self.original_body
        _validate_status("ReviewDraft", self.status, DRAFT_STATUSES)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ReviewDraft":
        body_present = "body" in data
        draft = cls(**data)
        if body_present:
            draft.body = data["body"]
        return draft


@dataclass
class PublishPackage:
    id: str
    task_id: str
    platform: str
    title: str
    synopsis: str
    tags: list[str]
    content_path: str
    metadata_path: str
    package_dir: str
    created_at: str = field(default_factory=utc_now_iso)
    status: str = "generated"

    def __post_init__(self) -> None:
        _validate_status("PublishPackage", self.status, PACKAGE_STATUSES)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "PublishPackage":
        return cls(**data)


@dataclass
class Project:
    id: str
    title: str
    source: str = "zhihu"
    description: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    status: str = "active"

    def __post_init__(self) -> None:
        if not self.title:
            raise ValueError("Project.title is required")
        _validate_status("Project", self.status, PROJECT_STATUSES)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Project":
        return cls(**data)


@dataclass
class Story:
    id: str
    project_id: str
    title: str
    body_path: str
    version: int = 1
    task_id: str = ""
    synopsis: str = ""
    word_count: int = 0
    created_at: str = field(default_factory=utc_now_iso)
    status: str = "generated"

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValueError("Story.version must be >= 1")
        if self.word_count < 0:
            raise ValueError("Story.word_count must be >= 0")
        _validate_status("Story", self.status, STORY_STATUSES)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Story":
        return cls(**data)


@dataclass
class VideoAsset:
    id: str
    project_id: str
    run_id: str
    kind: str
    uri: str
    content_type: str = "application/octet-stream"
    provider: str = ""
    shot_id: str = ""
    prompt: str = ""
    metadata: dict = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    status: str = "generated"

    def __post_init__(self) -> None:
        _validate_choice("VideoAsset.kind", self.kind, VIDEO_ASSET_KINDS)
        _validate_status("VideoAsset", self.status, VIDEO_ASSET_STATUSES)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "VideoAsset":
        return cls(**data)


@dataclass
class Review:
    id: str
    project_id: str
    target_kind: str
    target_id: str
    reviewer: str = "human"
    decision: str = "pending"
    comment: str = ""
    metadata: dict = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        _validate_choice("Review.target_kind", self.target_kind, REVIEW_TARGET_KINDS)
        _validate_status("Review", self.decision, REVIEW_STATUSES)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Review":
        return cls(**data)


@dataclass
class DramaProjectSession:
    id: str
    story_path: str
    project_id: str = ""
    shot_limit: int = 1
    stage_drafts: dict = field(default_factory=dict)
    drafts: dict = field(default_factory=dict)
    confirmed_stages: list[str] = field(default_factory=list)
    pending_stage: str = ""
    video_run_id: str = ""
    rework_requests: list[dict] = field(default_factory=list)
    provider: str = "bailian"
    model: str = "deepseek-v4-pro"
    status: str = "started"
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    error: str = ""

    def __post_init__(self) -> None:
        if self.shot_limit < 1:
            raise ValueError("DramaProjectSession.shot_limit must be >= 1")
        _validate_status("DramaProjectSession", self.status, DRAMA_SESSION_STATUSES)
        for stage in self.confirmed_stages:
            if stage not in DRAMA_STAGES:
                raise ValueError(f"Invalid confirmed drama stage: {stage}")
        if self.pending_stage and self.pending_stage not in DRAMA_STAGES:
            raise ValueError(f"Invalid pending drama stage: {self.pending_stage}")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "DramaProjectSession":
        return cls(**data)


@dataclass
class DramaStageVersion:
    id: str
    run_id: str
    stage: str
    content: str
    event: str
    project_id: str = ""
    human_feedback: str = ""
    model: str = "deepseek-v4-pro"
    agent: str = "deepagent"
    created_at: str = field(default_factory=utc_now_iso)
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.stage not in DRAMA_STAGES:
            raise ValueError(f"Invalid DramaStageVersion.stage={self.stage!r}")
        _validate_status("DramaStageVersion", self.event, DRAMA_STAGE_EVENTS)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "DramaStageVersion":
        return cls(**data)


@dataclass
class DramaProjectPackage:
    id: str
    run_id: str
    story_path: str
    package_uri: str
    stage_count: int
    version_count: int
    video_run_id: str = ""
    provider: str = "bailian"
    created_at: str = field(default_factory=utc_now_iso)
    status: str = "generated"
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.stage_count < 0:
            raise ValueError("DramaProjectPackage.stage_count must be >= 0")
        if self.version_count < 0:
            raise ValueError("DramaProjectPackage.version_count must be >= 0")
        _validate_status("DramaProjectPackage", self.status, DRAMA_PACKAGE_STATUSES)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "DramaProjectPackage":
        return cls(**data)


@dataclass
class ProjectRelease:
    id: str
    project_id: str
    package_id: str
    run_id: str
    status: str = "confirmed"
    reviewer: str = "human"
    created_at: str = field(default_factory=utc_now_iso)
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.project_id:
            raise ValueError("ProjectRelease.project_id is required")
        if not self.package_id:
            raise ValueError("ProjectRelease.package_id is required")
        if not self.run_id:
            raise ValueError("ProjectRelease.run_id is required")
        _validate_status("ProjectRelease", self.status, PROJECT_RELEASE_STATUSES)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ProjectRelease":
        return cls(**data)


@dataclass
class CostLedgerEntry:
    id: str
    project_id: str
    release_id: str
    package_id: str
    run_id: str
    source: str
    amount_cny: float
    currency: str = "CNY"
    estimated: bool = True
    created_at: str = field(default_factory=utc_now_iso)
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.project_id:
            raise ValueError("CostLedgerEntry.project_id is required")
        if not self.release_id:
            raise ValueError("CostLedgerEntry.release_id is required")
        if not self.package_id:
            raise ValueError("CostLedgerEntry.package_id is required")
        if not self.run_id:
            raise ValueError("CostLedgerEntry.run_id is required")
        if not self.source:
            raise ValueError("CostLedgerEntry.source is required")
        if self.amount_cny < 0:
            raise ValueError("CostLedgerEntry.amount_cny must be >= 0")
        if self.currency != "CNY":
            raise ValueError("CostLedgerEntry.currency must be CNY")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CostLedgerEntry":
        return cls(**data)


@dataclass
class ConsistencyProfile:
    id: str
    project_id: str
    session_id: str
    source_version_ids: list[str] = field(default_factory=list)
    characters: list[dict] = field(default_factory=list)
    world_facts: list[dict] = field(default_factory=list)
    visual_style: dict = field(default_factory=dict)
    narrative_constraints: list[str] = field(default_factory=list)
    asset_bindings: dict = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        if not self.project_id:
            raise ValueError("ConsistencyProfile.project_id is required")
        if not self.session_id:
            raise ValueError("ConsistencyProfile.session_id is required")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ConsistencyProfile":
        return cls(**data)


@dataclass
class OperationLog:
    id: str
    project_id: str
    action: str
    actor: str
    target_kind: str
    target_id: str
    session_id: str = ""
    run_id: str = ""
    message: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.project_id:
            raise ValueError("OperationLog.project_id is required")
        if not self.actor:
            raise ValueError("OperationLog.actor is required")
        if not self.target_id:
            raise ValueError("OperationLog.target_id is required")
        _validate_choice("OperationLog.action", self.action, OPERATION_ACTIONS)
        _validate_choice(
            "OperationLog.target_kind",
            self.target_kind,
            OPERATION_TARGET_KINDS,
        )

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "OperationLog":
        return cls(**data)


@dataclass
class DramaVideoRun:
    id: str
    story_path: str
    project_id: str = ""
    shot_limit: int = 1
    stage_drafts: dict = field(default_factory=dict)
    status: str = "queued"
    submitted_count: int = 0
    jobs_path: str = ""
    package_dir: str = ""
    error: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        if self.shot_limit < 1:
            raise ValueError("DramaVideoRun.shot_limit must be >= 1")
        if self.submitted_count < 0:
            raise ValueError("DramaVideoRun.submitted_count must be >= 0")
        _validate_status("DramaVideoRun", self.status, DRAMA_VIDEO_RUN_STATUSES)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "DramaVideoRun":
        return cls(**data)


@dataclass
class DramaVideoJob:
    id: str
    kind: str
    run_id: str
    shot_id: str = ""
    status: str = "queued"
    payload: dict = field(default_factory=dict)
    result: dict = field(default_factory=dict)
    error: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        _validate_choice("DramaVideoJob.kind", self.kind, DRAMA_VIDEO_JOB_KINDS)
        _validate_status("DramaVideoJob", self.status, DRAMA_VIDEO_JOB_STATUSES)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "DramaVideoJob":
        return cls(**data)
