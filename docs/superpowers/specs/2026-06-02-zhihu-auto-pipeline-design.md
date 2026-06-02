# Zhihu Auto Pipeline — 知乎全自动创作发布流水线

## 概述

为 zhihu_fiction 项目增加端到端全自动流水线：自动抓取知乎热榜 → AI 自主选题 → DeepAgent 多智能体创作 → Reviewer 质量评审（不达标重试） → 浏览器全自动发布。Pipeline 设计为内容类型无关的编排引擎，后续可插拔接入短剧等内容类型。

## 核心原则

- 使用 **DeepAgents** 重构 Agent 层，Coordinator 作为 DeepAgent 通过 tool-calling 编排子智能体
- Reviewer 保持独立，不参与 Coordinator 的工具集，作为 Pipeline 层的质量门
- Pipeline 是编排引擎，不感知 Agent 内部实现
- 任何单次运行失败不影响后续调度

## 架构

```
┌─────────────────────────────────────────────────────────┐
│                    CLI / Scheduler                       │
│              /auto  │  /schedule start  │  cron          │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                    Pipeline                              │
│                                                         │
│  scraper ──► topic_selector ──► coordinator ──► reviewer ──► publisher
│                  │                   │               │            │
│             热榜抓取          DeepAgent        独立质量门   全自动发布
│                          tool-calling 编排      +重试       +验证
│                                                         │
│  运行日志: output/.pipeline/runs.jsonl                   │
│  调度配置: output/.pipeline/schedule.json                │
└─────────────────────────────────────────────────────────┘
```

## Agent 层重构（DeepAgents）

### 旧架构 → 新架构

```
旧：BaseAgent 子类 × 6 → Orchestrator 按固定顺序调用

新：DeepAgent Coordinator（1 个）
      ├─ tool: analyze_topic    → 选题分析
      ├─ tool: plan_outline     → 大纲规划
      ├─ tool: write_draft      → 初稿创作
      ├─ tool: polish_draft     → 润色优化
      └─ tool: synthesize       → 发布方案整合

    ReviewerAgent 独立，不注册为 tool
```

### Coordinator DeepAgent 设计

```python
# Coordinator 的系统提示词概要
"""
你是知乎爆款小说创作主编。你通过调用子智能体完成小说创作全流程。

你可以灵活决定调用顺序和次数：
- 大纲不理想时可以回头调整选题分析
- 初稿写完发现节奏有问题，可以调用润色后再判断
- 最终交付完整小说正文 + 发布方案

每个子智能体返回完整报告，你需要整合它们的结果。
"""
```

### Tool 定义（5 个工具函数）

每个 tool 是对应 Agent 角色的函数封装，内部调用 LLM 完成任务：

| Tool 名称 | 输入 | 输出 | 说明 |
|-----------|------|------|------|
| `analyze_topic` | topic, hot_trends, skills | 选题分析报告 | 分析爆款潜力，推荐题材方向 |
| `plan_outline` | topic, topic_analysis, skills | 故事大纲 | 5 段式结构 + 人物小传 + 钩子设计 |
| `write_draft` | topic, outline, skills | 完整小说正文 | 2000+ 字，完整故事 |
| `polish_draft` | topic, draft, feedback | 润色后全文 | 根据评审意见修改 |
| `synthesize` | topic, analysis, outline, final_draft | 发布方案 | 标题变体 + 话题标签 + 爆款评估 |

### Reviewer 独立设计

```python
class ReviewerAgent:
    """独立的质量评判者，不作为 Coordinator 的工具"""
    
    def review(self, draft: str, topic: str) -> ReviewResult:
        """返回评分配额（1-10）+ 扣分原因 + 改进建议"""
    
    @property
    def threshold(self) -> float:
        """质量门槛，默认 6.0"""
```

**为什么 Reviewer 独立：**
- Reviewer 是评判者，不是创作工具
- 如果注册为 tool，Coordinator 可能选择性调用或"优化"评审结果
- Pipeline 拿到 Coordinator 产出后调 Reviewer，不达标时把评审意见传回 Coordinator 重新创作

### 文件变更

| 操作 | 文件 | 说明 |
|------|------|------|
| **重写** | `agents.py` | 旧 6 个 BaseAgent → 5 个 tool 函数 + DeepAgent Coordinator |
| **重写** | `base.py` | 简化为 tool 注册机制和 DeepAgent 工厂 |
| **重写** | `orchestrator.py` | 简化为 thin wrapper，调用 Coordinator |
| 新增 | `pipeline.py` | Pipeline 编排引擎（内容类型无关） |
| 新增 | `automator_zhihu.py` | 知乎全自动发布器（真正自动点击） |
| 新增 | `tests/test_pipeline.py` | Pipeline 集成测试 |
| 新增 | `tests/test_agents.py` | Agent 层单元测试 |
| 新增 | `tests/test_automator_zhihu.py` | 发布器单元测试 |
| 修改 | `cli.py` | 新增 `/auto`、`/schedule` 命令 |
| 修改 | `__init__.py` | 移除 `workspace_shims`，更新导出 |
| 不改动 | `scraper.py` | 保持原样 |
| 不改动 | `distiller.py` | 保持原样 |
| 不改动 | `skills_store.py` | 保持原样 |
| 不改动 | `exporter.py` | 保持原样 |
| 不改动 | `publishers/` | 保持原样 |
| 不改动 | `config.py` `llm.py` | 保持原样 |

## Pipeline 核心接口

```python
class Pipeline:
    """内容类型无关的自动创作流水线"""

    def __init__(
        self,
        scraper: ScraperProtocol,           # 抓取策略
        topic_selector: TopicSelectorProtocol,  # 选题策略
        coordinator: DeepAgent,             # DeepAgent 主编排
        reviewer: ReviewerAgent,            # 独立质量门
        publisher: PublisherProtocol,       # 发布策略
        quality_threshold: float = 6.0,
        max_rewrites: int = 2,
        run_dir: Path = ...,
    ): ...

    def run(self, topic: str | None = None) -> RunResult: ...
    def run_scheduled(self, interval_minutes: int) -> ScheduledRun: ...
```

### 关键设计决策

1. **选题自动化** — 接收热榜 JSON，调 LLM 分析选最优，返回题材+主题
2. **Coordinator 自主编排** — 不硬编码 Agent 调用顺序，Coordinator 根据中间结果动态决策
3. **质量门** — Reviewer 评分 < threshold 时，评审意见传回 Coordinator 重新创作，最多 `max_rewrites` 轮
4. **异常隔离** — 每个阶段失败只影响当次运行，不中断调度循环

## 知乎全自动发布器 (`automator_zhihu.py`)

### 流程

1. 打开 `zhuanlan.zhihu.com/write`
2. 检测登录状态（session 过期 → `LoginRequired`）
3. 填入标题 → 填入正文 → 添加标签
4. 点击「发布」按钮
5. 检测确认弹窗 → 点击「确认发布」
6. 等待跳转到已发布文章页 → 提取文章 URL
7. 截图已发布页面 → 返回 URL + 截图路径

### 选择器策略（多层降级）

| 步骤 | 主策略 | 降级策略 |
|------|--------|---------|
| 标题输入框 | `[placeholder*='标题']` | 第一个 textarea |
| 编辑器 | `.public-DraftEditor-content` | `[contenteditable='true']` |
| 发布按钮 | `button:text-is("发布")` | 遍历所有 button 匹配文本 |
| 确认弹窗 | `.Modal button:has-text("确认")` | `[role='dialog'] button:has-text("发布")` |

### 异常处理

- 选择器失效 → 截图保存到 `data/debug/`，抛出 `PublishError` 含截图路径
- 发布后 30 秒未跳转 → 超时失败
- Session 过期 → 抛出 `LoginRequired`，Pipeline 捕获后记录并跳过

## CLI 命令

```
/auto [主题]            一次性全自动运行（不指定主题则 AI 自选）

/schedule start [N]h    启动定时调度（默认每 6 小时）
/schedule stop          停止调度
/schedule status        查看调度状态和下次运行时间
```

### 调度器设计

- 后台线程运行，不阻塞 CLI 交互
- 间隔可配置：命令参数或环境变量 `PIPELINE_INTERVAL_MINUTES`
- 每次运行追加到 `output/.pipeline/runs.jsonl`
- 调度状态持久化到 `output/.pipeline/schedule.json`，重启恢复

## 运行日志格式 (`runs.jsonl`)

```json
{
  "run_id": "20260602_143021",
  "trigger": "scheduled",
  "topic": "密室逃脱中发现同伴是凶手",
  "genre": "悬疑",
  "stages": {
    "scrape": {"status": "ok", "items": 50, "duration_s": 2.1},
    "select_topic": {"status": "ok", "selected": "...", "duration_s": 8.3},
    "create": {"status": "ok", "words": 3420, "coordinator_steps": 5, "duration_s": 45.2},
    "review": {"status": "ok", "score": 7.5, "rounds": 1, "duration_s": 12.1},
    "publish": {"status": "ok", "url": "https://zhuanlan.zhihu.com/p/...", "duration_s": 15.3}
  },
  "total_duration_s": 83.0,
  "timestamp": "2026-06-02T14:30:21"
}
```

## 错误处理和降级

```
scrape 失败
  ├─ 有缓存 → 用缓存（标记 stale）
  └─ 无缓存 → 本次运行终止，等下次调度

select_topic 失败
  └─ 用热度第一的话题兜底，标记 fallback

Coordinator 失败（LLM 错误/超时）
  ├─ 重试 3 次
  └─ 仍失败 → 本次运行终止

review 不达标（score < threshold）
  ├─ 第 1 轮：评审意见传回 Coordinator 重写
  ├─ 第 2 轮：再次重写
  └─ 仍不达标 → 记录跳过，不发布

publish 失败
  ├─ 选择器失效 → 截图保存，记录详细错误
  ├─ Session 过期 → 标记需要重新登录
  └─ 其他错误 → 记录，不阻塞调度
```

**全局原则：任何单次运行失败不影响后续调度。**

## 文件变更总览

| 操作 | 文件 | 说明 |
|------|------|------|
| 重写 | `agents.py` | 5 个 tool 函数 + DeepAgent Coordinator |
| 重写 | `base.py` | tool 注册 + DeepAgent 工厂 |
| 重写 | `orchestrator.py` | thin wrapper，调 Coordinator |
| 新增 | `pipeline.py` | Pipeline 编排引擎 |
| 新增 | `automator_zhihu.py` | 知乎全自动发布器 |
| 新增 | `tests/test_pipeline.py` | Pipeline 集成测试 |
| 新增 | `tests/test_agents.py` | Agent 层单元测试 |
| 新增 | `tests/test_automator_zhihu.py` | 发布器单元测试 |
| 修改 | `cli.py` | 新增 `/auto`、`/schedule` 命令 |
| 修改 | `__init__.py` | 移除 `workspace_shims`，更新导出 |

## 测试策略

- **test_agents.py**: 验证 5 个 tool 函数正确调用 LLM，Coordinator 的 tool schema 正确注册
- **test_pipeline.py**: Mock scraper/LLM/publisher，验证编排逻辑（选题→Coordinator 创作→评审→重试→发布→跳过）
- **test_automator_zhihu.py**: 验证选择器策略、登录检测、发布按钮定位、确认弹窗处理（条件跳过，需要 playwright）
- **手动验证**: 全流程跑通后，检查 `output/.pipeline/` 运行日志完整性