"""Nature Skills — MCM/ICM 竞赛辅助技能包。

来源: https://github.com/Gunp-666/MCM-AI-Starter-Kit
"""

from .loader import (
    SkillLoader,
    get_writing_rules,
    get_model_reference,
    get_viz_template,
    list_available_skills,
)

__all__ = [
    "SkillLoader",
    "get_writing_rules",
    "get_model_reference",
    "get_viz_template",
    "list_available_skills",
]
