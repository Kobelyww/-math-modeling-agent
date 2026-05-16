"""Prompt 约束验证器。

确保优化过程不破坏 Agent 的基本能力。
"""

from __future__ import annotations

from dataclasses import dataclass, field

REQUIRED_KEYWORDS_BY_ROLE = {
    "modeler": ["数学模型", "假设", "优化目标"],
    "programmer": ["代码", "算法", "python"],
    "writer": ["论文", "摘要", "结论"],
    "reviewer": ["评审", "改进", "建议"],
    "synthesizer": ["整合", "方案", "实施"],
    "data_engineer": ["数据", "预处理", "清洗"],
    "code_debugger": ["代码", "审查", "bug"],
}


@dataclass
class ConstraintCheck:
    passed: bool = True
    issues: list[str] = field(default_factory=list)


class PromptConstraintValidator:
    """验证优化后的 Prompt 不违反基本约束。"""

    def __init__(
        self,
        max_size_increase: float = 0.5,
        max_chars: int = 8000,
        min_chars: int = 300,
    ) -> None:
        self.max_size_increase = max_size_increase
        self.max_chars = max_chars
        self.min_chars = min_chars

    def validate(self, original: str, evolved: str, role: str | None = None) -> ConstraintCheck:
        issues = []

        if len(evolved) < self.min_chars:
            issues.append(f"Prompt too short ({len(evolved)} < {self.min_chars} chars)")
        if len(evolved) > self.max_chars:
            issues.append(f"Prompt too long ({len(evolved)} > {self.max_chars} chars)")
        if len(original) > 0 and len(evolved) > len(original) * (1 + self.max_size_increase):
            pct = int((len(evolved) / len(original) - 1) * 100)
            issues.append(f"Prompt grew {pct}% (limit {int(self.max_size_increase * 100)}%)")

        if role and role in REQUIRED_KEYWORDS_BY_ROLE:
            missing = [kw for kw in REQUIRED_KEYWORDS_BY_ROLE[role] if kw not in evolved]
            if missing:
                issues.append(f"Missing keywords: {', '.join(missing)}")

        return ConstraintCheck(passed=len(issues) == 0, issues=issues)