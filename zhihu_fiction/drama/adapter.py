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
