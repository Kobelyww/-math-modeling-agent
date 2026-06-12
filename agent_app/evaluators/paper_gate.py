from __future__ import annotations

import re

from agent_app.domain.models import PaperDraft, QualityReport

REQUIRED_SECTIONS = [
    "摘要",
    "关键词",
    "问题重述",
    "模型假设",
    "符号说明",
    "问题分析",
    "模型建立与求解",
    "结果分析",
    "灵敏度",
    "模型评价",
    "参考文献",
    "附录",
]
PLACEHOLDER_MARKERS = ["TO" + "DO", "待" + "补充", "占" + "位"]
STANDALONE_LUE_PATTERN = re.compile(
    r"(^|[\s，。；;：:、（）()【】\[\]《》<>])略([\s，。；;：:、（）()【】\[\]《》<>]|$)"
)


def evaluate_paper(paper: PaperDraft) -> QualityReport:
    section_text = "\n".join(f"{key}\n{value}" for key, value in paper.sections.items())
    section_keys = {key.strip() for key in paper.sections}
    fixes: list[str] = []

    for section in REQUIRED_SECTIONS:
        if section not in section_keys:
            fixes.append(f"缺少论文章节: {section}")

    if any(marker in section_text for marker in PLACEHOLDER_MARKERS) or STANDALONE_LUE_PATTERN.search(
        section_text
    ):
        fixes.append("论文存在占" + "位文本")
    if paper.latex_path is None:
        fixes.append("缺少 paper.tex")

    passed = not fixes
    return QualityReport(
        gate_name="paper",
        passed=passed,
        score=1.0
        if passed
        else max(0.0, 1.0 - len(fixes) / (len(REQUIRED_SECTIONS) + 2)),
        required_fixes=fixes,
    )
