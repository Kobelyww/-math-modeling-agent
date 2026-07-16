
# LLM Study — Multi-Agent Systems

This is a collection of multi-agent AI systems built with DeepSeek and LangChain.

## Active Projects

### agent_app/ — Math Modeling Multi-Agent System
8 specialist agents (DataEngineer, Modeler, Planner, Programmer, CodeDebugger, Writer, Reviewer, Synthesizer)
orchestrating the complete MCM/ICM competition workflow.

**Available skills for agent_app work:**
- `/mcm-academic-writing` — MCM paper writing standards (de-AI-fication, structure, abstract)
- `/nature-visualization` — Nature journal style plotting templates
- `/mcm-model-selection` — Mathematical model selection reference guide

**Nature Skills resources:** `agent_app/nature_skills/`
- `Rules/` — Academic writing rules, model references, diagram standards
- `Viz_Templates/` — 9 reusable Nature-style matplotlib templates
- `Tools/` — PDF extraction utility

### werewolf/ — AI Werewolf Game
12-player multi-agent game with role-playing agents under information asymmetry.
Supports Hermes-style self-evolution (7-step text optimization pipeline).

### zhihu_fiction/ — Zhihu Viral Fiction Generator
6-agent collaborative fiction writing with skill distillation and multi-platform publishing.

**开发规范：** 每次实现任务后，必须进行两轮审查：
1. **Spec 审查** — 对照 plan/spec 逐项检查是否按计划实现，有无遗漏或多余
2. **质量审查** — 检查代码质量、命名、边界情况、测试覆盖
只有两轮审查都通过后，才能进入下一个任务。

## Common Patterns
All projects share: BaseAgent (retry+error classification) → Specialized System Prompts → Orchestrator coordination.
