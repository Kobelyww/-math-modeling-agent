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
DEMO_PLACEHOLDER_MARKERS = [
    "DeepAgent generated model",
    "DeepAgent competition experiment placeholder",
    "Competition Paper Draft",
    "This draft summarizes the local modeling workflow",
]
BANNED_INTERNAL_MARKERS = [
    "Claim-Aware Section Context",
    "generic_cumcm_contract_workflow",
    "cumcm_b_problem_contract_workflow",
    "cumcm_b_problem_benchmark_workflow",
    "暂无已支持结论",
    "this is a scaffold",
]
BASELINE_ONLY_MARKERS = [
    "solver strategy 选择求解方式",
    "claim map 追踪到具体文件",
    "baseline 求解流程",
    "workflow summary",
]
MIN_SECTION_CHARS = 18
MIN_TOTAL_CHARS = 2200
MIN_SECTION_CHARS_BY_NAME = {
    "关键词": 2,
}
STANDALONE_LUE_PATTERN = re.compile(
    r"(^|[\s，。；;：:、（）()【】\[\]《》<>])略([\s，。；;：:、（）()【】\[\]《》<>]|$)"
)


def evaluate_paper(paper: PaperDraft) -> QualityReport:
    section_text = "\n".join(f"{key}\n{value}" for key, value in paper.sections.items())
    checked_texts = [section_text]
    latex_missing = paper.latex_path is None or not paper.latex_path.exists()
    if not latex_missing:
        try:
            checked_texts.append(paper.latex_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            latex_missing = True
    checked_text = "\n".join(checked_texts)
    section_keys = {key.strip() for key in paper.sections}
    fixes: list[str] = []

    for section in REQUIRED_SECTIONS:
        if section not in section_keys:
            fixes.append(f"缺少论文章节: {section}")
            continue
        body = str(paper.sections.get(section, "")).strip()
        min_chars = MIN_SECTION_CHARS_BY_NAME.get(section, MIN_SECTION_CHARS)
        if len(body) < min_chars:
            fixes.append(f"章节内容过短: {section}")

    if (
        any(marker in checked_text for marker in [*PLACEHOLDER_MARKERS, *DEMO_PLACEHOLDER_MARKERS])
        or STANDALONE_LUE_PATTERN.search(checked_text)
    ):
        fixes.append("论文存在占" + "位文本")
    normalized_text = checked_text.lower()
    leaked_markers = [
        marker
        for marker in BANNED_INTERNAL_MARKERS
        if marker.lower() in normalized_text
    ]
    if leaked_markers:
        fixes.append(f"论文泄露内部上下文: {', '.join(leaked_markers)}")
    baseline_markers = [
        marker
        for marker in BASELINE_ONLY_MARKERS
        if marker.lower() in normalized_text
    ]
    if baseline_markers:
        fixes.append(
            "论文包含 baseline/workflow 摘要痕迹，缺少真实推导、算法细节和结果解释"
        )
    total_body_chars = sum(len(str(value).strip()) for value in paper.sections.values())
    if total_body_chars < MIN_TOTAL_CHARS:
        fixes.append(
            f"论文正文过短，需要扩展真实推导、算法说明、结果解释和讨论"
            f"（当前 {total_body_chars} 字，至少 {MIN_TOTAL_CHARS} 字）"
        )
    if latex_missing:
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
