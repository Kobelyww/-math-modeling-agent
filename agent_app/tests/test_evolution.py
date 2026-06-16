"""Smoke tests for the evolution module (imports and basic instantiation)."""

import pytest

from agent_app.evolution import (
    ConstraintValidator,
    EvolutionCandidate,
    EvolutionResult,
    EvolutionTracker,
    FitnessDimension,
    FitnessScore,
    GenerationMetrics,
    PromptConstraintValidator,
)

LONG = (
    "A sufficiently long prompt text that exceeds the minimum character "
    "requirement for constraint validation checks. It discusses mathematical "
    "modeling approaches including linear programming and optimization, "
    "with enough detail to serve as a realistic agent system prompt."
)


class TestFitnessScore:
    def test_defaults(self):
        fs = FitnessScore()
        assert fs.overall == 0.0

    def test_to_dict(self):
        fs = FitnessScore(overall=0.8, dimensions={FitnessDimension.CLARITY: 4.0})
        assert fs.to_dict()["overall"] == 0.8


class TestConstraintValidator:
    def test_default_pass(self):
        assert ConstraintValidator().validate(LONG, LONG).passed

    def test_too_short(self):
        assert not ConstraintValidator(min_chars=100).validate("o", "s").passed

    def test_too_long(self):
        assert not ConstraintValidator(max_chars=10).validate("o", "a" * 20).passed

    def test_size_increase(self):
        assert not ConstraintValidator(max_size_increase=0.1).validate("abc", "a" * 100).passed


class TestPromptConstraintValidator:
    def test_missing_keywords(self):
        r = PromptConstraintValidator().validate(LONG, LONG, role="modeler")
        assert not r.passed
        assert any("Missing keywords" in i for i in r.issues)

    def test_keywords_present(self):
        pv = PromptConstraintValidator()
        base = LONG + " " + LONG
        prompt = base + (
            " 数学模型：使用线性规划方法对问题进行建模。"
            "假设：所有变量连续且非负目标函数和约束均为线性。"
            "优化目标：在满足资源约束的条件下最小化总成本。"
            "这是一个完整的数学建模方案描述包含模型假设和符号说明。"
        )
        result = pv.validate(base, prompt, role="modeler")
        assert result.passed


class TestEvolutionTracker:
    def test_summary(self, tmp_path):
        t = EvolutionTracker(data_dir=tmp_path)
        t.record_generation(GenerationMetrics(
            generation=1, tasks_completed=3, avg_fitness=0.5, best_fitness=0.7,
            agents_optimized=["m"], total_candidates=4, improvements_adopted=2,
        ))
        t.record_generation(GenerationMetrics(
            generation=2, tasks_completed=3, avg_fitness=0.7, best_fitness=0.85,
            agents_optimized=["m"], total_candidates=3, improvements_adopted=1,
        ))
        s = t.improvement_summary()
        assert "0.500" in s and "0.700" in s


class TestEvolutionDataclasses:
    def test_candidate_score(self):
        c = EvolutionCandidate(prompt="x")
        c.fitness = FitnessScore(overall=0.75)
        assert c.score == 0.75

    def test_result(self):
        r = EvolutionResult(
            role="m", original_prompt="o", best_prompt="b",
            original_score=0.5, best_score=0.8, improvement=0.3,
            generations=2, candidates_tested=5, passed_validation=True,
        )
        assert r.improvement == 0.3