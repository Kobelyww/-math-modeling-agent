"""Dataclass models for workspace state."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from uuid import uuid4


MATERIAL_STATUSES = {"inbox", "selected", "archived"}
TOPIC_CARD_STATUSES = {"draft", "approved", "archived"}
TASK_STATUSES = {"queued", "running", "needs_review", "approved", "failed", "canceled"}
DRAFT_STATUSES = {"needs_edit", "ready_for_package", "rejected"}
PACKAGE_STATUSES = {"generated", "confirmed", "exported"}


def utc_now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _validate_status(kind: str, value: str, allowed: set[str]) -> None:
    if value not in allowed:
        allowed_text = ", ".join(sorted(allowed))
        raise ValueError(
            f"Invalid {kind}.status={value!r}; expected one of: {allowed_text}"
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
