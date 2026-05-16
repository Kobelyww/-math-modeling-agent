"""进化追踪器，记录每代优化指标和历史。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class GenerationMetrics:
    generation: int
    tasks_completed: int = 0
    avg_fitness: float = 0.0
    best_fitness: float = 0.0
    agents_optimized: list[str] = field(default_factory=list)
    total_candidates: int = 0
    improvements_adopted: int = 0

    def to_dict(self) -> dict:
        return {
            "generation": self.generation,
            "tasks_completed": self.tasks_completed,
            "avg_fitness": self.avg_fitness,
            "best_fitness": self.best_fitness,
            "agents_optimized": self.agents_optimized,
            "total_candidates": self.total_candidates,
            "improvements_adopted": self.improvements_adopted,
        }


class EvolutionTracker:
    """进化历史追踪，支持持久化和进度报告。"""

    def __init__(self, data_dir: str | Path | None = None) -> None:
        if data_dir is None:
            from ..config import APP_ROOT
            data_dir = APP_ROOT / "data"
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._history: list[GenerationMetrics] = []

    def record_generation(self, metrics: GenerationMetrics) -> None:
        self._history.append(metrics)
        self._save()

    def _save(self) -> None:
        path = self._data_dir / "evolution_history.json"
        path.write_text(
            json.dumps([m.to_dict() for m in self._history], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def improvement_summary(self) -> str:
        if not self._history:
            return "No evolution records yet."

        lines = ["Evolution summary:"]
        first = self._history[0]
        last = self._history[-1]

        lines.append(f"  Generations: {len(self._history)}")
        lines.append(f"  Initial avg fitness: {first.avg_fitness:.3f}")
        lines.append(f"  Final avg fitness:   {last.avg_fitness:.3f}")
        if first.avg_fitness > 0:
            improvement = (last.avg_fitness - first.avg_fitness) / first.avg_fitness * 100
            lines.append(f"  Total improvement:   {improvement:+.1f}%")

        total_improvements = sum(g.improvements_adopted for g in self._history)
        total_candidates = sum(g.total_candidates for g in self._history)
        if total_candidates > 0:
            rate = total_improvements / total_candidates
            lines.append(f"  Adoption rate:       {total_improvements}/{total_candidates} ({rate:.0%})")

        return "\n".join(lines)

    @property
    def history(self) -> list[GenerationMetrics]:
        return list(self._history)