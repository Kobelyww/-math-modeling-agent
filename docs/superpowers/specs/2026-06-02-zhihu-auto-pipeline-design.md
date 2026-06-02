# Zhihu Auto Pipeline — 知乎全自动创作发布流水线

## 概述

为 zhihu_fiction 项目增加端到端全自动流水线：自动抓取知乎热榜 → AI 自主选题 → 多 Agent 创作 → 质量评审（不达标重试） → 浏览器全自动发布。同时将 Pipeline 设计为内容类型无关的编排引擎，后续可插拔接入短剧等内容类型的 Agent 链。

## 核心原则

- **不改动**现有 `agents.py`、`orchestrator.py`、`publishers/`——它们继续作为库被 Pipeline 调用
- `pipeline.py` 是新增的编排层，内容类型无关，Agent 链和 Publisher 通过配置注入
- 知乎发布自动化重写为独立模块 `automator_zhihu.py`，借鉴 MCP 服务已有的完整实现
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
│  scraper ──► topic_selector ──► agent_chain ──► gate ──► publisher
│                  │                   │            │         │
│             热榜抓取          选题→大纲→初稿   评审阈值   全自动发布
│                              →评审→润色       +重试      +验证
│                                                         │
│  运行日志: output/.pipeline/runs.jsonl                   │
│  调度配置: output/.pipeline/schedule.json                │
└─────────────────────────────────────────────────────────┘

现有模块（不改动）：
  agents.py  orchestrator.py  scraper.py  distiller.py  exporter.py
  publishers/  skills_store.py  llm.py  config.py

新增模块：
  pipeline.py         — Pipeline 编排引擎（内容类型无关）
  automator_zhihu.py  — 知乎全自动发布（真正自动点击发布+验证）

修改模块：
  cli.py              — 新增 /auto、/schedule 命令
  __init__.py         — 移除 workspace_shims 导入
```

## Pipeline 核心接口

```python
class Pipeline:
    """内容类型无关的自动创作流水线"""

    def __init__(
        self,
        scraper: ScraperProtocol,        # 抓取策略
        selector: TopicSelectorProtocol,  # 选题策略
        agent_chain: list[BaseAgent],     # Agent 链（可替换）
        reviewer: ReviewerAgent,          # 评审+质量门
        publisher: PublisherProtocol,     # 发布策略
        quality_threshold: float = 6.0,   # 质量门槛
        max_rewrites: int = 2,            # 不达标最大重写轮数
        run_dir: Path = ...,              # 运行日志目录
    ): ...

    def run(self, topic: str | None = None) -> RunResult: ...
    def run_scheduled(self, interval_minutes: int) -> ScheduledRun: ...
```

### 关键设计决策

1. **Pipeline 不感知 Agent 内部逻辑** — 只知道 `BaseAgent.invoke(prompt)` 接口。新增短剧 Agent 链只需传入不同的 Agent 实例列表
2. **选题自动化** — `TopicSelectorProtocol` 接收热榜 JSON，调用 LLM 分析选最优，返回题材+主题。默认实现用现有的 `TopicAnalyzerAgent`
3. **质量门** — Reviewer 评分 < threshold 时，将评审意见传回 DraftWriter 重写，最多 `max_rewrites` 轮。所有轮次记录在 `RunResult.rewrite_history` 中
4. **异常隔离** — 每个阶段失败只影响当次运行，不会中断调度循环

## 知乎全自动发布器 (`automator_zhihu.py`)

### 流程

1. 打开 `zhuanlan.zhihu.com/write`
2. 检测登录状态（session 过期则提示重新登录，抛出 `LoginRequired`）
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
- 发布后 30 秒未跳转 → 检查当前页面 URL，若仍包含 `/write` 则超时失败
- Session 过期 → 抛出 `LoginRequired`，Pipeline 层捕获后记录并跳过本次发布

## CLI 命令

```
/auto [主题]        一次性全自动运行（不指定主题则 AI 自选）

/schedule start [N]h 启动定时调度（默认每 6 小时）
/schedule stop        停止调度
/schedule status      查看调度状态和下次运行时间
```

### 调度器设计

- 后台线程运行，不阻塞 CLI 交互
- 间隔可配置：命令参数或环境变量 `PIPELINE_INTERVAL_MINUTES`
- 每次运行追加到 `output/.pipeline/runs.jsonl`
- 调度状态持久化到 `output/.pipeline/schedule.json`，重启 CLI 后可恢复

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
    "create": {"status": "ok", "words": 3420, "duration_s": 45.2},
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

create 失败（LLM 错误/超时）
  ├─ 重试 3 次（沿用 BaseAgent 的重试机制）
  └─ 仍失败 → 本次运行终止

review 不达标（score < threshold）
  ├─ 第 1 轮：评审意见传回 DraftWriter 重写
  ├─ 第 2 轮：再次重写
  └─ 仍不达标 → 记录跳过，不发布

publish 失败
  ├─ 选择器失效 → 截图保存，记录详细错误
  ├─ Session 过期 → 标记需要重新登录
  └─ 其他错误 → 记录，不阻塞调度
```

**全局原则：任何单次运行失败不影响后续调度。**

## 文件变更清单

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `pipeline.py` | Pipeline 编排引擎 |
| 新增 | `automator_zhihu.py` | 知乎全自动发布器 |
| 新增 | `tests/test_pipeline.py` | Pipeline 集成测试 |
| 新增 | `tests/test_automator_zhihu.py` | 发布器单元测试 |
| 修改 | `cli.py` | 新增 `/auto`、`/schedule` 命令 |
| 修改 | `__init__.py` | 移除 `workspace_shims` 导入 |

## 测试策略

- **test_pipeline.py**: Mock scraper/LLM/publisher，验证编排逻辑（选题→创作→评审→重试→发布→跳过）
- **test_automator_zhihu.py**: 验证选择器策略、登录检测、发布按钮定位、确认弹窗处理（条件跳过，需要 playwright）
- **手动验证**: 首次全流程跑通后，检查 `output/.pipeline/` 运行日志完整性