"""GEPA 风格优化器（对标 Hermes s25-s27）。

GEPA = Generate → Evaluate → Prioritize → Apply
读取执行 trace → 理解为什么失败 → 针对性文本变异 → 评估 → 择优
"""

from __future__ import annotations

from dataclasses import dataclass, field

from langchain_core.language_models import BaseChatModel

from .evaluator import ConstraintValidator, FitnessEvaluator, FitnessScore

FEEDBACK_PROMPT = """你是数学建模 Agent Prompt 调试专家。分析以下 Agent Prompt 在哪出了问题。

## 当前 Prompt
{current_prompt}

## 表现数据
- 适应度总分：{fitness:.2f}/1.0
- 各维度得分：
{dimensions}

## 任务 Trace（Agent 的实际输出）
{traces}

## 任务
找出 3 个最关键的 Prompt 缺陷：
1. 哪条策略指令没被模型遵循？
2. 哪条指令导致了糟糕的输出？
3. 缺少什么指令可以防止这些问题？

对每个缺陷，给出具体的 Prompt 修改方案（改哪一部分、改成什么）。"""

MUTATE_PROMPT = """你是数学建模 Agent Prompt 优化师。根据以下缺陷分析，对 Prompt 做外科手术式修改。

## 原始 Prompt
{original_prompt}

## 缺陷分析
{feedback}

## 修改规则
1. 只改与缺陷直接相关的部分
2. 不改整体结构和编号体系
3. 每条修改都要有明确的理由
4. 保持原文总长度变化在 30% 以内

请输出修改后的**完整** Prompt。不要解释，直接输出 Prompt 正文。"""


@dataclass
class EvolutionCandidate:
    prompt: str
    fitness: FitnessScore | None = None
    passed_constraints: bool = False
    generation: int = 0

    @property
    def score(self) -> float:
        return self.fitness.overall if self.fitness else 0.0


@dataclass
class EvolutionResult:
    role: str
    original_prompt: str
    best_prompt: str
    original_score: float
    best_score: float
    improvement: float
    generations: int
    candidates_tested: int
    passed_validation: bool


class GEPAOptimizer:
    """GEPA 风格的反馈→变异→评估→择优优化器。"""

    def __init__(
        self,
        llm: BaseChatModel,
        evaluator: FitnessEvaluator,
        validator: ConstraintValidator | None = None,
        max_generations: int = 3,
        candidates_per_gen: int = 2,
        improvement_threshold: float = 0.03,
    ) -> None:
        self.llm = llm
        self.evaluator = evaluator
        self.validator = validator or ConstraintValidator()
        self.max_generations = max_generations
        self.candidates_per_gen = candidates_per_gen
        self.improvement_threshold = improvement_threshold

    def optimize(
        self,
        role: str,
        current_prompt: str,
        question: str,
        agent_output: str,
    ) -> EvolutionResult:
        best = EvolutionCandidate(prompt=current_prompt, generation=0)
        best.fitness = self.evaluator.evaluate(role, question, agent_output)
        total_candidates = 1

        for gen in range(self.max_generations):
            dims = []
            if best.fitness:
                for d, s in best.fitness.dimensions.items():
                    dims.append(f"  - {d.value}: {s:.1f}/5")
            dim_str = "\n".join(dims)

            feedback = self._generate_feedback(best.prompt, best.fitness, agent_output[:3000], dim_str)
            for _ in range(self.candidates_per_gen):
                mutated = self._mutate(best.prompt, feedback)
                if not self.validator.validate(current_prompt, mutated).passed:
                    continue
                total_candidates += 1
                candidate = EvolutionCandidate(prompt=mutated, generation=gen + 1)
                candidate.fitness = self.evaluator.evaluate(role, question, agent_output)
                candidate.passed_constraints = True
                if candidate.score > best.score + self.improvement_threshold:
                    best = candidate
            if best.generation < gen + 1:
                break

        orig_fitness = self.evaluator.evaluate(role, question, agent_output)
        return EvolutionResult(
            role=role,
            original_prompt=current_prompt,
            best_prompt=best.prompt,
            original_score=orig_fitness.overall,
            best_score=best.score,
            improvement=best.score - orig_fitness.overall,
            generations=best.generation,
            candidates_tested=total_candidates,
            passed_validation=self.validator.validate(current_prompt, best.prompt).passed,
        )

    def _generate_feedback(self, prompt: str, fitness: FitnessScore, traces: str, dim_str: str) -> str:
        fb_prompt = FEEDBACK_PROMPT.format(
            current_prompt=prompt,
            fitness=fitness.overall if fitness else 0.0,
            dimensions=dim_str,
            traces=traces,
        )
        result = self.llm.invoke(fb_prompt)
        return result.content if hasattr(result, "content") else str(result)

    def _mutate(self, prompt: str, feedback: str) -> str:
        mut_prompt = MUTATE_PROMPT.format(original_prompt=prompt, feedback=feedback)
        result = self.llm.invoke(mut_prompt)
        content = result.content if hasattr(result, "content") else str(result)
        if isinstance(content, list):
            content = "".join(
                str(item.get("text", item)) if isinstance(item, dict) else str(item)
                for item in content
            )
        return content.strip()