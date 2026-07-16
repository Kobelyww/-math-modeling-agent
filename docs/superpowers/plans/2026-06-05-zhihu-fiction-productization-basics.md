# Zhihu Fiction Productization Basics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `zhihu_fiction` easy to configure, start, understand, and verify before deeper MVP feature work begins.

**Architecture:** Keep the current file-based project structure and CLI/Web entry points. Add a checked-in environment example, improve configuration parsing errors in `config.py`, and add tests that lock down configuration behavior. Documentation remains in `zhihu_fiction/README.md` and should describe both CLI and Web usage without introducing new runtime behavior.

**Tech Stack:** Python 3.11, `python-dotenv`, pytest, DeepSeek environment variables, FastAPI/Uvicorn for Web startup instructions.

---

## Scope

This plan implements only the productization-basics slice of `docs/superpowers/specs/2026-06-05-zhihu-fiction-mvp-design.md`:

- Add `.env.example` with supported DeepSeek variables.
- Improve missing and malformed environment variable messages in `config.py`.
- Ensure documentation covers setup, CLI, Web, data directories, tests, and safety notes.
- Add tests for config loading behavior.
- Run existing `zhihu_fiction` tests.

This plan does not implement structured review, skill-card schema changes, Web workspace redesign, or publishing package schema changes.

## File Structure

### Create

- `zhihu_fiction/.env.example`
  - Checked-in template for all supported environment variables.

- `zhihu_fiction/tests/test_config.py`
  - Unit tests for config loading, missing API key error, invalid numeric config error, model alias behavior, and per-agent temperature overrides.

### Modify

- `zhihu_fiction/config.py`
  - Add focused parsing helpers for floats and ints.
  - Improve `DEEPSEEK_API_KEY` setup message.
  - Include variable name and invalid value in malformed numeric errors.
  - Preserve existing `Settings`, `AgentConfig`, `MODEL_ALIASES`, and `load_settings` public behavior.

- `zhihu_fiction/README.md`
  - Review and adjust only if current README lacks `.env.example`, setup, Web, data, safety, or testing instructions.

---

## Task 1: Add config tests before changing implementation

**Files:**
- Create: `zhihu_fiction/tests/test_config.py`
- Modify: none
- Test: `zhihu_fiction/tests/test_config.py`

- [ ] **Step 1: Create failing tests for current config behavior**

Create `zhihu_fiction/tests/test_config.py` with this content:

```python
"""Tests for zhihu_fiction configuration loading."""
from __future__ import annotations

import pytest

from zhihu_fiction.config import load_settings


def test_load_settings_reads_required_and_optional_values(tmp_path, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "DEEPSEEK_API_KEY=test-key",
                "DEEPSEEK_API_BASE=https://example.test/v1",
                "DEEPSEEK_MODEL=deepseek-v4",
                "DEEPSEEK_TEMPERATURE=0.25",
                "DEEPSEEK_MAX_RETRIES=5",
            ]
        ),
        encoding="utf-8",
    )

    settings = load_settings(env_file)

    assert settings.api_key == "test-key"
    assert settings.api_base == "https://example.test/v1"
    assert settings.model == "deepseek-v4-pro"
    assert settings.temperature == 0.25
    assert settings.max_retries == 5


def test_load_settings_missing_api_key_mentions_env_example(tmp_path, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("DEEPSEEK_MODEL=deepseek-v4-pro\n", encoding="utf-8")

    with pytest.raises(RuntimeError) as exc_info:
        load_settings(env_file)

    message = str(exc_info.value)
    assert "DEEPSEEK_API_KEY" in message
    assert ".env.example" in message
    assert str(env_file) in message


def test_load_settings_rejects_invalid_temperature(tmp_path, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "DEEPSEEK_API_KEY=test-key",
                "DEEPSEEK_TEMPERATURE=hot",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError) as exc_info:
        load_settings(env_file)

    message = str(exc_info.value)
    assert "DEEPSEEK_TEMPERATURE" in message
    assert "hot" in message
    assert "float" in message


def test_load_settings_rejects_invalid_max_retries(tmp_path, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "DEEPSEEK_API_KEY=test-key",
                "DEEPSEEK_MAX_RETRIES=many",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError) as exc_info:
        load_settings(env_file)

    message = str(exc_info.value)
    assert "DEEPSEEK_MAX_RETRIES" in message
    assert "many" in message
    assert "integer" in message


def test_load_settings_reads_agent_temperature_overrides(tmp_path, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "DEEPSEEK_API_KEY=test-key",
                "DEEPSEEK_TEMPERATURE=0.7",
                "DEEPSEEK_REVIEWER_TEMPERATURE=0.2",
                "DEEPSEEK_DRAFT_WRITER_TEMPERATURE=0.9",
            ]
        ),
        encoding="utf-8",
    )

    settings = load_settings(env_file)

    assert settings.get_agent_config("reviewer").temperature == 0.2
    assert settings.get_agent_config("draft_writer").temperature == 0.9
    assert settings.get_agent_config("polisher").temperature == 0.7
```

- [ ] **Step 2: Run config tests to verify failures**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_config.py -v
```

Expected:

```text
FAILED zhihu_fiction/tests/test_config.py::test_load_settings_missing_api_key_mentions_env_example
FAILED zhihu_fiction/tests/test_config.py::test_load_settings_rejects_invalid_temperature
FAILED zhihu_fiction/tests/test_config.py::test_load_settings_rejects_invalid_max_retries
```

The exact number of failures may differ if previous work already improved `config.py`, but at least one test should fail before implementation.

---

## Task 2: Improve configuration parsing and setup errors

**Files:**
- Modify: `zhihu_fiction/config.py`
- Test: `zhihu_fiction/tests/test_config.py`

- [ ] **Step 1: Replace `config.py` with explicit parsing helpers**

Modify `zhihu_fiction/config.py` to match this implementation:

```python
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

APP_ROOT = Path(__file__).resolve().parent

MODEL_ALIASES = {
    "deepseek-v4": "deepseek-v4-pro",
}

AGENT_ROLES = [
    "topic_analyzer",
    "outline_planner",
    "draft_writer",
    "polisher",
    "reviewer",
    "synthesizer",
]


@dataclass(frozen=True)
class AgentConfig:
    role: str
    temperature: float = 0.7
    max_tokens: int = 8192


@dataclass(frozen=True)
class Settings:
    api_key: str
    api_base: str | None
    model: str
    temperature: float
    max_retries: int = 3
    agent_configs: dict[str, AgentConfig] = field(default_factory=dict)

    def get_agent_config(self, role: str) -> AgentConfig:
        return self.agent_configs.get(role, AgentConfig(role=role, temperature=self.temperature))


def _parse_float_env(name: str, default: str) -> float:
    raw_value = os.getenv(name, default)
    try:
        return float(raw_value)
    except ValueError as exc:
        raise RuntimeError(
            f"Invalid {name}={raw_value!r}; expected a float such as 0.7."
        ) from exc


def _parse_int_env(name: str, default: str) -> int:
    raw_value = os.getenv(name, default)
    try:
        return int(raw_value)
    except ValueError as exc:
        raise RuntimeError(
            f"Invalid {name}={raw_value!r}; expected an integer such as 3."
        ) from exc


def load_settings(env_path: str | Path | None = None) -> Settings:
    if env_path is None:
        candidates = [APP_ROOT / ".env", APP_ROOT.parent / ".env"]
        env_path = next((p for p in candidates if p.exists()), candidates[0])
    else:
        env_path = Path(env_path)

    load_dotenv(env_path, override=True)

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        example_path = APP_ROOT / ".env.example"
        raise RuntimeError(
            "Missing DEEPSEEK_API_KEY. "
            f"Create or update {env_path} using {example_path} as a template."
        )

    temperature = _parse_float_env("DEEPSEEK_TEMPERATURE", "0.7")
    raw_model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro")
    model = MODEL_ALIASES.get(raw_model, raw_model)
    max_retries = _parse_int_env("DEEPSEEK_MAX_RETRIES", "3")

    agent_configs: dict[str, AgentConfig] = {}
    for role in AGENT_ROLES:
        key = f"DEEPSEEK_{role.upper()}_TEMPERATURE"
        if key in os.environ:
            agent_configs[role] = AgentConfig(role=role, temperature=_parse_float_env(key, "0.7"))

    return Settings(
        api_key=api_key,
        api_base=os.getenv("DEEPSEEK_API_BASE") or None,
        model=model,
        temperature=temperature,
        max_retries=max_retries,
        agent_configs=agent_configs,
    )
```

- [ ] **Step 2: Run config tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_config.py -v
```

Expected:

```text
5 passed
```

- [ ] **Step 3: Run existing zhihu_fiction tests**

Run:

```bash
python -m pytest zhihu_fiction/tests -v
```

Expected:

```text
passed
```

The exact number of tests should include the new config tests plus existing agent and pipeline tests.

- [ ] **Step 4: Commit config improvements**

Only commit if the current session has explicit approval to commit. If approved, run:

```bash
git add zhihu_fiction/config.py zhihu_fiction/tests/test_config.py
git commit -m "$(cat <<'EOF'
Improve zhihu_fiction configuration errors

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

If commit approval is not available, skip the commit and report the changed files.

---

## Task 3: Add environment template

**Files:**
- Create: `zhihu_fiction/.env.example`
- Test: manual file inspection plus full tests

- [ ] **Step 1: Create `.env.example`**

Create `zhihu_fiction/.env.example` with this content:

```env
# Required: DeepSeek API key used by zhihu_fiction.
DEEPSEEK_API_KEY=

# Optional: override the API base URL when using a compatible proxy or gateway.
DEEPSEEK_API_BASE=

# Optional: model name. deepseek-v4 is accepted as an alias for deepseek-v4-pro.
DEEPSEEK_MODEL=deepseek-v4-pro

# Optional: default generation temperature for agents without a role-specific override.
DEEPSEEK_TEMPERATURE=0.7

# Optional: retry count for LLM calls.
DEEPSEEK_MAX_RETRIES=3

# Optional: role-specific temperatures.
DEEPSEEK_TOPIC_ANALYZER_TEMPERATURE=0.7
DEEPSEEK_OUTLINE_PLANNER_TEMPERATURE=0.7
DEEPSEEK_DRAFT_WRITER_TEMPERATURE=0.8
DEEPSEEK_POLISHER_TEMPERATURE=0.7
DEEPSEEK_REVIEWER_TEMPERATURE=0.3
DEEPSEEK_SYNTHESIZER_TEMPERATURE=0.5
```

- [ ] **Step 2: Verify the file is tracked as a template, not a secret**

Run:

```bash
git diff -- zhihu_fiction/.env.example
```

Expected:

```text
+DEEPSEEK_API_KEY=
```

There must be no real API key or account credential in the file.

- [ ] **Step 3: Run config tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_config.py -v
```

Expected:

```text
5 passed
```

- [ ] **Step 4: Commit environment template**

Only commit if explicitly approved. If approved, run:

```bash
git add zhihu_fiction/.env.example
git commit -m "$(cat <<'EOF'
Add zhihu_fiction environment template

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

If commit approval is not available, skip the commit and report the changed file.

---

## Task 4: Align README with productization basics

**Files:**
- Modify: `zhihu_fiction/README.md`
- Test: documentation review and full tests

- [ ] **Step 1: Inspect README for required sections**

Open `zhihu_fiction/README.md` and verify these headings exist:

```text
功能概览
项目结构
安装与准备
环境变量
命令行使用
Web 服务使用
数据与输出
发布与合规注意事项
测试
当前适合继续改进的方向
推荐业务定位
```

- [ ] **Step 2: If any heading is missing, replace README with the approved productization README**

Use this exact content only if the current README is missing one or more required sections:

```markdown
# Zhihu Fiction Studio

`zhihu_fiction` 是一个面向爆款故事创作的多智能体内容生产系统。它围绕“热点抓取 → 技能蒸馏 → 多 Agent 创作 → 评审改写 → 多平台发布包导出/辅助发布”构建，适合用来探索知乎短篇、网文开篇、平台化故事内容和 AI 写作工作流。

## 功能概览

- **热点采集**：抓取知乎热榜、搜索话题，支持手动录入兜底。
- **技能蒸馏**：从热门内容中提炼题材、开篇钩子、反转节奏、互动引导等创作技能。
- **多 Agent 创作**：由选题分析、大纲规划、正文创作、润色、评审、发布方案等角色协作完成作品。
- **质量评审与改写**：按开篇钩子、节奏、人设、逻辑、情绪张力、金句密度等维度审稿，并可触发定向修改。
- **多章节支持**：支持续写和多章节创作，自动携带前文上下文。
- **多平台发布包**：可导出知乎盐选、起点、番茄等平台适配的标题、简介、标签和正文格式。
- **Web 工作台**：提供 FastAPI 服务、SSE 流式进度、运行历史、作品查看、技能库和定时任务接口。
- **浏览器辅助发布**：支持基于 Playwright 的知乎辅助发布流程。

## 项目结构

```text
zhihu_fiction/
├── agents.py             # DeepAgent 工具函数、系统提示词、评审 Agent
├── automator_zhihu.py    # 知乎浏览器辅助发布
├── base.py               # 内容规范化、基础工具
├── cli.py                # 交互式命令行入口
├── config.py             # 环境变量和模型配置
├── distiller.py          # 爆款内容技能蒸馏
├── exporter.py           # 多平台发布包导出
├── llm.py                # LLM 创建逻辑
├── orchestrator.py       # Coordinator 调用和工作流兼容封装
├── pipeline.py           # 自动化流水线、调度、检查点、内容安全
├── scraper.py            # 知乎热榜/搜索/手动录入采集
├── server.py             # FastAPI Web 服务和 SSE 接口
├── skills_store.py       # 技能库存取
├── tools.py              # 辅助工具
├── publishers/           # 知乎、起点、番茄发布包适配器
├── static/               # Web 前端静态资源
├── tests/                # 单元测试
├── data/                 # 抓取数据、技能库、认证状态等运行数据
└── output/               # 生成作品、发布包、流水线记录
```

## 安装与准备

建议从仓库根目录执行命令。

```bash
pip install -r zhihu_fiction/requirements.txt
```

如果需要使用浏览器辅助发布：

```bash
playwright install chromium
```

## 环境变量

复制模板并填写 API key：

```bash
cp zhihu_fiction/.env.example zhihu_fiction/.env
```

`.env` 示例：

```env
DEEPSEEK_API_KEY=your_api_key
DEEPSEEK_MODEL=deepseek-v4-pro
DEEPSEEK_API_BASE=
DEEPSEEK_TEMPERATURE=0.7
DEEPSEEK_MAX_RETRIES=3
```

可选的 Agent 温度配置：

```env
DEEPSEEK_TOPIC_ANALYZER_TEMPERATURE=0.7
DEEPSEEK_OUTLINE_PLANNER_TEMPERATURE=0.7
DEEPSEEK_DRAFT_WRITER_TEMPERATURE=0.8
DEEPSEEK_POLISHER_TEMPERATURE=0.7
DEEPSEEK_REVIEWER_TEMPERATURE=0.3
DEEPSEEK_SYNTHESIZER_TEMPERATURE=0.5
```

## 命令行使用

启动交互式 CLI：

```bash
python -m zhihu_fiction.cli
```

常用命令：

```text
/scrape                 抓取知乎热榜
/search <关键词>        搜索知乎话题
/manual                 手动录入热门内容
/files                  查看已抓取文件
/distill                从已抓取内容蒸馏创作技能
/distill_file <文件>    蒸馏指定文件
/skills                 查看技能库题材
/skill <题材>           查看指定题材技能卡
/create <主题>          完整多 Agent 创作
/fast <主题>            快速创作
/polish <主题>          精打磨模式
/stream <主题>          流式输出创作过程
/outputs                查看已生成作品
/load <文件名>          加载历史作品
/continue               基于已加载作品续写下一章
/publish                导出最近作品的多平台发布包
/publish <主题>         创作并导出发布包
/autopublish            浏览器辅助发布到知乎
/mode <模式>            设置创作模式：fast、polish、full
/genre <题材>           设置目标题材
/help                   查看帮助
/exit                   退出
```

推荐流程：

```text
/scrape
/distill
/genre 悬疑
/create 一个密室逃脱中发现同伴是凶手的故事
/publish
```

## Web 服务使用

启动 FastAPI 服务：

```bash
uvicorn zhihu_fiction.server:app --reload
```

浏览器打开本地服务首页即可使用 Web 工作台。

主要接口：

```text
GET  /                         Web 首页
POST /api/run                  启动一次创作任务
GET  /api/stream/{run_id}      订阅 SSE 流式进度
POST /api/run/continue         续写任务
GET  /api/runs                 查看运行历史
GET  /api/runs/{run_id}        查看单次运行详情
GET  /api/stories              查看生成作品列表
GET  /api/stories/{story_path} 查看作品内容
GET  /api/skills/genres        查看技能库题材
GET  /api/skills/{genre}       查看指定题材技能卡
GET  /api/scheduler            查看调度状态
POST /api/scheduler/start      启动定时创作
POST /api/scheduler/stop       停止定时创作
```

## 数据与输出

常见运行目录：

```text
zhihu_fiction/data/scraped/       抓取和手动录入的热门内容
zhihu_fiction/data/auth/          浏览器发布登录状态
zhihu_fiction/output/             生成的小说、发布包和中间结果
zhihu_fiction/output/.pipeline/   自动流水线运行历史、检查点和调度文件
```

`data/auth/` 可能包含平台登录状态，提交代码或分享项目时需要避免泄露。

## 发布与合规注意事项

- 抓取逻辑优先使用公开热榜接口，失败时可用搜索或手动录入兜底。
- 浏览器辅助发布依赖平台页面结构和账号状态，可能因平台改版或风控失效。
- 自动发布前建议人工检查标题、正文、标签、版权来源和平台规则。
- 生成内容已经包含基础内容安全润色，但不能替代人工审核。
- 不建议把 Web 服务直接暴露到公网；如需部署，应增加认证、收紧 CORS、隐藏内部异常信息。

## 测试

运行当前项目测试：

```bash
python -m pytest zhihu_fiction/tests
```

建议在修改以下模块后至少运行相关测试：

- `agents.py`：Agent 工具、提示词、输出格式
- `orchestrator.py`：Coordinator 输出解析和多章节上下文
- `pipeline.py`：自动流水线、评审改写、检查点和调度
- `exporter.py` / `publishers/`：发布包元数据和平台格式化
- `server.py`：API、SSE、运行状态和调度接口

## 当前适合继续改进的方向

1. **补齐结构化评审输出**：让 Reviewer 输出 JSON，便于统计、自动重写和质量看板。
2. **强化技能库版本管理**：按题材、平台、结构类型沉淀可复用创作技能。
3. **完善 Web 生产闭环**：加入任务队列、作品编辑、发布前人工确认和运行失败重试。
4. **加强测试覆盖**：增加 Fake LLM 端到端测试、发布器 mock 测试和 SSE API 测试。
5. **收紧生产安全配置**：区分开发/生产环境，限制 CORS，隐藏异常细节，保护登录状态文件。
6. **扩展业务边界**：从知乎短篇扩展到小红书故事、公众号故事、短剧脚本和网文开篇生成。

## 推荐业务定位

短期建议定位为：**AI 爆款故事生产与分发工作台**。

知乎可以作为第一个验证渠道，但系统能力更适合沉淀为跨平台内容生产工具：用热点和爆款样本做选题决策，用技能库复用创作方法，用多 Agent 工作流完成生产、评审、改写和发布包生成。
```

- [ ] **Step 3: Run tests after README changes**

Run:

```bash
python -m pytest zhihu_fiction/tests -v
```

Expected:

```text
passed
```

- [ ] **Step 4: Commit README updates**

Only commit if explicitly approved. If approved, run:

```bash
git add zhihu_fiction/README.md
git commit -m "$(cat <<'EOF'
Document zhihu_fiction setup and workflow

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

If commit approval is not available, skip the commit and report the changed file.

---

## Task 5: Final verification and handoff

**Files:**
- No new files
- Verify: `zhihu_fiction/config.py`, `zhihu_fiction/.env.example`, `zhihu_fiction/README.md`, `zhihu_fiction/tests/test_config.py`

- [ ] **Step 1: Run full zhihu_fiction test suite**

Run:

```bash
python -m pytest zhihu_fiction/tests -v
```

Expected:

```text
passed
```

- [ ] **Step 2: Run spec review for this slice**

Check these productization-basics requirements from `docs/superpowers/specs/2026-06-05-zhihu-fiction-mvp-design.md`:

```text
README focused on installation, configuration, CLI, Web, data directories, testing, and safety boundaries.
.env.example includes all supported DeepSeek variables.
config.py gives clear errors for missing or malformed config.
Existing tests pass.
```

Expected review result:

```text
All productization-basics requirements are covered.
Structured review, skill-card schema, Web workspace, and publishing package schema remain intentionally out of scope for later plans.
```

- [ ] **Step 3: Run quality review for this slice**

Check:

```text
config.py keeps load_settings public API compatible.
No API keys or auth files were added.
.env.example contains only blank or example values.
README does not claim unimplemented MVP features are already available.
test_config.py isolates environment values with tmp_path and monkeypatch.
```

Expected review result:

```text
Quality review passed.
```

- [ ] **Step 4: Inspect git status**

Run:

```bash
git status --short
```

Expected relevant changed files:

```text
 M zhihu_fiction/README.md
 M zhihu_fiction/config.py
?? zhihu_fiction/.env.example
?? zhihu_fiction/tests/test_config.py
```

The README may already be modified from earlier work. Do not stage unrelated files.

- [ ] **Step 5: Report handoff**

Report:

```text
Implemented productization-basics slice.
Changed files:
- zhihu_fiction/config.py
- zhihu_fiction/.env.example
- zhihu_fiction/README.md
- zhihu_fiction/tests/test_config.py
Validation:
- python -m pytest zhihu_fiction/tests -v: passed
Not implemented in this slice:
- structured review
- structured skill cards
- Web workspace MVP
- standardized publishing package
```

If commits were skipped because approval was unavailable, include:

```text
No commits created; commit approval was not provided.
```

---

## Self-Review

### Spec coverage

Covered:

- Productization basics.
- `.env.example`.
- Clearer config errors.
- README setup, CLI, Web, data, safety, and testing sections.
- Existing test suite verification.

Deferred to later plans:

- Structured review.
- Skill distillation schema improvements.
- Short-story Web workspace.
- Publishing package schema.

### Placeholder scan

No placeholders are required for execution. Every task includes exact file paths, commands, expected outcomes, and code content where implementation is needed.

### Type consistency

`load_settings`, `Settings`, `AgentConfig`, and `get_agent_config` signatures remain compatible with existing tests and callers.