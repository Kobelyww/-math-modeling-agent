"""自进化系统：分析弱点 → 优化策略 → 跨代锦标赛。"""

from .optimizer import StrategyOptimizer
from .tournament import EvolutionTournament
from .tracker import EvolutionTracker

__all__ = ["StrategyOptimizer", "EvolutionTournament", "EvolutionTracker"]
