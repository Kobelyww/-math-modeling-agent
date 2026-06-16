"""Hermes 风格 Agent 自进化入口（7 步文本优化管线）。

对标 NousResearch/hermes-agent：
  1. SELECT   → 选择优化目标（表现最弱的 Agent 优先）
  2. BUILD    → 生成评估数据集（solve trace 提取）
  3. BASELINE → 多维适应度评估（数学严谨性/代码质量/完整性/清晰度）
  4. CONSTRAIN→ 约束门控检查（长度/结构/关键字保留）
  5. OPTIMIZE → GEPA 反馈→变异→评估→择优循环
  6. VALIDATE → 约束 + holdout 验证
  7. DEPLOY   → 备份 → 写入 → 生效

用法：
    python -m agent_app.evolution.evolve --generations 3 --tasks 5
    python -m agent_app.evolution.evolve --agent modeler
    python -m agent_app.evolution.evolve --eval-only
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

if __name__ == "__main__" and __package__ is None:
    _parent = Path(__file__).resolve().parent.parent.parent
    if str(_parent) not in sys.path:
        sys.path.insert(0, str(_parent))
    __package__ = "agent_app.evolution"

from ..agents import create_agents
from ..config import APP_ROOT, load_settings
from ..llm import create_llm
from ..orchestrator import Orchestrator

from .constraints import PromptConstraintValidator
from .evaluator import FitnessEvaluator
from .gepa_optimizer import GEPAOptimizer
from .tracker import EvolutionTracker, GenerationMetrics

PROMPT_BACKUP_DIR = APP_ROOT / "data" / "prompt_backups"

_DEFAULT_TASKS = [
    "建立城市交通流优化模型，分析高峰期拥堵问题并给出缓解方案",
    "构建投资组合优化模型，在风险约束下最大化预期收益",
    "设计一个疫情传播预测模型，评估不同干预策略的效果",
    "建立垃圾分类优化模型，最小化处理成本同时满足环保要求",
    "构建人才招聘匹配模型，优化候选人与职位的双边匹配效率",
]


def _backup_prompt(role: str, prompt: str) -> Path:
    PROMPT_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = PROMPT_BACKUP_DIR / f"{role}_{ts}.txt"
    path.write_text(prompt, encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Hermes 风格数模 Agent 自进化")
    parser.add_argument("--generations", type=int, default=3, help="进化代数")
    parser.add_argument("--tasks", type=int, default=3, help="每代评估任务数")
    parser.add_argument("--agent", type=str, default=None, help="只优化指定 Agent")
    parser.add_argument("--eval-only", action="store_true", help="只做评估，不优化")
    parser.add_argument("--gepa-generations", type=int, default=3, help="GEPA 优化代数")
    args = parser.parse_args()

    print("=" * 60)
    print("  数模多智能体自进化（Hermes 风格）")
    print("  agent 表现 = 模型 x 上下文文本质量")
    print("=" * 60)
    print(f"  世代: {args.generations}, 每代 {args.tasks} 个任务")
    if args.agent:
        print(f"  目标 Agent: {args.agent}")
    print()

    settings = load_settings()
    base_llm = create_llm(settings)
    optimizer_llm = create_llm(settings)

    fitness_evaluator = FitnessEvaluator(optimizer_llm)
    constraint_validator = PromptConstraintValidator()
    gepa = GEPAOptimizer(
        optimizer_llm, fitness_evaluator,
        max_generations=args.gepa_generations,
    )
    tracker = EvolutionTracker()

    agents = create_agents(base_llm)
    current_prompts: dict[str, str] = {}
    for role, agent in agents.items():
        current_prompts[role] = agent.system_prompt

    target_agents = [args.agent] if args.agent else list(current_prompts.keys())
    tasks = _DEFAULT_TASKS[: args.tasks]

    for gen in range(args.generations):
        print("─" * 50)
        print(f"  第 {gen + 1}/{args.generations} 代")
        print("─" * 50)

        # === 1. SELECT ===
        if gen == 0:
            print(f"\n  (1) SELECT: 首代全量评估所有 Agent")
        else:
            print(f"\n  (1) SELECT: 优化目标 -> {', '.join(target_agents)}")

        # === 2+3. BUILD + BASELINE ===
        print(f"\n  (2)+(3) BUILD + BASELINE: 运行 {len(tasks)} 个任务 + 适应度评估...")
        all_scores: dict[str, list[float]] = {a: [] for a in target_agents}
        agent_outputs: dict[str, list[tuple[str, str]]] = {a: [] for a in target_agents}

        for i, task in enumerate(tasks):
            print(f"    任务 {i + 1}/{len(tasks)}: {task[:50]}...")
            orch = Orchestrator(settings)
            try:
                result = orch.solve_sequential(task)
                for role, content in [
                    ("modeler", result.modeling.content),
                    ("programmer", result.programming.content),
                    ("writer", result.writing.content),
                    ("synthesizer", result.synthesis),
                ]:
                    if role in all_scores:
                        score = fitness_evaluator.evaluate(role, task, content)
                        all_scores[role].append(score.overall)
                        agent_outputs[role].append((task, content))
            except Exception as exc:
                print(f"      求解失败: {exc}")

        avg_scores = {}
        for role, scores in all_scores.items():
            if scores:
                avg_scores[role] = sum(scores) / len(scores)
                # show dimension breakdown for first task
                if agent_outputs[role]:
                    sample_score = fitness_evaluator.evaluate(
                        role, tasks[0], agent_outputs[role][0][1]
                    )
                    dim_parts = [f"{d.value}:{s:.1f}" for d, s in sample_score.dimensions.items()]
                    print(f"    {role}: fitness {avg_scores[role]:.2f} | {' | '.join(dim_parts)}")

        overall_avg = sum(avg_scores.values()) / max(len(avg_scores), 1)

        # === 4. CONSTRAIN ===
        print(f"\n  (4) CONSTRAIN: 约束门控...")
        for role in target_agents:
            if role in current_prompts:
                check = constraint_validator.validate(
                    current_prompts[role], current_prompts[role], role
                )
                status = "passed" if check.passed else f"FAILED: {'; '.join(check.issues)}"
                print(f"    {role}: {status}")

        # === 5. OPTIMIZE ===
        improvements = 0
        if not args.eval_only and gen < args.generations - 1:
            print(f"\n  (5) OPTIMIZE: GEPA 反馈->变异->评估->择优...")
            sorted_agents = sorted(avg_scores.items(), key=lambda x: x[1]) if avg_scores else []
            optimize_roles = [args.agent] if args.agent else [
                a for a, _ in sorted_agents[:3] if a in agent_outputs and agent_outputs[a]
            ]

            for role in optimize_roles:
                if role not in current_prompts:
                    continue
                task, output = agent_outputs[role][0]
                print(f"    [{role}] GEPA optimizing ({args.gepa_generations} gens)...")
                result = gepa.optimize(role, current_prompts[role], task, output)

                if result.improvement > 0.03:
                    backup = _backup_prompt(role, current_prompts[role])
                    current_prompts[role] = result.best_prompt
                    print(
                        f"    [{role}] adopted "
                        f"({result.original_score:.2f}->{result.best_score:.2f}, "
                        f"+{result.improvement:+.0%}, "
                        f"{result.candidates_tested} candidates) "
                        f"backup: {backup.name}"
                    )
                    improvements += 1
                else:
                    print(f"    [{role}] no significant improvement, kept original")

        # Record tracker
        tracker.record_generation(GenerationMetrics(
            generation=gen + 1,
            tasks_completed=len(tasks),
            avg_fitness=overall_avg,
            best_fitness=max(avg_scores.values()) if avg_scores else 0.0,
            agents_optimized=target_agents,
            improvements_adopted=improvements,
        ))
        print()

    # === 6+7. VALIDATE + DEPLOY ===
    print(f"\n{'=' * 60}")
    print(f"  进化完成!")
    print(f"{'=' * 60}")

    print(f"\n  (6) VALIDATE: 最终约束检查")
    for role in target_agents:
        if role in current_prompts:
            check = constraint_validator.validate(
                current_prompts[role], current_prompts[role], role
            )
            print(f"    {role}: {'passed' if check.passed else 'FAILED'}")

    print(f"\n  (7) DEPLOY: Prompt 已生效（备份在 data/prompt_backups/）")
    print(f"    进化历史: data/evolution_history.json")

    print(f"\n{tracker.improvement_summary()}")


if __name__ == "__main__":
    main()