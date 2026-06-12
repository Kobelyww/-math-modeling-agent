"""Pydantic request schemas for workspace API routes."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ManualMaterialRequest(BaseModel):
    title: str
    content: str = ""
    excerpt: str = ""
    tags: list[str] = Field(default_factory=list)
    url: str = ""
    hot_score: float = 0.0


class ImportScrapedRequest(BaseModel):
    items: list[dict]


class TopicCardRequest(BaseModel):
    title: str
    source_material_ids: list[str] = Field(default_factory=list)
    genre: str = ""
    platform: str = "zhihu"
    hook: str = ""
    angle: str = ""
    risk_notes: str = ""
    target_reader: str = ""


class CreateTaskRequest(BaseModel):
    chapters: int = Field(default=1, ge=1)
    mode: str = "full"
    priority: int = 0


class DraftUpdateRequest(BaseModel):
    title: str | None = None
    synopsis: str | None = None
    tags: list[str] | None = None
    body: str | None = None
    editor_notes: str | None = None


class GeneratePackageRequest(BaseModel):
    task_id: str
    platform: str = "zhihu"
