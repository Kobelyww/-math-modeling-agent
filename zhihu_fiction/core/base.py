"""Shared content normalization and markdown parsing helpers."""

from __future__ import annotations


def normalize_content(content) -> str:
    """Normalize LangChain message content to a plain string."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text", "")))
            else:
                parts.append(str(item))
        return "".join(parts)
    return str(content)


def extract_story_body(markdown_text: str) -> tuple[str, str]:
    """Extract story body and synthesis from a saved markdown file.

    File structure::

        # Title
        > genre

        ---

        # Chapter 1
        ...story with scene-break --- lines...

        # 发布方案
        ...synthesis...

    Returns (story_body, synthesis) where story_body is the text between
    the metadata ``---`` and ``# 发布方案`` (exclusive).  Scene-break
    ``---`` lines inside the story are preserved.
    """
    lines = markdown_text.split("\n")
    story_lines: list[str] = []
    synth_lines: list[str] = []
    in_story = False
    in_synth = False

    for line in lines:
        stripped = line.strip()
        if stripped == "# 发布方案":
            in_synth = True
            in_story = False
            continue
        if in_synth:
            synth_lines.append(line)
            continue
        if in_story:
            story_lines.append(line)
            continue
        if stripped == "---" and not in_story:
            in_story = True
            continue

    body = "\n".join(story_lines).strip()
    synthesis = "\n".join(synth_lines).strip()
    return body, synthesis

__all__ = ["extract_story_body", "normalize_content"]
