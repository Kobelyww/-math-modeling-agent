"""Hermes 风格适应度评估器。

定义多维适应度维度和评分逻辑，用于评估 Agent 输出质量。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum

from langchain_core.language_models import BaseChatModel


class FitnessDimension(Enum):
    MATHEMATICAL_RIGOR = "数学严谨性"
    CODE_QUALITY = "代码质量"
    SOLUTION_COMPLETENESS = "完整性"
    CLARITY = "清晰度"


@dataclass
class FitnessScore:
    overall: float = 0.0
    dimensions: dict[FitnessDimension, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "overall": self.overall,
            "dimensions": {d.value: s for d, s in self.dimensions.items()},
        }


@dataclass
class ConstraintCheck:
    passed: bool = True
    issues: list[str] = field(default_factory=list)

    def summary(self) -> str:
        if self.passed:
            return "所有约束检查通过"
        return "问题:\n" + "\n".join(f"  - {i}" for i in self.issues)


EVAL_PROMPT = """你是一个数学建模评审专家。请评估以下 Agent 在完成建模任务时的输出质量。

## 任务
{question}

## Agent 输出
{agent_output}

## 评估维度
1. 数学严谨性 (1-5)：模型选择是否恰当？假设是否合理？推导是否严格？
2. 代码质量 (1-5)：代码是否可执行？算法设计是否高效？有无明显 bug？
3. 完整性 (1-5)：是否覆盖了任务的所有子问题？
4. 清晰度 (1-5)：结构是否清晰？表达是否准确？学术规范是否到位？

请严格按以下 JSON 格式输出（不要包含其他文字）：
{{"数学严谨性": <1-5>, "代码质量": <1-5>, "完整性": <1-5>, "清晰度": <1-5>}}
"""


class FitnessEvaluator:
    """使用 LLM 评估 Agent 输出质量的多维适应度评价器。"""

    def __init__(self, llm: BaseChatModel) -> None:
        self.llm = llm

    def evaluate(self, agent_role: str, question: str, agent_output: str) -> FitnessScore:
        prompt = EVAL_PROMPT.format(question=question[:2000], agent_output=agent_output[:3000])
        result = self.llm.invoke(prompt)
        text = result.content if hasattr(result, "content") else str(result)
        scores = self._parse_scores(text)

        dims = {
            FitnessDimension.MATHEMATICAL_RIGOR: scores.get("数学严谨性", 3.0),
            FitnessDimension.CODE_QUALITY: scores.get("代码质量", 3.0),
            FitnessDimension.SOLUTION_COMPLETENESS: scores.get("完整性", 3.0),
            FitnessDimension.CLARITY: scores.get("清晰度", 3.0),
        }
        overall = sum(dims.values()) / len(dims) / 5.0

        return FitnessScore(overall=min(overall, 1.0), dimensions=dims)

    @staticmethod
    def _parse_scores(text: str) -> dict[str, float]:
        try:
            json_match = re.search(r'\{[^}]+\}', text)
            if json_match:
                data = json.loads(json_match.group())
                return {k: float(v) for k, v in data.items()}
        except (json.JSONDecodeError, ValueError):
            pass

        scores = {}
        for dim in ["数学严谨性", "代码质量", "完整性", "清晰度"]:
            m = re.search(rf"{dim}.*?([1-5])", text)
            if m:
                scores[dim] = float(m.group(1))
        return scores


class ConstraintValidator:
    """验证优化后的 Prompt 是否满足基本约束。"""

    def __init__(
        self,
        max_size_increase: float = 0.5,
        max_chars: int = 8000,
        min_chars: int = 200,
        require_keywords: list[str] | None = None,
    ) -> None:
        self.max_size_increase = max_size_increase
        self.max_chars = max_chars
        self.min_chars = min_chars
        self.require_keywords = require_keywords or []

    def validate(self, original: str, evolved: str) -> ConstraintCheck:
        issues = []

        if len(evolved) < self.min_chars:
            issues.append(f"Prompt 过短（{len(evolved)} < {self.min_chars} 字符）")
        if len(evolved) > self.max_chars:
            issues.append(f"Prompt 过长（{len(evolved)} > {self.max_chars} 字符）")
        if len(evolved) > len(original) * (1 + self.max_size_increase):
            issues.append(
                f"Prompt 增幅过大（{len(evolved)} vs 原始 {len(original)}，"
                f"增幅 {len(evolved) / max(len(original), 1) - 1:.0%}）"
            )

        for kw in self.require_keywords:
            if kw not in evolved:
                issues.append(f"缺少必要关键字: {kw}")

        return ConstraintCheck(passed=len(issues) == 0, issues=issues)
