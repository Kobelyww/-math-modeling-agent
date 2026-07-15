from __future__ import annotations

from pathlib import Path

from agent_app.domain.contracts import Claim


CUMCM_SECTION_ORDER = [
    ("00_title", "title"),
    ("01_abstract", "abstract"),
    ("02_keywords", "keywords"),
    ("03_problem_restatement", "problem_restatement"),
    ("04_problem_analysis", "problem_analysis"),
    ("05_assumptions", "assumptions"),
    ("06_symbols", "symbols"),
    ("07_model_solution", "model_solution"),
    ("08_result_analysis", "result_analysis"),
    ("09_robustness_analysis", "robustness_analysis"),
    ("10_model_evaluation", "model_evaluation"),
    ("11_references", "references"),
    ("12_appendix", "appendix"),
]


def build_section_context(section: str, claims: list[Claim]) -> dict:
    matching = [claim for claim in claims if claim.section == section]
    return {
        "section": section,
        "claim_ids": [claim.claim_id for claim in matching],
        "claims": [
            {
                "claim_id": claim.claim_id,
                "text": claim.text,
                "evidence": [_format_evidence(evidence.path, evidence.locator) for evidence in claim.evidence],
                "status": claim.status.value,
                "is_supported": claim.is_supported(),
            }
            for claim in matching
        ],
    }


def write_section_files(run_dir: Path | str, claims: list[Claim]) -> list[Path]:
    root = Path(run_dir)
    section_dir = root / "sections"
    section_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for filename, section in CUMCM_SECTION_ORDER:
        context = build_section_context(section, claims)
        path = section_dir / f"{filename}.md"
        path.write_text(_render_claim_section(section, context), encoding="utf-8")
        paths.append(path)
    return paths


def _render_claim_section(section: str, context: dict) -> str:
    title = {
        "title": "题目",
        "abstract": "摘要",
        "keywords": "关键词",
        "problem_restatement": "问题重述",
        "problem_analysis": "问题分析",
        "assumptions": "模型假设",
        "symbols": "符号说明",
        "model_solution": "模型建立与求解",
        "result_analysis": "结果分析",
        "robustness_analysis": "灵敏度与稳健性分析",
        "model_evaluation": "模型评价",
        "references": "参考文献",
        "appendix": "附录",
    }.get(section, section)
    lines = [f"## {title}", ""]
    supported_claims = [claim for claim in context["claims"] if claim.get("is_supported")]
    if supported_claims:
        for claim in supported_claims:
            evidence = "；".join(claim["evidence"]) or "证据位置待补充"
            lines.append(f"{claim['text']} 该结论对应 `{claim['claim_id']}`，证据位置为 {evidence}。")
        return "\n".join(lines) + "\n"

    default_text = {
        "abstract": "本文围绕题面要求建立可复现的数学建模流程，并将模型、实验与论文结论逐项绑定。",
        "keywords": "数学建模；合同驱动；可复现实验；证据追踪",
        "problem_restatement": "本节概括赛题目标、输入数据、约束条件与需要提交的结果。",
        "problem_analysis": "本节根据子问题类型分析变量、参数、目标函数和求解依赖。",
        "assumptions": "模型假设仅服务于已识别的子问题，并在结果解释中保留适用边界。",
        "symbols": "主要符号随模型合同和结果文件一起定义，避免引入未使用变量。",
        "model_solution": "各子问题按合同选择求解策略，生成代码、结果文件和验证记录。",
        "result_analysis": "本节只写入已有结果文件能够支撑的结论。",
        "robustness_analysis": "稳健性分析围绕参数扰动、数据缺失和模型假设变化展开。",
        "model_evaluation": "模型评价从可解释性、可复现性、局限性和竞赛提交完整性展开。",
        "references": "参考文献由证据检索阶段与本地参考文件共同维护。",
        "appendix": "附录包含代码入口、合同文件、结果文件和审查报告路径。",
    }.get(section, "本节保留为用户可审阅正文，不包含内部调试上下文。")
    lines.append(default_text)
    return "\n".join(lines) + "\n"


def _format_evidence(path: Path, locator: str) -> str:
    if locator:
        return f"{path}#{locator}"
    return str(path)
