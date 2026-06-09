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
        try:
            episode_count = int(data.get("episode_count", 0))
        except (TypeError, ValueError) as exc:
            raise DramaValidationError("episode_count must be an integer") from exc

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
            episode_count=episode_count,
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
        cleaned = []
        for value in values:
            if not value or not value.strip():
                raise DramaValidationError(f"{kind} id is required")
            cleaned.append(value.strip())
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
        try:
            duration_seconds = int(shot.duration_seconds)
        except (TypeError, ValueError) as exc:
            raise DramaValidationError(
                f"shot {shot.id} duration_seconds must be an integer"
            ) from exc
        if not 5 <= duration_seconds <= 8:
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
