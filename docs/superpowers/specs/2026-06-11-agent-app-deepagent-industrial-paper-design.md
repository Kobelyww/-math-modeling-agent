# Agent App DeepAgent Industrial Paper Design

Date: 2026-06-11

## Goal

重构 `agent_app` 为 DeepAgent 原生的工业可用数模论文生产系统。系统面向数学建模竞赛场景，支持输入赛题文字、数据文件和参考文献/PDF，输出可提交的竞赛论文包。

本次不是在旧 `Orchestrator` 上增加一层 DeepAgent 包装，而是把项目重构为稳定的领域模型、服务层、DeepAgent 工作流、质量评估和接口层。旧代码中有价值的能力可以迁移为服务或工具，但旧的巨型编排器不再作为主架构。

## Confirmed Decisions

- 重构方式：完全重构，不做兼容式小修。
- 核心框架：使用 `deepagents.create_deep_agent` 构建主协调器。
- 目标场景：数模竞赛完整论文包优先。
- 输入范围：赛题文字 + 数据文件 + 参考文献/PDF。
- 交付目标：生成竞赛提交包，而不是泛泛的分析回答。
- 架构目标：工业可用、可测试、可追踪、可恢复、可扩展。
- 第一版保留 CLI/Web/GUI 的用户价值，但接口层统一调用新的 Run API，不直接绑定旧编排器。

## Existing Project Context

当前 `agent_app` 已经具备不少可迁移资产：

- `agents.py`：8 个手写角色 Agent。
- `orchestrator.py`：多策略编排、`WorkflowResult`、输出保存。
- `tools.py`：Python 执行、LaTeX 编译、文献检索、笔记、写作规则等工具。
- `rag.py`：PDF/MD/TXT 知识库索引与混合检索。
- `literature.py`：arXiv、Semantic Scholar、Crossref 检索。
- `exploration.py`：文件系统和 Web 探索工具。
- `sandbox/`：Docker/Python 沙箱能力。
- `web/`、`gui.py`、`cli.py`：现有用户入口。

主要问题是这些能力被 demo 式地耦合在巨型编排器和自由文本输出中：

- 阶段状态和产物不是一等对象。
- 论文、代码、LaTeX 主要从 Markdown 中提取，结构不稳定。
- 输入附件、参考资料、实验结果、图表和论文之间缺少可追踪关系。
- 质量验收依赖提示词自觉，不具备强门禁。
- 接口层直接调用具体编排策略，难以替换内部架构。

本设计将保留可复用能力，但改变所有权边界。

## Product Scope

### In Scope

1. 定义 run 级任务模型，支持每次求解独立追踪。
2. 建立 DeepAgent 原生 `competition_paper` 工作流。
3. 支持赛题、数据文件、参考文献/PDF 的输入登记与 run 级索引。
4. 迁移 RAG、文献检索、数据分析、代码执行、LaTeX 编译为服务。
5. 为 DeepAgent 暴露结构化工具。
6. 引入阶段状态机、工具白名单和质量门禁。
7. 产出完整竞赛论文包。
8. 提供统一 Runner API 供 CLI/Web/GUI 使用。
9. 建立单元、集成和最小端到端测试。

### Out of Scope

- 第一版不追求兼容所有旧 `Orchestrator` 策略。
- 第一版不实现多人协同编辑论文。
- 第一版不保证所有机器都能编译 PDF；没有 LaTeX 环境时输出可诊断报告。
- 第一版不做真实竞赛评奖级自动判分。
- 第一版不把科研论文模板作为主输出；科研论文模式可在后续通过 workflow profile 扩展。

## Target Architecture

```text
agent_app/
  domain/
    models.py
    schemas.py
    errors.py
  deepagent/
    coordinator.py
    middleware.py
    prompts.py
    runner.py
  workflows/
    competition_paper.py
  services/
    run_store.py
    ingestion.py
    rag_service.py
    literature_service.py
    data_analysis.py
    code_execution.py
    latex_service.py
    artifact_service.py
  tools/
    competition.py
    data.py
    evidence.py
    experiment.py
    paper.py
  evaluators/
    input_gate.py
    modeling_gate.py
    experiment_gate.py
    paper_gate.py
    submission_gate.py
  interfaces/
    cli.py
    web.py
    gui.py
  infra/
    config.py
    logging.py
    paths.py
    serialization.py
  legacy/
    orchestrator.py
    agents.py
```

### Architecture Principles

- `domain/` 不依赖 DeepAgent、LangChain 或 UI，是最稳定层。
- `services/` 承载可测试业务能力，不把 LLM 协调逻辑写进服务。
- `tools/` 是 DeepAgent 调用服务的薄封装，必须有明确参数和返回结构。
- `deepagent/` 只负责协调、阶段推进、中间件和提示词。
- `interfaces/` 只调用 Runner API，不直接知道内部工具或 Agent。
- 旧模块迁入 `legacy/` 或在实现中逐步删除主入口引用。
- 现有顶层 `cli.py`、`gui.py`、`web/`、`tools.py` 在迁移期可保留为薄入口或兼容 facade，但核心实现应移动到新分层内，避免继续扩展旧文件。

## Domain Model

### RunSpec

用户发起任务的输入规范。

Fields:

- `question`: 赛题文字。
- `data_files`: 数据文件路径列表，支持 CSV、Excel、JSON、图片、PDF 附件。
- `reference_files`: 参考文献路径列表，支持 PDF、MD、TXT。
- `output_profile`: 输出类型，第一版固定为 `competition_paper`。
- `options`: top-k、最大修复次数、是否尝试编译 PDF、是否允许在线检索。

### RunState

运行过程状态。

Fields:

- `run_id`
- `stage`
- `created_at`
- `updated_at`
- `spec`
- `artifacts`
- `issues`
- `quality_reports`
- `token_usage`
- `elapsed_seconds`

### ProblemBrief

题目理解结果。

Fields:

- `background`
- `questions`
- `objectives`
- `constraints`
- `required_data`
- `deliverables`
- `risk_notes`

### DataAuditReport

数据审计结果。

Fields:

- `files`
- `field_dictionary`
- `missing_values`
- `outliers`
- `descriptive_statistics`
- `usable_features`
- `data_limitations`
- `recommended_preprocessing`

### EvidenceNote and BibliographyItem

参考资料和引用依据。

Fields:

- `source_id`
- `title`
- `authors`
- `year`
- `url_or_path`
- `summary`
- `relevance`
- `citation_key`

### ModelingPlan

建模方案。

Fields:

- `subproblem_plans`
- `variables`
- `parameters`
- `assumptions`
- `objective_functions`
- `constraints`
- `candidate_models`
- `selected_model`
- `algorithm_plan`
- `evaluation_metrics`
- `sensitivity_plan`

### ExperimentResult

实验执行结果。

Fields:

- `code_path`
- `execution_status`
- `stdout`
- `stderr`
- `result_files`
- `figure_files`
- `tables`
- `metrics`
- `sensitivity_results`
- `reproducibility_notes`

### PaperDraft

论文草稿。

Fields:

- `markdown_path`
- `latex_path`
- `sections`
- `figures_used`
- `tables_used`
- `references_used`
- `appendix_files`

### QualityReport

质量审查结果。

Fields:

- `gate_name`
- `passed`
- `score`
- `findings`
- `required_fixes`
- `optional_improvements`

## DeepAgent Workflow

Workflow name: `competition_paper`.

```text
ingest_inputs
-> understand_problem
-> audit_data
-> retrieve_evidence
-> plan_modeling
-> run_experiments
-> analyze_results
-> draft_paper
-> review_and_revise
-> package_submission
```

### Stage Responsibilities

1. `ingest_inputs`
   - 创建 run 目录。
   - 保存赛题文本。
   - 登记数据和参考文献。
   - 生成 `inputs_manifest.json`。

2. `understand_problem`
   - 解析背景、小问、目标、约束和交付要求。
   - 输出 `problem_brief.md` 和结构化 `ProblemBrief`。

3. `audit_data`
   - 读取数据文件概要。
   - 识别字段、缺失、异常、可用特征和风险。
   - 输出 `data_audit.md`。

4. `retrieve_evidence`
   - 构建 run 级参考资料索引。
   - 查询本地知识库和用户参考资料。
   - 可选调用在线文献检索。
   - 输出 `evidence_notes.md` 和参考文献清单。

5. `plan_modeling`
   - 制定每个小问的建模策略。
   - 选择主模型、备选模型、评价指标、求解算法和灵敏度分析方案。
   - 输出 `modeling_report.md`。

6. `run_experiments`
   - 生成或修复 `solve.py`。
   - 执行代码并保存日志。
   - 生成结果表格、图表和结构化结果。
   - 失败时进入 repair loop，达到上限后记录降级说明。

7. `analyze_results`
   - 解释数值结果。
   - 形成灵敏度/鲁棒性分析。
   - 提炼模型优缺点和改进方向。

8. `draft_paper`
   - 生成竞赛论文 Markdown 草稿和 `paper.tex`。
   - 正文必须覆盖竞赛论文必备章节。
   - 附录必须引用或包含核心代码。

9. `review_and_revise`
   - 运行质量评估器。
   - 对必修问题触发 DeepAgent 修订。
   - 保存 `review_report.md`。

10. `package_submission`
    - 汇总产物。
    - 尝试编译 `paper.pdf`。
    - 生成 `final_synthesis.md` 和 `run.json`。

## DeepAgent Coordinator

`create_competition_paper_agent(llm, services, middleware)` 返回 DeepAgent 实例。

Coordinator system prompt 需要明确：

- 你是数模竞赛论文生产总协调器。
- 目标不是聊天回答，而是完成可提交论文包。
- 必须按阶段推进，不跳过数据审计、建模规划、实验和审查。
- 每个小问必须被追踪到建模方案、代码或论文段落。
- 不能伪造实验结果；无法执行或无法编译时必须写清诊断。
- 最终输出必须引用 run 目录中的实际产物。

## Stage Middleware

DeepAgent 使用阶段中间件控制执行：

- 当前阶段注入阶段说明、可用工具和通过条件。
- 非当前阶段工具不可调用。
- 每次工具调用后记录 `tool_history`。
- 每阶段检查结构化产物是否存在。
- 质量门禁未过时，进入修复阶段或保持当前阶段。
- 到达最大修复次数后允许降级前进，但必须写入 `RunIssue` 和审查报告。

阶段中间件应和 `zhihu_fiction/agents.py` 中的 `StageGateMiddleware` 思路一致，但要改为通用、可测试、run-aware 的实现。

## DeepAgent Tools

工具是服务层的薄封装，参数和返回值必须稳定。

### ingest_inputs

Inputs:

- `run_id`
- `question`
- `data_files`
- `reference_files`

Output:

- `inputs_manifest`
- `saved_paths`
- `warnings`

### analyze_problem

Inputs:

- `run_id`
- `question`

Output:

- `ProblemBrief`
- `problem_brief_path`

### audit_data

Inputs:

- `run_id`
- `file_paths`

Output:

- `DataAuditReport`
- `data_audit_path`

### retrieve_evidence

Inputs:

- `run_id`
- `query`
- `reference_files`
- `top_k`
- `allow_online_search`

Output:

- `evidence_notes`
- `bibliography`
- `evidence_notes_path`

### plan_model

Inputs:

- `run_id`
- `problem_brief`
- `data_audit`
- `evidence_notes`

Output:

- `ModelingPlan`
- `modeling_report_path`

### run_experiment

Inputs:

- `run_id`
- `modeling_plan`
- `data_files`

Output:

- `ExperimentResult`
- `code_path`
- `result_paths`
- `figure_paths`

### repair_code

Inputs:

- `run_id`
- `code_path`
- `stderr`
- `modeling_plan`

Output:

- `repaired_code_path`
- `repair_notes`

### draft_competition_paper

Inputs:

- `run_id`
- `problem_brief`
- `data_audit`
- `modeling_plan`
- `experiment_result`
- `evidence_notes`

Output:

- `PaperDraft`
- `paper_markdown_path`
- `paper_tex_path`

### compile_latex

Inputs:

- `run_id`
- `tex_path`

Output:

- `compiled`
- `pdf_path`
- `log_path`
- `diagnostics`

### review_submission

Inputs:

- `run_id`
- `paper_draft`
- `experiment_result`
- `artifacts`

Output:

- `QualityReport`
- `review_report_path`

### package_submission

Inputs:

- `run_id`

Output:

- `package_manifest`
- `final_synthesis_path`
- `run_json_path`

## Quality Gates

### Input Gate

Must pass:

- 赛题文本已保存。
- 所有数据文件和参考文献已登记。
- 文件路径被限制在允许目录内。
- 可读取参考资料已进入 run 级索引或写入失败原因。
- 数据文件至少完成概要读取；失败原因写入 `data_audit.md`。

### Modeling Gate

Must pass:

- 每个小问都有建模目标。
- 变量、参数、约束、目标函数或评价指标存在。
- 模型假设存在，且不明显冲突。
- 至少有一种主模型和一种备选或对比思路。
- 有求解算法说明和适用性解释。

### Experiment Gate

Must pass:

- `solve.py` 存在。
- 至少一次 Python 执行成功，或失败后有清晰降级诊断。
- 有结果表格、指标或结构化结果文件。
- 有图表生成计划；适合生成图表时保存到 `figures/`。
- 有灵敏度分析或鲁棒性分析，不能只有空泛描述。

### Paper Gate

Must pass:

- 摘要。
- 关键词。
- 问题重述。
- 模型假设。
- 符号说明。
- 问题分析。
- 模型建立与求解。
- 结果分析。
- 灵敏度或鲁棒性分析。
- 模型评价与改进。
- 参考文献。
- 附录代码。

Also must pass:

- 不出现明显占位文本，如 `TODO`、`待补充`、`占位`。
- 图表在正文中被引用。
- 参考文献有正文引用或证据说明。
- 公式、变量命名基本一致。

### Submission Gate

Must pass:

- `modeling_report.md`
- `solve.py`
- `paper.tex`
- `review_report.md`
- `final_synthesis.md`
- `run.json`

Optional artifacts:

- `paper.pdf` when LaTeX is available.
- `figures/` when the problem or data supports visualization.
- `results/` when experiments produce structured results.

## Output Package

Each run writes to:

```text
agent_app/output/runs/<run_id>/
  inputs_manifest.json
  problem_brief.md
  data_audit.md
  evidence_notes.md
  modeling_report.md
  solve.py
  results/
  figures/
  paper.md
  paper.tex
  paper.pdf
  review_report.md
  final_synthesis.md
  run.json
```

`paper.pdf` is present only when compilation succeeds. When compilation fails, the run must include a LaTeX log and diagnostics in `review_report.md`.

## Runner API

Interfaces should call a stable API:

```python
from agent_app.deepagent.runner import CompetitionPaperRunner
from agent_app.domain.models import RunSpec

runner = CompetitionPaperRunner.from_settings(settings)
result = runner.run(
    RunSpec(
        question="...",
        data_files=[...],
        reference_files=[...],
        output_profile="competition_paper",
    )
)
```

Runner returns a `RunResult`. `RunState` remains the persisted run snapshot managed by `RunStore`.

`RunResult` fields:

- `run_id`
- `status`
- `stage`
- `artifacts`
- `quality_reports`
- `summary`

Streaming interfaces can subscribe to run events:

- `stage_started`
- `tool_started`
- `tool_finished`
- `gate_failed`
- `repair_started`
- `artifact_written`
- `run_finished`

## Interfaces

### CLI

The CLI should expose:

- `/paper <question>`: run competition paper workflow.
- `/attach <path>`: add data/reference files before running.
- `/runs`: list recent runs.
- `/run <run_id>`: inspect run artifacts and status.

Existing general chat or old strategy commands may remain only if they do not obscure the new primary workflow.

### Web

The Web API should expose:

- create run.
- upload files.
- stream run events over WebSocket.
- query run status.
- list artifacts.
- download package files.

### GUI

The GUI should center on the run workflow:

- problem input.
- file upload.
- reference upload.
- run progress timeline.
- artifact viewer.
- quality report viewer.

## Migration Strategy

The refactor should happen in controlled slices:

1. Add domain models and run store.
2. Add services around existing capabilities.
3. Add structured DeepAgent tools.
4. Add stage middleware and coordinator.
5. Add runner and minimal CLI path.
6. Add quality gates.
7. Add Web/GUI integration.
8. Move old orchestrator and agents behind `legacy/` or remove from public exports.
9. Update README and tests.

This order keeps the project runnable while replacing the core architecture.

## Testing Strategy

### Unit Tests

- Domain model serialization and validation.
- Run directory creation and artifact saving.
- Path safety checks.
- Tool input/output schema.
- Quality gate pass/fail cases.
- LaTeX diagnostics parsing.
- Data audit for CSV/Excel/minimal bad file cases.

### Integration Tests

- Run-level RAG indexing of local reference files.
- Code execution service writes logs and results.
- Paper draft service writes Markdown and TeX.
- Stage middleware enforces tool whitelist.
- Failed experiment triggers repair path.

### End-to-End Smoke Test

Use a tiny deterministic modeling problem with a small CSV:

- create run.
- ingest inputs.
- audit data.
- plan a simple model.
- execute generated or fixture code.
- draft paper.
- run quality gates.
- package artifacts.

The smoke test must not require real external API calls. LLM and DeepAgent calls should be mockable or replaceable with fixture responses.

## Reliability and Safety

- All run paths must be under `agent_app/output/runs/<run_id>`.
- Uploaded or referenced files must be copied or safely registered through `InputIngestionService`.
- Tools must not accept arbitrary absolute writes.
- Code execution should default to sandboxed execution with timeout.
- Online literature search should be optional and degrade gracefully.
- Missing API keys should produce actionable diagnostics, not import-time failure.
- Every run should leave enough state for debugging even when it fails.

## Success Criteria

The refactor is successful when:

1. A user can provide 赛题、数据文件和参考文献/PDF and start one run through the new Runner API.
2. The run creates a traceable `output/runs/<run_id>` directory.
3. DeepAgent advances through the defined stages with tool whitelist enforcement.
4. The system produces at least `modeling_report.md`, `solve.py`, `paper.tex`, `review_report.md`, `final_synthesis.md`, and `run.json`.
5. Quality gates catch missing sections, missing code, failed experiments, and obvious placeholder text.
6. CLI or another interface can display run status and final artifacts.
7. Tests cover the core architecture without needing real external API calls.

## Risks

- DeepAgent API differences may require an adapter layer; the design isolates this in `deepagent/coordinator.py` and `deepagent/runner.py`.
- Full PDF compilation depends on local LaTeX availability; failure is acceptable when diagnostics are saved.
- Fully automated mathematical modeling can still make weak model choices; quality gates reduce but do not eliminate this risk.
- A complete UI rewrite could slow the core refactor; the first implementation should prioritize Runner + CLI before Web/GUI polish.
