# Agent App DeepSeek Generation Loop Design

Date: 2026-07-13

## Goal

将 `agent_app` 的数模论文生产链路从模板生成升级为 DeepSeek V4 Pro 驱动的智能体生成闭环。

本次设计明确模型分工：Mimo 只负责视觉重建，后续赛题理解、建模、代码生成、论文写作、审查和返工全部由 DeepSeek V4 Pro 完成。目标是让系统真正生成可审阅、可复现、可返工的数模竞赛论文包，而不是只生成结构正确但内容浅的 demo 产物。

## Confirmed Decisions

- Mimo 只用于 PDF 页面、图片和表格的视觉重建。
- DeepSeek V4 Pro 是所有后续文本、代码和审查智能体的默认模型。
- 不再让 `plan_model`、`run_experiment`、`draft_competition_paper` 依赖固定 Python 字符串模板作为主要生成方式。
- 审查失败后必须触发对应阶段返工，不能继续把失败产物打包为 completed。
- 论文写作必须按章节拆分生成，避免单次 prompt 过长导致 LLM 忽略证据、丢公式或输出空泛段落。

## Model Routing

配置层拆分视觉模型和文本智能体模型：

```env
VISION_PROVIDER=mimo
MIMO_API_BASE=https://api.xiaomimimo.com/v1
MIMO_VISION_MODEL=mimo-v2.5-pro

TEXT_AGENT_PROVIDER=deepseek
DEEPSEEK_API_BASE=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-pro
```

Routing rules:

- PDF upload and visual table reconstruction call Mimo.
- `analyze_problem`, `plan_model`, `run_experiment`, `draft_competition_paper`, `review_submission`, and revise steps call DeepSeek.
- If Mimo fails, the system may fall back to text/PyMuPDF extraction, but it must mark table confidence as degraded.
- If DeepSeek fails, the current stage fails or retries; Mimo must not be used as fallback writer/modeler.

## Target Workflow

```text
PDF / text input
  -> Mimo visual reconstruction
  -> structured problem package
  -> DeepSeek problem analyst
  -> DeepSeek modeling planner
  -> DeepSeek programmer
  -> local code execution
  -> DeepSeek code debugger if needed
  -> DeepSeek section writers
  -> DeepSeek paper synthesizer
  -> three DeepSeek reviewers
  -> targeted revise loop
  -> package only if quality gates pass
```

## Structured Problem Package

The upload and ingestion layer must create a structured evidence bundle before downstream agents run.

Artifacts:

- `problem_spec.json`: normalized background, subproblems, objectives, constraints, deliverables.
- `tables.json`: all extracted or visually reconstructed tables with page source, title, schema, rows, confidence, and extraction method.
- `figures.json`: image and figure descriptions with page source and confidence.
- `source_map.json`: mapping from every extracted item to PDF page and extraction method.
- `question.md`: readable input snapshot for humans.

For B problem style tasks, table 1 and table 2 must be represented in `tables.json`. Downstream code must read this artifact instead of hardcoding table values in `solve.py`.

## DeepSeek Stage Responsibilities

### Problem Analyst

Input:

- `question.md`
- `problem_spec.json`
- `tables.json`
- `figures.json`

Output:

- corrected `problem_spec.json`
- `problem_brief.md`

Responsibilities:

- Identify the real number of subproblems instead of assuming four questions.
- Extract dependencies between subproblems.
- Flag missing tables, ambiguous OCR, or impossible requirements.
- Preserve exact question wording needed for modeling.

### Modeling Planner

Input:

- corrected `problem_spec.json`
- `tables.json`
- data audit
- evidence notes

Output:

- `model_plan.json`
- `modeling_report.md`

Responsibilities:

- Define variables, parameters, assumptions, objectives, constraints, algorithms, and sensitivity plan.
- For every planned experiment, explain its relationship to the paper conclusion: support, limit, or refute.
- Reject experiments that do not map to a conclusion.
- Avoid arbitrary constants unless they come from data, the problem statement, or an explicitly marked sensitivity parameter.

### Programmer

Input:

- `model_plan.json`
- `tables.json`
- data files

Output:

- `solve.py`
- `experiment_manifest.json`
- `results/*.csv`
- `results/model_equations.md`
- `run_log.md`

Responsibilities:

- Generate code from the model plan and structured tables.
- Run locally through the existing execution path.
- If code fails, invoke a DeepSeek code debugger with traceback, code, and expected artifact contract.
- Keep code deterministic and reproducible.
- Do not embed unexplained coefficients.

### Section Writers

Paper writing is split into chapter-level DeepSeek tasks.

Each section writer receives only:

- global paper outline
- symbol table
- relevant model snippets
- relevant result tables
- relevant reviewer constraints
- source references needed for that section

Section artifacts:

- `paper/sections/00_abstract.md`
- `paper/sections/01_problem_restatement.md`
- `paper/sections/02_assumptions.md`
- `paper/sections/03_symbols.md`
- `paper/sections/04_model_building.md`
- `paper/sections/05_solution_and_results.md`
- `paper/sections/06_sensitivity.md`
- `paper/sections/07_evaluation.md`
- `paper/sections/08_references.md`
- `paper/sections/09_appendix.md`

Rules:

- Each section must cite the artifacts it used.
- Result claims must point to exact result files or tables.
- Formula-heavy sections must use the shared symbol table.
- No section writer may invent a result not present in `results/`.
- The abstract is written last, after all result sections exist.

### Paper Synthesizer

Input:

- all section files
- `symbol_table.json`
- `model_plan.json`
- `experiment_manifest.json`

Output:

- `paper.md`
- `paper.tex`
- `paper_consistency_report.md`

Responsibilities:

- Merge sections into a coherent paper.
- Normalize terminology, symbols, numbering, table references, and figure references.
- Check that every conclusion has evidence.
- Check that all subproblems are answered.
- Produce LaTeX without losing Markdown content.

### Three Reviewers

Reviewers are DeepSeek V4 Pro roles:

- Model reviewer
- Experiment/code reviewer
- Paper reviewer

Each reviewer writes a Markdown report:

- `reviews/model_review.md`
- `reviews/experiment_review.md`
- `reviews/paper_review.md`

The main review report aggregates them into `review_report.md`.

## Revise Loop

Review failure triggers targeted invalidation:

- Model review failed: invalidate `model_plan.json`, `modeling_report.md`, `solve.py`, results, paper, and package.
- Experiment review failed: invalidate `solve.py`, results, paper, and package.
- Paper review failed: invalidate affected section files, `paper.md`, `paper.tex`, and package.

The system retries up to `max_repair_attempts`.

If still failing:

- Run status becomes `partial` or `needs_revision`.
- The Web UI shows required fixes.
- `package_submission` must not mark the run as completed.

## Web UX Changes

The paper page should expose the real process:

- Mimo visual reconstruction events.
- Structured table extraction preview.
- DeepSeek stage events.
- Section-by-section writing progress.
- Section artifact links.
- Reviewer reports.
- Revise loop events and invalidated artifacts.

The UI must not display all stages as complete if review failed.

## Testing Strategy

Unit tests:

- model routing selects Mimo only for visual reconstruction.
- DeepSeek is used for planner/programmer/writer/reviewer stages.
- `tables.json` is used by generated code instead of hardcoded B problem values.
- section writing creates individual section artifacts.
- paper synthesizer refuses missing required sections.
- review failure prevents successful package status.

Integration tests:

- B problem PDF upload creates `problem_spec.json`, `tables.json`, and source mapping.
- B problem full run produces code, result tables, section files, `paper.md`, and review reports.
- Shallow paper fails review and triggers revise instead of completed package.

Manual acceptance:

- Run `/Users/haobowang/Desktop/B题.pdf`.
- Confirm the system answers every detected subproblem.
- Confirm generated code reads structured table artifacts.
- Confirm paper has chapter-level content, formulas, result discussion, sensitivity analysis, and appendix.
- Confirm failed review stops packaging and exposes required fixes in Web.

## Implementation Order

1. Add model routing: Mimo visual provider and DeepSeek text agent provider.
2. Add structured problem package artifacts.
3. Replace deterministic B problem planner with DeepSeek planner.
4. Replace deterministic code generation with DeepSeek programmer plus execution/debug loop.
5. Replace monolithic paper writer with chapter-level section writers and synthesizer.
6. Connect three-reviewer reports to targeted revise loop.
7. Update Web streaming events for section writing and revise states.
8. Run B problem full-chain acceptance.
