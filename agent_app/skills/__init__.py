"""Progressive disclosure skill system — inspired by Claude Code's Skills.

Skills are modular prompt fragments that agents load on-demand based on task context.
This keeps base prompts lean while providing deep domain knowledge when needed.
"""

from .registry import Skill, SkillRegistry, SkillResolver, resolve_skills

__all__ = ["Skill", "SkillRegistry", "SkillResolver", "resolve_skills"]
