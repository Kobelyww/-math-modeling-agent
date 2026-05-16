"""Smoke tests for the evolution module (imports and basic instantiation)."""

import pytest

from agent_app.evolution import (
    ConstraintCheck,
    ConstraintValidator,
    EvolutionCandidate,
    EvolutionResult,
    EvolutionTracker,
    FitnessDimension,
    FitnessScore,
    GEPAOptimizer,
    GenerationMetrics,
    PromptConstraintValidator,
)


class TestFitnessScore:
    def test_defaults(self):
        fs = FitnessScore()
        assert fs.overall == 0.0
        assert len(fs.dimensions) == 0

    def test_to_dict(self):
        fs = FitnessScore(
            overall=0.8,
            dimensions={FitnessDimension.CLARITY: 4.0},
        )
        d = fs.to_dict()
        assert d["overall"] == 0.8
        assert "清晰度" in d["dimensions"]


class TestConstraintValidator:
    def test_default_pass(self):
        cv = ConstraintValidator()
        result = cv.validate("original prompt text", "evolved prompt text")
        assert result.passed is True

    def test_too_short(self):
        cv = ConstraintValidator(min_chars=100)
        result = cv.validate("original", "short")
        assert not result.passed

    def test_too_long(self):
        cv = ConstraintValidator(max_chars=10)
        result = cv.validate("original", "a" * 20)
        assert not result.passed

    def test_size_increase(self):
        cv = ConstraintValidator(max_size_increase=0.1)
        result = cv.validate("abc", "a" * 100)
        assert not result.passed


class TestPromptConstraintValidator:
    def test_missing_keywords(self):
        pv = PromptConstraintValidator()
        result = pv.validate("original prompt", "some text without required keywords", role="modeler")
        assert not result.passed
        assert any("Missing keywords" in i for i in result.issues)

    def test_keywords_present(self):
        pv = PromptConstraintValidator()
        result = pv.validate(
            "original",
            "数学模型：使用线性规划。假设：变量连续。优化目标：最小化成本。",
            role="modeler",
        )
        assert result.passed


class TestEvolutionTracker:
    def test_record_and_summary(self, tmp_path):
        tracker = EvolutionTracker(data_dir=tmp_path)
        tracker.record_generation(GenerationMetrics(
            generation=1, tasks_completed=3, avg_fitness=0.5, best_fitness=0.7,
            agents_optimized=["modeler"], total_candidates=4, improvements_adopted=2,
        ))
        tracker.record_generation(GenerationMetrics(
            generation=2, tasks_completed=3, avg_fitness=0.7, best_fitness=0.85,
            agents_optimized=["modeler"], total_candidates=3, improvements_adopted=1,
        ))
        assert len(tracker.history) == 2
        summary = tracker.improvement_summary()
        assert "0.500" in summary
        assert "0.700" in summary
        assert "3/7" in summary


class TestEvolutionDataclasses:
    def test_candidate_score(self):
        c = EvolutionCandidate(prompt="test")
        assert c.score == 0.0
        c.fitness = FitnessScore(overall=0.75)
        assert c.score == 0.75

    def test_result_improvement(self):
        r = EvolutionResult(
            role="modeler", original_prompt="orig", best_prompt="best",
            original_score=0.5, best_score=0.8, improvement=0.3,
            generations=2, candidates_tested=5, passed_validation=True,
        )
        assert r.improvement == 0.3
        assert r.passed_validation