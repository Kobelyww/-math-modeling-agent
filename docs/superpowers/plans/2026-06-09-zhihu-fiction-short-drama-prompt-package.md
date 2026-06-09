# Zhihu Fiction Short Drama Prompt Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a CLI-accessible post-processing module that converts a generated `zhihu_fiction` novel into a short-drama video prompt package.

**Architecture:** Add a standalone `zhihu_fiction/drama/` package with data models, LLM adaptation logic, prompt templates, and file export. Integrate it into the existing CLI as `/drama`, using `WorkflowResult.final_story` as the source and leaving the fiction pipeline unchanged.

**Tech Stack:** Python 3.11, dataclasses, JSON, pytest, existing `create_llm`, existing `WorkflowResult`, existing file-backed `zhihu_fiction/output/`.

---

## Scope

This plan implements the CLI-first version of `docs/superpowers/specs/2026-06-09-zhihu-fiction-short-drama-prompt-package-design.md`.

It builds:

- `DramaProject` domain models and validation.
- LLM adapter that turns a `WorkflowResult` into a validated drama project.
- Prompt templates for adaptation blueprint and shot-level generation.
- Exporter that writes Markdown and JSON package files.
- CLI `/drama` command.
- README updates.
- Focused tests.

It does not build:

- Video generation API calls.
- Video provider adapters.
- Web API route.
- Video queue or generated-video review workflow.

## File Structure

Create:

- `zhihu_fiction/drama/__init__.py`
  - Public exports for drama models, adapter, and exporter.

- `zhihu_fiction/drama/models.py`
  - Dataclasses, serialization, and validation rules for drama projects.

- `zhihu_fiction/drama/prompts.py`
  - Prompt templates and formatting helpers.

- `zhihu_fiction/drama/adapter.py`
  - LLM invocation, JSON extraction, validation, and error types.

- `zhihu_fiction/drama/exporter.py`
  - Package directory creation and Markdown/JSON file writing.

- `zhihu_fiction/tests/test_drama_models.py`
  - Model serialization and validation tests.

- `zhihu_fiction/tests/test_drama_adapter.py`
  - Fake-LLM adapter tests.

- `zhihu_fiction/tests/test_drama_exporter.py`
  - Export file tests.

- `zhihu_fiction/tests/test_cli_drama.py`
  - CLI command behavior tests.

Modify:

- `zhihu_fiction/cli.py`
  - Add `/drama` help text, `cmd_drama`, and command dispatch.

- `zhihu_fiction/README.md`
  - Document the short-drama prompt package workflow.

## Dirty Worktree Safety

The repository already has unrelated modified and untracked files. During execution, only stage files listed in each task.

Before each commit, run:

```bash
git diff --cached --name-status
```

The staged list must contain only the files named in that task. If unrelated files are staged, stop and unstage them before committing.

---

## Task 1: Add Drama Domain Models

**Files:**
- Create: `zhihu_fiction/drama/__init__.py`
- Create: `zhihu_fiction/drama/models.py`
- Create: `zhihu_fiction/tests/test_drama_models.py`

- [ ] **Step 1: Write failing model tests**

Create `zhihu_fiction/tests/test_drama_models.py` with this content:

```python
"""Tests for short-drama domain models."""
from __future__ import annotations

import pytest

from zhihu_fiction.drama.models import (
    DramaCharacter,
    DramaEpisode,
    DramaLocation,
    DramaProject,
    DramaShot,
    DramaValidationError,
)


def _shots(count: int = 6) -> list[DramaShot]:
    return [
        DramaShot(
            id=f"ep01_sc01_sh{i:02d}",
            episode_index=1,
            scene_index=1,
            shot_index=i,
            duration_seconds=6,
            location_id="living_room",
            character_ids=["heroine"],
            action=f"女主完成第 {i} 个关键动作。",
            dialogue="我不会再退让。",
            emotion="克制但坚定",
            camera="medium close-up, slow push in",
            visual_prompt="modern Chinese living room, cinematic lighting, medium close-up",
            negative_prompt="low quality, blurry, distorted face",
            consistency_refs=["character.heroine", "location.living_room"],
        )
        for i in range(1, count + 1)
    ]


def make_project(**overrides) -> DramaProject:
    project = DramaProject(
        title="重生后我不再忍让",
        source_title="测试主题",
        genre="复仇",
        logline="被背叛的女主重生后用真相反击。",
        audience="喜欢复仇爽感和家庭冲突的短剧观众",
        episode_count=1,
        characters=[
            DramaCharacter(
                id="heroine",
                name="林夏",
                role="女主",
                age_range="25-30",
                appearance="黑色长发，冷静克制，眼神坚定",
                costume="白色衬衫和深色长裤",
                personality="隐忍、聪明、行动果断",
                motivation="查清背叛真相并夺回人生",
                consistency_prompt="林夏，25岁左右，中国女性，黑色长发，白色衬衫，冷静坚定",
            )
        ],
        locations=[
            DramaLocation(
                id="living_room",
                name="林家客厅",
                visual_style="现代中式家庭客厅，压抑而整洁",
                time_period="现代",
                lighting="夜晚室内暖光，局部阴影",
                consistency_prompt="modern Chinese family living room, warm indoor light, tense mood",
            )
        ],
        episodes=[
            DramaEpisode(
                index=1,
                title="重生醒来",
                hook="女主在被害当天醒来，发现时间倒流。",
                synopsis="林夏重新回到被陷害的夜晚，第一次选择正面反击。",
                cliffhanger="她拿出录音笔，继母脸色骤变。",
                shots=_shots(),
            )
        ],
        adaptation_notes=["保留原小说的复仇主线，压缩支线。"],
        risk_notes=["避免过度暴力和违法细节。"],
    )
    for key, value in overrides.items():
        setattr(project, key, value)
    return project


def test_project_serializes_to_dict_and_back():
    project = make_project()

    data = project.to_dict()
    restored = DramaProject.from_dict(data)

    assert restored.title == "重生后我不再忍让"
    assert restored.episode_count == 1
    assert restored.total_shots == 6
    assert restored.characters[0].id == "heroine"
    assert restored.episodes[0].shots[0].visual_prompt


def test_rejects_more_than_ten_episodes():
    episodes = [
        DramaEpisode(
            index=i,
            title=f"第{i}集",
            hook="开场钩子",
            synopsis="剧情简介",
            cliffhanger="结尾反转",
            shots=[
                DramaShot(
                    id=f"ep{i:02d}_sc01_sh{j:02d}",
                    episode_index=i,
                    scene_index=1,
                    shot_index=j,
                    duration_seconds=6,
                    location_id="living_room",
                    character_ids=["heroine"],
                    action="角色行动",
                    dialogue="对白",
                    emotion="紧张",
                    camera="medium shot",
                    visual_prompt="cinematic shot",
                    negative_prompt="low quality",
                    consistency_refs=["character.heroine", "location.living_room"],
                )
                for j in range(1, 7)
            ],
        )
        for i in range(1, 12)
    ]
    project = make_project(episode_count=11, episodes=episodes)

    with pytest.raises(DramaValidationError, match="episode_count"):
        project.validate()


def test_rejects_invalid_shot_duration():
    project = make_project()
    project.episodes[0].shots[0].duration_seconds = 9

    with pytest.raises(DramaValidationError, match="duration_seconds"):
        project.validate()


def test_rejects_unknown_character_reference():
    project = make_project()
    project.episodes[0].shots[0].character_ids = ["unknown"]

    with pytest.raises(DramaValidationError, match="unknown character"):
        project.validate()


def test_rejects_unknown_location_reference():
    project = make_project()
    project.episodes[0].shots[0].location_id = "unknown_location"

    with pytest.raises(DramaValidationError, match="unknown location"):
        project.validate()


def test_rejects_episode_with_too_few_shots():
    project = make_project()
    project.episodes[0].shots = project.episodes[0].shots[:5]

    with pytest.raises(DramaValidationError, match="6-12 shots"):
        project.validate()
```

- [ ] **Step 2: Run model tests and confirm they fail**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_drama_models.py -v
```

Expected result:

```text
FAILED zhihu_fiction/tests/test_drama_models.py
ModuleNotFoundError: No module named 'zhihu_fiction.drama'
```

- [ ] **Step 3: Create drama package exports**

Create `zhihu_fiction/drama/__init__.py` with this content:

```python
"""Short-drama prompt package generation."""
from __future__ import annotations

from .models import (
    DramaCharacter,
    DramaEpisode,
    DramaLocation,
    DramaProject,
    DramaShot,
    DramaValidationError,
)

__all__ = [
    "DramaCharacter",
    "DramaEpisode",
    "DramaLocation",
    "DramaProject",
    "DramaShot",
    "DramaValidationError",
]
```

- [ ] **Step 4: Create models implementation**

Create `zhihu_fiction/drama/models.py` with this content:

```python
"""Domain models for novel-to-short-drama prompt packages."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


class DramaValidationError(ValueError):
    """Raised when a drama project cannot be used for prompt-package export."""


@dataclass(slots=True)
class DramaCharacter:
    id: str
    name: str
    role: str
    age_range: str
    appearance: str
    costume: str
    personality: str
    motivation: str
    consistency_prompt: str


@dataclass(slots=True)
class DramaLocation:
    id: str
    name: str
    visual_style: str
    time_period: str
    lighting: str
    consistency_prompt: str


@dataclass(slots=True)
class DramaShot:
    id: str
    episode_index: int
    scene_index: int
    shot_index: int
    duration_seconds: int
    location_id: str
    character_ids: list[str]
    action: str
    dialogue: str
    emotion: str
    camera: str
    visual_prompt: str
    negative_prompt: str
    consistency_refs: list[str]


@dataclass(slots=True)
class DramaEpisode:
    index: int
    title: str
    hook: str
    synopsis: str
    cliffhanger: str
    shots: list[DramaShot] = field(default_factory=list)


@dataclass(slots=True)
class DramaProject:
    title: str
    source_title: str
    genre: str
    logline: str
    audience: str
    episode_count: int
    characters: list[DramaCharacter] = field(default_factory=list)
    locations: list[DramaLocation] = field(default_factory=list)
    episodes: list[DramaEpisode] = field(default_factory=list)
    adaptation_notes: list[str] = field(default_factory=list)
    risk_notes: list[str] = field(default_factory=list)

    @property
    def total_shots(self) -> int:
        return sum(len(episode.shots) for episode in self.episodes)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DramaProject":
        characters = [
            DramaCharacter(**item)
            for item in data.get("characters", [])
        ]
        locations = [
            DramaLocation(**item)
            for item in data.get("locations", [])
        ]
        episodes = []
        for item in data.get("episodes", []):
            episode_data = dict(item)
            shots = [
                DramaShot(**shot)
                for shot in episode_data.pop("shots", [])
            ]
            episodes.append(DramaEpisode(**episode_data, shots=shots))

        project = cls(
            title=data.get("title", ""),
            source_title=data.get("source_title", ""),
            genre=data.get("genre", ""),
            logline=data.get("logline", ""),
            audience=data.get("audience", ""),
            episode_count=int(data.get("episode_count", 0)),
            characters=characters,
            locations=locations,
            episodes=episodes,
            adaptation_notes=list(data.get("adaptation_notes", [])),
            risk_notes=list(data.get("risk_notes", [])),
        )
        project.validate()
        return project

    def validate(self) -> None:
        if not self.title.strip():
            raise DramaValidationError("title is required")
        if not self.source_title.strip():
            raise DramaValidationError("source_title is required")
        if not self.logline.strip():
            raise DramaValidationError("logline is required")
        if not 1 <= self.episode_count <= 10:
            raise DramaValidationError("episode_count must be between 1 and 10")
        if len(self.episodes) != self.episode_count:
            raise DramaValidationError(
                f"episodes length {len(self.episodes)} does not match episode_count {self.episode_count}"
            )

        character_ids = self._unique_ids("character", [character.id for character in self.characters])
        location_ids = self._unique_ids("location", [location.id for location in self.locations])
        if not character_ids:
            raise DramaValidationError("at least one character is required")
        if not location_ids:
            raise DramaValidationError("at least one location is required")

        for episode in self.episodes:
            if episode.index < 1:
                raise DramaValidationError("episode index must be 1 or greater")
            if not 6 <= len(episode.shots) <= 12:
                raise DramaValidationError(
                    f"episode {episode.index} must contain 6-12 shots, got {len(episode.shots)}"
                )
            for shot in episode.shots:
                self._validate_shot(episode, shot, character_ids, location_ids)

    @staticmethod
    def _unique_ids(kind: str, values: list[str]) -> set[str]:
        cleaned = [value.strip() for value in values if value and value.strip()]
        if len(cleaned) != len(set(cleaned)):
            raise DramaValidationError(f"duplicate {kind} id")
        return set(cleaned)

    @staticmethod
    def _validate_shot(
        episode: DramaEpisode,
        shot: DramaShot,
        character_ids: set[str],
        location_ids: set[str],
    ) -> None:
        if shot.episode_index != episode.index:
            raise DramaValidationError(
                f"shot {shot.id} episode_index {shot.episode_index} does not match episode {episode.index}"
            )
        if not 5 <= int(shot.duration_seconds) <= 8:
            raise DramaValidationError(
                f"shot {shot.id} duration_seconds must be between 5 and 8"
            )
        if shot.location_id not in location_ids:
            raise DramaValidationError(
                f"shot {shot.id} references unknown location {shot.location_id}"
            )
        for character_id in shot.character_ids:
            if character_id not in character_ids:
                raise DramaValidationError(
                    f"shot {shot.id} references unknown character {character_id}"
                )
        if not shot.character_ids:
            raise DramaValidationError(f"shot {shot.id} must reference at least one character")
        if not shot.visual_prompt.strip():
            raise DramaValidationError(f"shot {shot.id} visual_prompt is required")
        if not shot.negative_prompt.strip():
            raise DramaValidationError(f"shot {shot.id} negative_prompt is required")
        if not shot.consistency_refs:
            raise DramaValidationError(f"shot {shot.id} consistency_refs is required")
```

- [ ] **Step 5: Run model tests and fix package import if needed**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_drama_models.py -v
```

Expected result after `models.py` is in place:

```text
6 passed
```

- [ ] **Step 6: Commit model task**

Run:

```bash
git add zhihu_fiction/drama/__init__.py
git add zhihu_fiction/drama/models.py
git add zhihu_fiction/tests/test_drama_models.py
git diff --cached --name-status
git commit -m "feat: add short-drama domain models"
```

Expected staged files:

```text
A	zhihu_fiction/drama/__init__.py
A	zhihu_fiction/drama/models.py
A	zhihu_fiction/tests/test_drama_models.py
```

---

## Task 2: Add Prompts and LLM Adapter

**Files:**
- Create: `zhihu_fiction/drama/prompts.py`
- Modify: `zhihu_fiction/drama/adapter.py`
- Create: `zhihu_fiction/tests/test_drama_adapter.py`

- [ ] **Step 1: Write failing adapter tests**

Create `zhihu_fiction/tests/test_drama_adapter.py` with this content:

```python
"""Tests for LLM-based novel-to-drama adaptation."""
from __future__ import annotations

import json

import pytest

from zhihu_fiction.drama.adapter import DramaAdapter, DramaAdapterError, extract_json_object


class FakeResponse:
    def __init__(self, content):
        self.content = content


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        if not self.responses:
            raise AssertionError("FakeLLM received more calls than expected")
        return FakeResponse(self.responses.pop(0))


def valid_project_payload() -> dict:
    shots = [
        {
            "id": f"ep01_sc01_sh{i:02d}",
            "episode_index": 1,
            "scene_index": 1,
            "shot_index": i,
            "duration_seconds": 6,
            "location_id": "living_room",
            "character_ids": ["heroine"],
            "action": f"女主完成第 {i} 个关键动作。",
            "dialogue": "我不会再退让。",
            "emotion": "克制但坚定",
            "camera": "medium close-up, slow push in",
            "visual_prompt": "modern Chinese living room, cinematic lighting",
            "negative_prompt": "low quality, blurry, distorted face",
            "consistency_refs": ["character.heroine", "location.living_room"],
        }
        for i in range(1, 7)
    ]
    return {
        "title": "重生后我不再忍让",
        "source_title": "测试主题",
        "genre": "复仇",
        "logline": "被背叛的女主重生后用真相反击。",
        "audience": "喜欢复仇爽感和家庭冲突的短剧观众",
        "episode_count": 1,
        "characters": [
            {
                "id": "heroine",
                "name": "林夏",
                "role": "女主",
                "age_range": "25-30",
                "appearance": "黑色长发，冷静克制，眼神坚定",
                "costume": "白色衬衫和深色长裤",
                "personality": "隐忍、聪明、行动果断",
                "motivation": "查清背叛真相并夺回人生",
                "consistency_prompt": "林夏，25岁左右，中国女性，黑色长发，白色衬衫，冷静坚定",
            }
        ],
        "locations": [
            {
                "id": "living_room",
                "name": "林家客厅",
                "visual_style": "现代中式家庭客厅，压抑而整洁",
                "time_period": "现代",
                "lighting": "夜晚室内暖光，局部阴影",
                "consistency_prompt": "modern Chinese family living room, warm indoor light, tense mood",
            }
        ],
        "episodes": [
            {
                "index": 1,
                "title": "重生醒来",
                "hook": "女主在被害当天醒来，发现时间倒流。",
                "synopsis": "林夏重新回到被陷害的夜晚，第一次选择正面反击。",
                "cliffhanger": "她拿出录音笔，继母脸色骤变。",
                "shots": shots,
            }
        ],
        "adaptation_notes": ["保留原小说的复仇主线，压缩支线。"],
        "risk_notes": ["避免过度暴力和违法细节。"],
    }


def test_extract_json_object_from_markdown_fence():
    text = '说明\n```json\n{"a": 1, "b": {"c": 2}}\n```\n结束'
    assert extract_json_object(text) == '{"a": 1, "b": {"c": 2}}'


def test_adapter_parses_valid_llm_json():
    blueprint = {"episode_count": 1, "notes": ["保留复仇主线"]}
    payload = valid_project_payload()
    llm = FakeLLM([
        json.dumps(blueprint, ensure_ascii=False),
        json.dumps(payload, ensure_ascii=False),
    ])

    project = DramaAdapter(llm).adapt(
        source_title="测试主题",
        genre="复仇",
        story="女主被陷害后重生，决定反击。",
        synthesis="发布方案",
    )

    assert project.title == "重生后我不再忍让"
    assert project.episode_count == 1
    assert project.total_shots == 6
    assert len(llm.prompts) == 2
    assert "测试主题" in llm.prompts[0]
    assert "保留复仇主线" in llm.prompts[1]


def test_adapter_rejects_empty_story():
    llm = FakeLLM([])

    with pytest.raises(DramaAdapterError, match="story is empty"):
        DramaAdapter(llm).adapt(
            source_title="测试主题",
            genre="复仇",
            story="",
            synthesis="",
        )


def test_adapter_preserves_raw_output_for_invalid_json():
    llm = FakeLLM([
        '{"episode_count": 1}',
        "这不是 JSON",
    ])

    with pytest.raises(DramaAdapterError) as exc_info:
        DramaAdapter(llm).adapt(
            source_title="测试主题",
            genre="复仇",
            story="女主被陷害后重生。",
            synthesis="发布方案",
        )

    assert "Could not parse drama project JSON" in str(exc_info.value)
    assert exc_info.value.raw_output == "这不是 JSON"


def test_adapter_wraps_validation_errors_with_raw_output():
    payload = valid_project_payload()
    payload["episode_count"] = 11
    llm = FakeLLM([
        '{"episode_count": 11}',
        json.dumps(payload, ensure_ascii=False),
    ])

    with pytest.raises(DramaAdapterError) as exc_info:
        DramaAdapter(llm).adapt(
            source_title="测试主题",
            genre="复仇",
            story="女主被陷害后重生。",
            synthesis="发布方案",
        )

    assert "episode_count" in str(exc_info.value)
    assert "episode_count" in exc_info.value.raw_output
```

- [ ] **Step 2: Run adapter tests and confirm they fail**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_drama_adapter.py -v
```

Expected result:

```text
FAILED zhihu_fiction/tests/test_drama_adapter.py
ImportError or AttributeError for DramaAdapter/extract_json_object
```

- [ ] **Step 3: Add prompt templates**

Create `zhihu_fiction/drama/prompts.py` with this content:

```python
"""Prompt templates for novel-to-short-drama adaptation."""
from __future__ import annotations


BLUEPRINT_PROMPT = """你是短剧改编策划。请把下面的知乎/网文小说改编成适合视频生成模型生产的竖屏短剧蓝图。

硬性规格：
- 最多 10 集。
- 每集 60-90 秒。
- 每集后半段必须有反转或悬念。
- 保留小说最强的情绪驱动和爽点。
- 删除不适合短视频呈现的冗长心理描写。
- 不要调用任何视频生成模型。

小说标题：{source_title}
题材：{genre}
发布方案参考：{synthesis}

小说正文：
{story}

只输出 JSON，字段如下：
{{
  "title": "短剧标题",
  "source_title": "{source_title}",
  "genre": "{genre}",
  "logline": "一句话卖点",
  "audience": "目标观众",
  "episode_count": 1,
  "characters": [
    {{
      "id": "heroine",
      "name": "角色名",
      "role": "角色功能",
      "age_range": "年龄段",
      "appearance": "稳定外貌",
      "costume": "稳定服装",
      "personality": "性格",
      "motivation": "核心动机",
      "consistency_prompt": "可复用的角色视觉一致性提示词"
    }}
  ],
  "locations": [
    {{
      "id": "living_room",
      "name": "场景名",
      "visual_style": "视觉风格",
      "time_period": "时代背景",
      "lighting": "灯光",
      "consistency_prompt": "可复用的场景一致性提示词"
    }}
  ],
  "episode_outline": [
    {{
      "index": 1,
      "title": "集标题",
      "hook": "开场钩子",
      "synopsis": "本集剧情",
      "cliffhanger": "结尾悬念"
    }}
  ],
  "adaptation_notes": ["改编策略"],
  "risk_notes": ["内容风险和规避方式"]
}}"""


SHOT_PACKAGE_PROMPT = """你是短剧分镜导演和视频模型 Prompt 工程师。请基于短剧蓝图，生成完整的镜头级短剧 Prompt 包。

硬性规格：
- episode_count 必须与蓝图一致，且不超过 10。
- 每集必须有 6-12 个镜头。
- 每个镜头 duration_seconds 必须在 5-8 秒之间。
- 每个镜头必须引用已存在的 character id 和 location id。
- 每个镜头必须有中文 action、dialogue、emotion。
- 每个镜头必须有 camera、visual_prompt、negative_prompt、consistency_refs。
- visual_prompt 可以使用英文或中英混合，必须利于视频模型理解。
- 不要输出 Markdown，不要解释，只输出 JSON。

原小说标题：{source_title}
题材：{genre}

短剧蓝图 JSON：
{blueprint_json}

小说正文参考：
{story}

输出 JSON 字段必须匹配：
{{
  "title": "短剧标题",
  "source_title": "{source_title}",
  "genre": "{genre}",
  "logline": "一句话卖点",
  "audience": "目标观众",
  "episode_count": 1,
  "characters": [],
  "locations": [],
  "episodes": [
    {{
      "index": 1,
      "title": "集标题",
      "hook": "开场钩子",
      "synopsis": "本集剧情",
      "cliffhanger": "结尾悬念",
      "shots": [
        {{
          "id": "ep01_sc01_sh01",
          "episode_index": 1,
          "scene_index": 1,
          "shot_index": 1,
          "duration_seconds": 6,
          "location_id": "living_room",
          "character_ids": ["heroine"],
          "action": "画面动作",
          "dialogue": "对白，没有对白时写空字符串",
          "emotion": "情绪",
          "camera": "camera movement and framing",
          "visual_prompt": "video generation prompt",
          "negative_prompt": "low quality, blurry, distorted face, inconsistent costume",
          "consistency_refs": ["character.heroine", "location.living_room"]
        }}
      ]
    }}
  ],
  "adaptation_notes": [],
  "risk_notes": []
}}"""


def build_blueprint_prompt(source_title: str, genre: str, story: str, synthesis: str = "") -> str:
    return BLUEPRINT_PROMPT.format(
        source_title=source_title,
        genre=genre or "未指定",
        story=story,
        synthesis=synthesis or "无",
    )


def build_shot_package_prompt(
    source_title: str,
    genre: str,
    story: str,
    blueprint_json: str,
) -> str:
    return SHOT_PACKAGE_PROMPT.format(
        source_title=source_title,
        genre=genre or "未指定",
        story=story,
        blueprint_json=blueprint_json,
    )
```

- [ ] **Step 4: Add adapter implementation**

Replace `zhihu_fiction/drama/adapter.py` with this content:

```python
"""LLM adapter that converts novels into short-drama projects."""
from __future__ import annotations

import json
import re
from typing import Any

from .models import DramaProject, DramaValidationError
from .prompts import build_blueprint_prompt, build_shot_package_prompt


class DramaAdapterError(RuntimeError):
    """Raised when the adapter cannot produce a valid drama project."""

    def __init__(self, message: str, raw_output: str = "") -> None:
        super().__init__(message)
        self.raw_output = raw_output


def message_content(response: Any) -> str:
    content = response.content if hasattr(response, "content") else response
    if isinstance(content, list):
        return "".join(
            str(item.get("text", item)) if isinstance(item, dict) else str(item)
            for item in content
        )
    return str(content)


def extract_json_object(text: str) -> str:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        return fenced.group(1).strip()

    start = text.find("{")
    if start < 0:
        raise ValueError("no JSON object found")

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1].strip()

    raise ValueError("unterminated JSON object")


class DramaAdapter:
    """Convert a novel workflow result into a validated short-drama project."""

    def __init__(self, llm) -> None:
        self.llm = llm

    def adapt_result(self, result) -> DramaProject:
        return self.adapt(
            source_title=result.topic,
            genre=result.genre,
            story=result.final_story,
            synthesis=getattr(result, "synthesis", ""),
        )

    def adapt(
        self,
        source_title: str,
        genre: str,
        story: str,
        synthesis: str = "",
    ) -> DramaProject:
        if not story or not story.strip():
            raise DramaAdapterError("story is empty; run /create or /load before /drama")

        blueprint_prompt = build_blueprint_prompt(
            source_title=source_title,
            genre=genre,
            story=story,
            synthesis=synthesis,
        )
        blueprint_raw = message_content(self.llm.invoke(blueprint_prompt))
        try:
            blueprint_json = extract_json_object(blueprint_raw)
            json.loads(blueprint_json)
        except (ValueError, json.JSONDecodeError) as exc:
            raise DramaAdapterError(
                f"Could not parse adaptation blueprint JSON: {exc}",
                raw_output=blueprint_raw,
            ) from exc

        shot_prompt = build_shot_package_prompt(
            source_title=source_title,
            genre=genre,
            story=story,
            blueprint_json=blueprint_json,
        )
        project_raw = message_content(self.llm.invoke(shot_prompt))
        try:
            project_json = extract_json_object(project_raw)
            payload = json.loads(project_json)
        except (ValueError, json.JSONDecodeError) as exc:
            raise DramaAdapterError(
                f"Could not parse drama project JSON: {exc}",
                raw_output=project_raw,
            ) from exc

        try:
            return DramaProject.from_dict(payload)
        except (TypeError, ValueError, DramaValidationError) as exc:
            raise DramaAdapterError(str(exc), raw_output=project_raw) from exc
```

- [ ] **Step 5: Update package exports**

Modify `zhihu_fiction/drama/__init__.py` to include adapter exports:

```python
"""Short-drama prompt package generation."""
from __future__ import annotations

from .adapter import DramaAdapter, DramaAdapterError
from .models import (
    DramaCharacter,
    DramaEpisode,
    DramaLocation,
    DramaProject,
    DramaShot,
    DramaValidationError,
)

__all__ = [
    "DramaAdapter",
    "DramaAdapterError",
    "DramaCharacter",
    "DramaEpisode",
    "DramaLocation",
    "DramaProject",
    "DramaShot",
    "DramaValidationError",
]
```

- [ ] **Step 6: Run adapter and model tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_drama_models.py zhihu_fiction/tests/test_drama_adapter.py -v
```

Expected result:

```text
11 passed
```

- [ ] **Step 7: Commit adapter task**

Run:

```bash
git add zhihu_fiction/drama/__init__.py
git add zhihu_fiction/drama/adapter.py
git add zhihu_fiction/drama/prompts.py
git add zhihu_fiction/tests/test_drama_adapter.py
git diff --cached --name-status
git commit -m "feat: add novel to drama adapter"
```

Expected staged files:

```text
M	zhihu_fiction/drama/__init__.py
A	zhihu_fiction/drama/adapter.py
A	zhihu_fiction/drama/prompts.py
A	zhihu_fiction/tests/test_drama_adapter.py
```

`zhihu_fiction/drama/__init__.py` appears as modified because this task exports `DramaAdapter`.

---

## Task 3: Add Prompt Package Exporter

**Files:**
- Modify: `zhihu_fiction/drama/exporter.py`
- Create: `zhihu_fiction/tests/test_drama_exporter.py`

- [ ] **Step 1: Write failing exporter tests**

Create `zhihu_fiction/tests/test_drama_exporter.py` with this content:

```python
"""Tests for short-drama prompt package export."""
from __future__ import annotations

import json

from zhihu_fiction.drama.exporter import DramaExporter
from zhihu_fiction.drama.models import (
    DramaCharacter,
    DramaEpisode,
    DramaLocation,
    DramaProject,
    DramaShot,
)


def make_project() -> DramaProject:
    shots = [
        DramaShot(
            id=f"ep01_sc01_sh{i:02d}",
            episode_index=1,
            scene_index=1,
            shot_index=i,
            duration_seconds=6,
            location_id="living_room",
            character_ids=["heroine"],
            action=f"女主完成第 {i} 个关键动作。",
            dialogue="我不会再退让。",
            emotion="克制但坚定",
            camera="medium close-up, slow push in",
            visual_prompt="modern Chinese living room, cinematic lighting",
            negative_prompt="low quality, blurry, distorted face",
            consistency_refs=["character.heroine", "location.living_room"],
        )
        for i in range(1, 7)
    ]
    return DramaProject(
        title="重生后我不再忍让",
        source_title="测试主题",
        genre="复仇",
        logline="被背叛的女主重生后用真相反击。",
        audience="喜欢复仇爽感和家庭冲突的短剧观众",
        episode_count=1,
        characters=[
            DramaCharacter(
                id="heroine",
                name="林夏",
                role="女主",
                age_range="25-30",
                appearance="黑色长发，冷静克制，眼神坚定",
                costume="白色衬衫和深色长裤",
                personality="隐忍、聪明、行动果断",
                motivation="查清背叛真相并夺回人生",
                consistency_prompt="林夏，25岁左右，中国女性，黑色长发，白色衬衫，冷静坚定",
            )
        ],
        locations=[
            DramaLocation(
                id="living_room",
                name="林家客厅",
                visual_style="现代中式家庭客厅，压抑而整洁",
                time_period="现代",
                lighting="夜晚室内暖光，局部阴影",
                consistency_prompt="modern Chinese family living room, warm indoor light, tense mood",
            )
        ],
        episodes=[
            DramaEpisode(
                index=1,
                title="重生醒来",
                hook="女主在被害当天醒来，发现时间倒流。",
                synopsis="林夏重新回到被陷害的夜晚，第一次选择正面反击。",
                cliffhanger="她拿出录音笔，继母脸色骤变。",
                shots=shots,
            )
        ],
        adaptation_notes=["保留原小说的复仇主线，压缩支线。"],
        risk_notes=["避免过度暴力和违法细节。"],
    )


def test_exporter_writes_prompt_package_files(tmp_path):
    exporter = DramaExporter(output_root=tmp_path, now_fn=lambda: "20260609_120000")

    package_dir = exporter.export(make_project())

    assert package_dir.name == "短剧视频Prompt包_20260609_120000"
    assert (package_dir / "manifest.json").exists()
    assert (package_dir / "改编方案.md").exists()
    assert (package_dir / "角色一致性设定.md").exists()
    assert (package_dir / "分集剧本.md").exists()
    assert (package_dir / "镜头表.json").exists()
    assert (package_dir / "视频生成Prompts.md").exists()

    manifest = json.loads((package_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["title"] == "重生后我不再忍让"
    assert manifest["episode_count"] == 1
    assert manifest["shot_count"] == 6

    shot_table = json.loads((package_dir / "镜头表.json").read_text(encoding="utf-8"))
    assert shot_table[0]["id"] == "ep01_sc01_sh01"
    assert shot_table[0]["visual_prompt"]


def test_exporter_uses_unique_directory_when_target_exists(tmp_path):
    exporter = DramaExporter(output_root=tmp_path, now_fn=lambda: "20260609_120000")

    first = exporter.export(make_project())
    second = exporter.export(make_project())

    assert first != second
    assert second.name == "短剧视频Prompt包_20260609_120000_2"


def test_export_failure_writes_error_and_raw_output(tmp_path):
    exporter = DramaExporter(output_root=tmp_path, now_fn=lambda: "20260609_120000")

    package_dir = exporter.export_failure(
        source_title="测试主题",
        raw_output="模型原始输出",
        error="Could not parse drama project JSON",
    )

    assert (package_dir / "raw_output.txt").read_text(encoding="utf-8") == "模型原始输出"
    assert "Could not parse" in (package_dir / "error.txt").read_text(encoding="utf-8")
```

- [ ] **Step 2: Run exporter tests and confirm they fail**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_drama_exporter.py -v
```

Expected result:

```text
FAILED zhihu_fiction/tests/test_drama_exporter.py
AttributeError or TypeError for DramaExporter
```

- [ ] **Step 3: Add exporter implementation**

Replace `zhihu_fiction/drama/exporter.py` with this content:

```python
"""Export short-drama projects as prompt packages."""
from __future__ import annotations

import json
from datetime import datetime
from dataclasses import asdict
from pathlib import Path

from ..config import APP_ROOT
from .models import DramaProject


def safe_filename(value: str, default: str = "short_drama") -> str:
    cleaned = "".join(char for char in value if char.isalnum() or char in ("-", "_", " "))
    cleaned = cleaned.strip().replace(" ", "_")
    return cleaned[:60] or default


class DramaExporter:
    """Write human-readable and machine-readable short-drama prompt packages."""

    def __init__(self, output_root: Path | None = None, now_fn=None) -> None:
        self.output_root = output_root or APP_ROOT / "output"
        self.now_fn = now_fn or (lambda: datetime.now().strftime("%Y%m%d_%H%M%S"))

    def export(self, project: DramaProject) -> Path:
        project.validate()
        base_dir = self.output_root / safe_filename(project.source_title or project.title)
        package_dir = self._unique_package_dir(base_dir / f"短剧视频Prompt包_{self.now_fn()}")
        package_dir.mkdir(parents=True, exist_ok=False)

        (package_dir / "manifest.json").write_text(
            json.dumps(self._manifest(project), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (package_dir / "改编方案.md").write_text(self._render_plan(project), encoding="utf-8")
        (package_dir / "角色一致性设定.md").write_text(self._render_consistency(project), encoding="utf-8")
        (package_dir / "分集剧本.md").write_text(self._render_scripts(project), encoding="utf-8")
        (package_dir / "镜头表.json").write_text(
            json.dumps(self._shot_table(project), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (package_dir / "视频生成Prompts.md").write_text(self._render_video_prompts(project), encoding="utf-8")
        return package_dir

    def export_failure(self, source_title: str, raw_output: str, error: str) -> Path:
        base_dir = self.output_root / safe_filename(source_title)
        package_dir = self._unique_package_dir(base_dir / f"短剧视频Prompt包_{self.now_fn()}_失败")
        package_dir.mkdir(parents=True, exist_ok=False)
        (package_dir / "raw_output.txt").write_text(raw_output, encoding="utf-8")
        (package_dir / "error.txt").write_text(error, encoding="utf-8")
        return package_dir

    @staticmethod
    def _unique_package_dir(path: Path) -> Path:
        if not path.exists():
            return path
        counter = 2
        while True:
            candidate = path.with_name(f"{path.name}_{counter}")
            if not candidate.exists():
                return candidate
            counter += 1

    @staticmethod
    def _manifest(project: DramaProject) -> dict:
        return {
            "title": project.title,
            "source_title": project.source_title,
            "genre": project.genre,
            "logline": project.logline,
            "audience": project.audience,
            "episode_count": project.episode_count,
            "shot_count": project.total_shots,
            "files": {
                "adaptation_plan": "改编方案.md",
                "consistency": "角色一致性设定.md",
                "scripts": "分集剧本.md",
                "shot_table": "镜头表.json",
                "video_prompts": "视频生成Prompts.md",
            },
            "project": project.to_dict(),
        }

    @staticmethod
    def _shot_table(project: DramaProject) -> list[dict]:
        rows = []
        for episode in project.episodes:
            for shot in episode.shots:
                row = asdict(shot)
                row["episode_title"] = episode.title
                rows.append(row)
        return rows

    @staticmethod
    def _render_plan(project: DramaProject) -> str:
        lines = [
            f"# {project.title}",
            "",
            f"原小说：{project.source_title}",
            f"题材：{project.genre}",
            f"一句话卖点：{project.logline}",
            f"目标观众：{project.audience}",
            f"分集数量：{project.episode_count}",
            f"镜头数量：{project.total_shots}",
            "",
            "## 改编策略",
        ]
        lines.extend(f"- {note}" for note in project.adaptation_notes)
        lines.extend(["", "## 风险提示"])
        lines.extend(f"- {note}" for note in project.risk_notes)
        return "\n".join(lines).strip() + "\n"

    @staticmethod
    def _render_consistency(project: DramaProject) -> str:
        lines = [f"# {project.title} 角色一致性设定", "", "## 角色"]
        for character in project.characters:
            lines.extend([
                "",
                f"### {character.name} ({character.id})",
                f"- 功能：{character.role}",
                f"- 年龄：{character.age_range}",
                f"- 外貌：{character.appearance}",
                f"- 服装：{character.costume}",
                f"- 性格：{character.personality}",
                f"- 动机：{character.motivation}",
                f"- 一致性 Prompt：{character.consistency_prompt}",
            ])
        lines.extend(["", "## 场景"])
        for location in project.locations:
            lines.extend([
                "",
                f"### {location.name} ({location.id})",
                f"- 视觉风格：{location.visual_style}",
                f"- 时代背景：{location.time_period}",
                f"- 灯光：{location.lighting}",
                f"- 一致性 Prompt：{location.consistency_prompt}",
            ])
        return "\n".join(lines).strip() + "\n"

    @staticmethod
    def _render_scripts(project: DramaProject) -> str:
        lines = [f"# {project.title} 分集剧本"]
        for episode in project.episodes:
            lines.extend([
                "",
                f"## 第 {episode.index} 集：{episode.title}",
                "",
                f"开场钩子：{episode.hook}",
                f"剧情简介：{episode.synopsis}",
                f"结尾悬念：{episode.cliffhanger}",
                "",
                "### 镜头",
            ])
            for shot in episode.shots:
                lines.extend([
                    "",
                    f"#### {shot.id}",
                    f"- 时长：{shot.duration_seconds}s",
                    f"- 场景：{shot.location_id}",
                    f"- 角色：{', '.join(shot.character_ids)}",
                    f"- 动作：{shot.action}",
                    f"- 对白：{shot.dialogue}",
                    f"- 情绪：{shot.emotion}",
                    f"- 镜头：{shot.camera}",
                ])
        return "\n".join(lines).strip() + "\n"

    @staticmethod
    def _render_video_prompts(project: DramaProject) -> str:
        lines = [f"# {project.title} 视频生成 Prompts"]
        for episode in project.episodes:
            lines.extend(["", f"## 第 {episode.index} 集：{episode.title}"])
            for shot in episode.shots:
                lines.extend([
                    "",
                    f"### {shot.id}",
                    f"- Duration: {shot.duration_seconds}s",
                    f"- Camera: {shot.camera}",
                    f"- Visual Prompt: {shot.visual_prompt}",
                    f"- Negative Prompt: {shot.negative_prompt}",
                    f"- Consistency Refs: {', '.join(shot.consistency_refs)}",
                    f"- Dialogue: {shot.dialogue}",
                    f"- Action: {shot.action}",
                ])
        return "\n".join(lines).strip() + "\n"
```

- [ ] **Step 4: Update package exports**

Modify `zhihu_fiction/drama/__init__.py` to include the exporter:

```python
"""Short-drama prompt package generation."""
from __future__ import annotations

from .adapter import DramaAdapter, DramaAdapterError
from .exporter import DramaExporter
from .models import (
    DramaCharacter,
    DramaEpisode,
    DramaLocation,
    DramaProject,
    DramaShot,
    DramaValidationError,
)

__all__ = [
    "DramaAdapter",
    "DramaAdapterError",
    "DramaExporter",
    "DramaCharacter",
    "DramaEpisode",
    "DramaLocation",
    "DramaProject",
    "DramaShot",
    "DramaValidationError",
]
```

- [ ] **Step 5: Run exporter and drama tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_drama_models.py zhihu_fiction/tests/test_drama_adapter.py zhihu_fiction/tests/test_drama_exporter.py -v
```

Expected result:

```text
14 passed
```

- [ ] **Step 6: Commit exporter task**

Run:

```bash
git add zhihu_fiction/drama/exporter.py
git add zhihu_fiction/drama/__init__.py
git add zhihu_fiction/tests/test_drama_exporter.py
git diff --cached --name-status
git commit -m "feat: export short-drama prompt packages"
```

Expected staged files:

```text
M	zhihu_fiction/drama/__init__.py
A	zhihu_fiction/drama/exporter.py
A	zhihu_fiction/tests/test_drama_exporter.py
```

---

## Task 4: Add CLI `/drama`

**Files:**
- Modify: `zhihu_fiction/cli.py`
- Create: `zhihu_fiction/tests/test_cli_drama.py`

- [ ] **Step 1: Write failing CLI tests**

Create `zhihu_fiction/tests/test_cli_drama.py` with this content:

```python
"""Tests for the CLI /drama command."""
from __future__ import annotations

from pathlib import Path

import zhihu_fiction.cli as cli_mod
from zhihu_fiction.cli import CLI
from zhihu_fiction.drama.models import (
    DramaCharacter,
    DramaEpisode,
    DramaLocation,
    DramaProject,
    DramaShot,
)
from zhihu_fiction.orchestrator import WorkflowResult


def make_result() -> WorkflowResult:
    return WorkflowResult(
        topic="测试主题",
        genre="复仇",
        topic_analysis="",
        outline="",
        draft="",
        polished="女主被陷害后重生，决定反击。",
        review="",
        synthesis="发布方案",
    )


def make_project() -> DramaProject:
    shots = [
        DramaShot(
            id=f"ep01_sc01_sh{i:02d}",
            episode_index=1,
            scene_index=1,
            shot_index=i,
            duration_seconds=6,
            location_id="living_room",
            character_ids=["heroine"],
            action=f"女主完成第 {i} 个关键动作。",
            dialogue="我不会再退让。",
            emotion="克制但坚定",
            camera="medium close-up, slow push in",
            visual_prompt="modern Chinese living room, cinematic lighting",
            negative_prompt="low quality, blurry, distorted face",
            consistency_refs=["character.heroine", "location.living_room"],
        )
        for i in range(1, 7)
    ]
    return DramaProject(
        title="重生后我不再忍让",
        source_title="测试主题",
        genre="复仇",
        logline="被背叛的女主重生后用真相反击。",
        audience="喜欢复仇爽感和家庭冲突的短剧观众",
        episode_count=1,
        characters=[
            DramaCharacter(
                id="heroine",
                name="林夏",
                role="女主",
                age_range="25-30",
                appearance="黑色长发，冷静克制，眼神坚定",
                costume="白色衬衫和深色长裤",
                personality="隐忍、聪明、行动果断",
                motivation="查清背叛真相并夺回人生",
                consistency_prompt="林夏，25岁左右，中国女性，黑色长发，白色衬衫，冷静坚定",
            )
        ],
        locations=[
            DramaLocation(
                id="living_room",
                name="林家客厅",
                visual_style="现代中式家庭客厅，压抑而整洁",
                time_period="现代",
                lighting="夜晚室内暖光，局部阴影",
                consistency_prompt="modern Chinese family living room, warm indoor light, tense mood",
            )
        ],
        episodes=[
            DramaEpisode(
                index=1,
                title="重生醒来",
                hook="女主在被害当天醒来，发现时间倒流。",
                synopsis="林夏重新回到被陷害的夜晚，第一次选择正面反击。",
                cliffhanger="她拿出录音笔，继母脸色骤变。",
                shots=shots,
            )
        ],
        adaptation_notes=["保留原小说的复仇主线，压缩支线。"],
        risk_notes=["避免过度暴力和违法细节。"],
    )


def test_cmd_drama_requires_loaded_story(capsys):
    cli = CLI.__new__(CLI)
    cli.last_result = None

    cli.cmd_drama()

    captured = capsys.readouterr()
    assert "没有可转换的小说" in captured.out
    assert "/create" in captured.out
    assert "/load" in captured.out


def test_cmd_drama_generates_package(monkeypatch, tmp_path, capsys):
    project = make_project()

    class StubAdapter:
        def __init__(self, llm):
            self.llm = llm

        def adapt_result(self, result):
            assert result.topic == "测试主题"
            return project

    class StubExporter:
        def export(self, exported_project):
            assert exported_project is project
            return tmp_path / "短剧视频Prompt包_20260609_120000"

        def export_failure(self, source_title, raw_output, error):
            raise AssertionError("export_failure should not be called")

    monkeypatch.setattr(cli_mod, "create_llm", lambda settings, temperature=0.3: object())
    monkeypatch.setattr(cli_mod, "DramaAdapter", StubAdapter)
    monkeypatch.setattr(cli_mod, "DramaExporter", StubExporter)

    cli = CLI.__new__(CLI)
    cli.settings = object()
    cli.last_result = make_result()

    cli.cmd_drama()

    captured = capsys.readouterr()
    assert "短剧 Prompt 包已生成" in captured.out
    assert "共 1 集，6 个镜头" in captured.out
    assert str(tmp_path) in captured.out
```

- [ ] **Step 2: Run CLI drama tests and confirm they fail**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_cli_drama.py -v
```

Expected result:

```text
FAILED zhihu_fiction/tests/test_cli_drama.py
AttributeError: 'CLI' object has no attribute 'cmd_drama'
```

- [ ] **Step 3: Add CLI imports**

Modify `zhihu_fiction/cli.py` near the existing imports. Add:

```python
from .drama.adapter import DramaAdapter, DramaAdapterError
from .drama.exporter import DramaExporter
```

- [ ] **Step 4: Add help text command**

In `HELP_TEXT`, add this line after `/publish <主题>`:

```text
║  /drama         将最近/已加载小说转成短剧视频Prompt包    ║
```

- [ ] **Step 5: Add `cmd_drama` method**

Add this method immediately after `cmd_publish` in `zhihu_fiction/cli.py`:

```python
    def cmd_drama(self) -> None:
        """Convert the latest or loaded story into a short-drama prompt package."""
        if self.last_result is None:
            print("没有可转换的小说。请先运行 /create <主题> 或 /load <文件名>。")
            return

        print(f"\n[短剧] 正在将「{self.last_result.topic}」转换为短剧视频 Prompt 包...")

        exporter = DramaExporter()
        try:
            llm = create_llm(self.settings, temperature=0.3)
            project = DramaAdapter(llm).adapt_result(self.last_result)
            output_dir = exporter.export(project)
            print("\n短剧 Prompt 包已生成：")
            print(output_dir)
            print(f"共 {project.episode_count} 集，{project.total_shots} 个镜头")
        except DramaAdapterError as exc:
            failure_dir = exporter.export_failure(
                source_title=self.last_result.topic,
                raw_output=exc.raw_output,
                error=str(exc),
            )
            print(f"\n[错误] 短剧 Prompt 包生成失败: {exc}")
            if exc.raw_output:
                print(f"模型原始输出已保存: {failure_dir / 'raw_output.txt'}")
            else:
                print(f"错误信息已保存: {failure_dir / 'error.txt'}")
        except Exception as exc:
            print(f"\n[错误] 短剧 Prompt 包生成失败: {exc}")
```

- [ ] **Step 6: Add command dispatch**

In the main command loop, add this branch after `/publish`:

```python
            elif cmd == "/drama":
                self.cmd_drama()
```

- [ ] **Step 7: Run CLI and drama tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_drama_models.py zhihu_fiction/tests/test_drama_adapter.py zhihu_fiction/tests/test_drama_exporter.py zhihu_fiction/tests/test_cli_drama.py -v
```

Expected result:

```text
16 passed
```

- [ ] **Step 8: Commit CLI task**

Run:

```bash
git add zhihu_fiction/cli.py
git add zhihu_fiction/tests/test_cli_drama.py
git diff --cached --name-status
git commit -m "feat: add short-drama CLI export"
```

Expected staged files:

```text
M	zhihu_fiction/cli.py
A	zhihu_fiction/tests/test_cli_drama.py
```

---

## Task 5: Update README Workflow

**Files:**
- Modify: `zhihu_fiction/README.md`

- [ ] **Step 1: Add feature bullet**

In `zhihu_fiction/README.md`, under `## 功能概览`, add this bullet after the multi-platform publishing bullet:

```markdown
- **短剧 Prompt 包**：可将已生成小说转换为 10 集以内的短剧分集剧本、角色/场景一致性设定、镜头表和视频生成提示词，为后续接入视频生成模型做准备。
```

- [ ] **Step 2: Add CLI command documentation**

In the CLI command list, add:

```text
/drama                  将最近/已加载小说转成短剧视频 Prompt 包
```

- [ ] **Step 3: Add recommended drama workflow**

After the existing recommended workflow block, add:

````markdown
短剧 Prompt 包流程：

```text
/create 一个适合短剧改编的复仇爽文
/drama
```

输出目录示例：

```text
zhihu_fiction/output/<story>/短剧视频Prompt包_<timestamp>/
├── manifest.json
├── 改编方案.md
├── 角色一致性设定.md
├── 分集剧本.md
├── 镜头表.json
└── 视频生成Prompts.md
```

第一版只生成视频模型 Prompt 包，不直接调用视频生成 API。
````

- [ ] **Step 4: Add safety note**

In `## 发布与合规注意事项`, add:

```markdown
- 短剧 Prompt 包是视频生成前的策划和分镜资产，接入视频模型前仍需要人工检查角色一致性、内容安全、版权来源和平台规则。
```

- [ ] **Step 5: Verify README mentions drama command and package**

Run:

```bash
rg -n "/drama|短剧视频Prompt包|视频生成 API" zhihu_fiction/README.md
```

Expected output includes all three terms:

```text
/drama
短剧视频Prompt包
视频生成 API
```

- [ ] **Step 6: Commit README task**

Run:

```bash
git add zhihu_fiction/README.md
git diff --cached --name-status
git commit -m "docs: document short-drama prompt workflow"
```

Expected staged files:

```text
M	zhihu_fiction/README.md
```

---

## Task 6: Final Verification

**Files:**
- No new files.
- Verify all files changed by Tasks 1-5.

- [ ] **Step 1: Run drama-specific tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_drama_models.py zhihu_fiction/tests/test_drama_adapter.py zhihu_fiction/tests/test_drama_exporter.py zhihu_fiction/tests/test_cli_drama.py -v
```

Expected result:

```text
16 passed
```

- [ ] **Step 2: Run existing zhihu_fiction tests**

Run:

```bash
python -m pytest zhihu_fiction/tests -v
```

Expected result:

```text
all tests pass
```

If existing unrelated tests fail, record the exact failing test names and error messages before deciding whether they belong to this feature.

- [ ] **Step 3: Smoke-test imports**

Run:

```bash
python -c "from zhihu_fiction.drama import DramaAdapter, DramaExporter, DramaProject; print('drama imports OK')"
```

Expected output:

```text
drama imports OK
```

- [ ] **Step 4: Verify changed file list**

Run:

```bash
git diff --name-status HEAD~5..HEAD
```

Expected changed files include:

```text
zhihu_fiction/drama/__init__.py
zhihu_fiction/drama/models.py
zhihu_fiction/drama/prompts.py
zhihu_fiction/drama/adapter.py
zhihu_fiction/drama/exporter.py
zhihu_fiction/tests/test_drama_models.py
zhihu_fiction/tests/test_drama_adapter.py
zhihu_fiction/tests/test_drama_exporter.py
zhihu_fiction/tests/test_cli_drama.py
zhihu_fiction/cli.py
zhihu_fiction/README.md
```

- [ ] **Step 5: Final status check**

Run:

```bash
git status --short
```

Expected result:

```text
No files from the short-drama implementation are unstaged or untracked.
```

The repository may still show unrelated pre-existing dirty files. Do not revert them.

## Acceptance Checklist

- [ ] `/drama` is listed in CLI help.
- [ ] `/drama` with no loaded story prints a clear message.
- [ ] `/drama` uses `WorkflowResult.final_story`.
- [ ] `DramaProject` validates 1-10 episodes.
- [ ] Each episode validates 6-12 shots.
- [ ] Each shot validates 5-8 seconds.
- [ ] Each shot validates known character and location references.
- [ ] Invalid LLM JSON raises `DramaAdapterError` with `raw_output`.
- [ ] Export creates `manifest.json`.
- [ ] Export creates `改编方案.md`.
- [ ] Export creates `角色一致性设定.md`.
- [ ] Export creates `分集剧本.md`.
- [ ] Export creates `镜头表.json`.
- [ ] Export creates `视频生成Prompts.md`.
- [ ] Export never overwrites an existing package directory.
- [ ] README documents the workflow.
- [ ] Drama-specific tests pass.
- [ ] Existing `zhihu_fiction/tests` pass or unrelated failures are reported with evidence.
