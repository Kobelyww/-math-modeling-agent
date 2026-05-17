"""Hermes 风格自进化管线（对标 NousResearch/hermes-agent）。

7 步文本优化管线：
  1. SELECT   — 选择优化目标（表现最弱的 Agent 优先）
  2. BUILD    — 生成评估数据集（历史 solve trace 提取）
  3. BASELINE — 多维适应度评估（数学严谨性/代码质量/完整性/清晰度）
  4. CONSTRAIN— 约束门控检查（长度/结构/关键字保留）
  5. OPTIMIZE — GEPA 反馈→变异→评估→择优循环
  6. VALIDATE — 约束 + holdout 验证
  7. DEPLOY   — 备份 → 写入 → 生效

用法：
    python -m agent_app.evolution.evolve --generations 3 --tasks 5
    python -m agent_app.evolution.evolve --agent modeler
    python -m agent_app.evolution.evolve --eval-only
"""

from .constraints import ConstraintCheck, PromptConstraintValidator
from .evaluator import (
    ConstraintValidator,
    FitnessDimension,
    FitnessEvaluator,
    FitnessScore,
)
from .gepa_optimizer import EvolutionCandidate, EvolutionResult, GEPAOptimizer
from .tracker import EvolutionTracker, GenerationMetrics

__all__ = [
    "ConstraintCheck",
    "ConstraintValidator",
    "EvolutionCandidate",
    "EvolutionResult",
    "EvolutionTracker",
    "FitnessDimension",
    "FitnessEvaluator",
    "FitnessScore",
    "GEPAOptimizer",
    "GenerationMetrics",
    "PromptConstraintValidator",
]
