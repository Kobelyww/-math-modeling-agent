"""Video generation providers for short-drama shots."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

import requests

from .models import DramaShot


class DramaVideoError(RuntimeError):
    """Raised when video generation cannot be submitted or queried."""


@dataclass(frozen=True)
class BailianVideoConfig:
    api_key: str
    model: str = "wanx2.1-t2v-turbo"
    submit_url: str = "https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis"
    task_url: str = "https://dashscope.aliyuncs.com/api/v1/tasks"
    timeout_seconds: int = 60
    size: str = "1280*720"


@dataclass(slots=True)
class VideoJob:
    provider: str
    provider_job_id: str
    shot_id: str
    status: str
    video_url: str = ""
    error: str = ""
    raw_response: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VideoJob":
        return cls(
            provider=str(data.get("provider") or ""),
            provider_job_id=str(data.get("provider_job_id") or ""),
            shot_id=str(data.get("shot_id") or ""),
            status=str(data.get("status") or "UNKNOWN"),
            video_url=str(data.get("video_url") or ""),
            error=str(data.get("error") or ""),
            raw_response=data.get("raw_response") if isinstance(data.get("raw_response"), dict) else None,
        )


class VideoProvider(Protocol):
    provider_name: str

    def submit_shot(self, shot: DramaShot) -> VideoJob:
        ...

    def get_job(self, provider_job_id: str, shot_id: str = "") -> VideoJob:
        ...


def load_bailian_video_config() -> BailianVideoConfig:
    """Load DashScope/Bailian video settings from environment variables."""
    api_key = (
        os.getenv("DASHSCOPE_API_KEY")
        or os.getenv("BAILIAN_API_KEY")
        or os.getenv("EMBEDDING_API_KEY")
    )
    if not api_key:
        raise DramaVideoError(
            "Missing DASHSCOPE_API_KEY, BAILIAN_API_KEY, or EMBEDDING_API_KEY in .env"
        )

    return BailianVideoConfig(
        api_key=api_key,
        model=os.getenv("BAILIAN_VIDEO_MODEL", "wanx2.1-t2v-turbo"),
        submit_url=os.getenv(
            "BAILIAN_VIDEO_SUBMIT_URL",
            "https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis",
        ),
        task_url=os.getenv("BAILIAN_VIDEO_TASK_URL", "https://dashscope.aliyuncs.com/api/v1/tasks"),
        timeout_seconds=int(os.getenv("BAILIAN_VIDEO_TIMEOUT_SECONDS", "60")),
        size=os.getenv("BAILIAN_VIDEO_SIZE", "1280*720"),
    )


class BailianVideoProvider:
    """Submit and query text-to-video tasks through Bailian/DashScope."""

    provider_name = "bailian"

    def __init__(
        self,
        api_key: str | None = None,
        config: BailianVideoConfig | None = None,
        http_client=None,
    ) -> None:
        if config is None:
            config = load_bailian_video_config() if api_key is None else BailianVideoConfig(api_key=api_key)
        elif api_key is not None:
            config = BailianVideoConfig(
                api_key=api_key,
                model=config.model,
                submit_url=config.submit_url,
                task_url=config.task_url,
                timeout_seconds=config.timeout_seconds,
                size=config.size,
            )
        self.config = config
        self.http_client = http_client or requests

    def submit_shot(self, shot: DramaShot) -> VideoJob:
        response = self.http_client.post(
            self.config.submit_url,
            headers=self._headers(async_task=True),
            json=self._payload_for_shot(shot),
            timeout=self.config.timeout_seconds,
        )
        data = self._parse_response(response)
        return self._job_from_response(data, shot_id=shot.id)

    def get_job(self, provider_job_id: str, shot_id: str = "") -> VideoJob:
        response = self.http_client.get(
            f"{self.config.task_url.rstrip('/')}/{provider_job_id}",
            headers=self._headers(async_task=False),
            timeout=self.config.timeout_seconds,
        )
        data = self._parse_response(response)
        return self._job_from_response(data, shot_id=shot_id)

    def _payload_for_shot(self, shot: DramaShot) -> dict[str, Any]:
        return {
            "model": self.config.model,
            "input": {
                "prompt": self._prompt_for_shot(shot),
                "negative_prompt": shot.negative_prompt,
            },
            "parameters": {
                "duration": int(shot.duration_seconds),
                "size": self.config.size,
            },
        }

    @staticmethod
    def _prompt_for_shot(shot: DramaShot) -> str:
        parts = [
            shot.visual_prompt.strip(),
            f"Action: {shot.action.strip()}",
            f"Emotion: {shot.emotion.strip()}",
            f"Camera: {shot.camera.strip()}",
        ]
        if shot.dialogue.strip():
            parts.append(f"Dialogue subtitle: {shot.dialogue.strip()}")
        if shot.consistency_refs:
            parts.append(f"Consistency refs: {', '.join(shot.consistency_refs)}")
        return "\n".join(part for part in parts if part)

    def _headers(self, async_task: bool) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        if async_task:
            headers["X-DashScope-Async"] = "enable"
        return headers

    @staticmethod
    def _parse_response(response) -> dict[str, Any]:
        if response.status_code >= 400:
            raise DramaVideoError(f"Bailian video API failed: HTTP {response.status_code} {response.text}")
        try:
            data = response.json()
        except ValueError as exc:
            raise DramaVideoError(f"Bailian video API returned invalid JSON: {response.text}") from exc
        if "code" in data and data.get("code"):
            message = data.get("message") or data.get("code")
            raise DramaVideoError(f"Bailian video API failed: {message}")
        return data

    def _job_from_response(self, data: dict[str, Any], shot_id: str) -> VideoJob:
        output = data.get("output") or {}
        task_id = str(output.get("task_id") or "")
        if not task_id:
            raise DramaVideoError(f"Bailian video API response missing task_id: {data}")
        status = str(output.get("task_status") or "UNKNOWN")
        video_url = str(
            output.get("video_url")
            or output.get("url")
            or (output.get("results") or [{}])[0].get("url", "")
        )
        error = str(output.get("message") or output.get("error") or "")
        return VideoJob(
            provider=self.provider_name,
            provider_job_id=task_id,
            shot_id=shot_id,
            status=status,
            video_url=video_url,
            error=error,
            raw_response=data,
        )


def create_video_provider(name: str | None = None, **kwargs) -> VideoProvider:
    """Create a configured video provider.

    Bailian/DashScope is the default because it supports RMB settlement in the
    user's current deployment path. Additional domestic providers can register
    behind this factory without changing the calling workflow.
    """
    provider_name = (name or os.getenv("ZH_VIDEO_PROVIDER") or "bailian").strip().lower()
    if provider_name in {"bailian", "dashscope", "aliyun"}:
        return BailianVideoProvider(**kwargs)
    raise DramaVideoError(f"Unsupported video provider: {provider_name}")


class VideoJobStore:
    """Append-only JSONL store for generated video tasks."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, job: VideoJob) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(job.to_dict(), ensure_ascii=False) + "\n")

    def list(self) -> list[VideoJob]:
        if not self.path.exists():
            return []
        jobs: list[VideoJob] = []
        with self.path.open(encoding="utf-8") as file:
            for line in file:
                if not line.strip():
                    continue
                try:
                    jobs.append(VideoJob.from_dict(json.loads(line)))
                except (json.JSONDecodeError, TypeError, ValueError):
                    continue
        return jobs

    def replace_all(self, jobs: list[VideoJob]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as file:
            for job in jobs:
                file.write(json.dumps(job.to_dict(), ensure_ascii=False) + "\n")
