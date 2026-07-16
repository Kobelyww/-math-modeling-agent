



# Claude Code & Hermes Agent 技术全解与 Agent 工程师学习路线

> 整合自 GitHub 官方仓库源码分析、Anthropic Cookbook、Claude Agent SDK、NousResearch Hermes Agent —— 系统性 Agent 技术文档

---

## 目录

**第一部分：Claude Code 技术架构全解**

- [1. 总览与设计哲学](#1-总览与设计哲学)
- [2. Agent Loop — 核心循环的完整实现](#2-agent-loop--核心循环的完整实现)
- [3. 工具系统 — 从 Schema 到执行的完整链路](#3-工具系统--从-schema-到执行的完整链路)
- [4. Sub-Agent 子代理系统](#4-sub-agent-子代理系统)
- [5. Hook 系统 — 生命周期拦截器](#5-hook-系统--生命周期拦截器)
- [6. 上下文管理 — Compaction 完整机制](#6-上下文管理--compaction-完整机制)
- [7. Memory 系统 — 跨会话知识持久化](#7-memory-系统--跨会话知识持久化)
- [8. 权限系统 — 多层防御架构](#8-权限系统--多层防御架构)
- [9. Claude Agent SDK — 构建自定义 Agent 的官方工具包](#9-claude-agent-sdk--构建自定义-agent-的官方工具包)
- [10. Agent 设计模式 — 五大经典模式与代码实现](#10-agent-设计模式--五大经典模式与代码实现)

**第二部分：Agent 工程师学习路线**

- [11. 五层能力模型](#11-五层能力模型)
- [12. 分层学习路线与时间线](#12-分层学习路线与时间线)
- [13. 关键技术深入指引](#13-关键技术深入指引)
- [14. 推荐资源全清单](#14-推荐资源全清单)

**第三部分：Hermes Agent 自进化机制深度分析**

- [15. 项目概述与核心哲学](#15-项目概述与核心哲学)
- [16. 自进化四层系统总架构](#16-自进化四层系统总架构)
- [17. Background Review — 自动后台审视的完整实现](#17-background-review--自动后台审视的完整实现)
- [18. Curator — 技能库周期性维护器](#18-curator--技能库周期性维护器)
- [19. Context Compressor — Hermes 的压缩策略](#19-context-compressor--hermes-的压缩策略)
- [20. Memory 与 Skill 双轨知识系统](#20-memory-与-skill-双轨知识系统)
- [21. Werewolf GEPA — 7 步文本进化管线](#21-werewolf-gepa--7-步文本进化管线)
- [22. Claude Code vs Hermes Agent 全面对比](#22-claude-code-vs-hermes-agent-全面对比)

**第四部分：工程实践与落地指南**

- [23. 架构映射——Claude/Hermes 概念到自研 Agent 的对照表](#23-架构映射claudehermes-概念到自研-agent-的对照表)
- [24. 典型故障模式与反模式（含 agent_app 案例）](#24-典型故障模式与反模式含-agent_app-案例)
- [25. 生产级 Agent 检查清单](#25-生产级-agent-检查清单)
- [26. MCP 生态与 Tool Search 落地路径](#26-mcp-生态与-tool-search-落地路径)
- [27. 多 Agent 编排模式选型决策树](#27-多-agent-编排模式选型决策树)
- [28. 评测、观测与成本治理](#28-评测观测与成本治理)
- [29. 2026 架构趋势与演进方向](#29-2026-架构趋势与演进方向)

**第五部分：全章节实现细节深度手册**

- [30. §1–§2 Agent Loop 源码级实现](#30-§1§2-agent-loop-源码级实现)
- [31. §3 工具系统完整实现](#31-§3-工具系统完整实现)
- [32. §4 Sub-Agent 子代理实现](#32-§4-sub-agent-子代理实现)
- [33. §5 Hook 系统落地实现](#33-§5-hook-系统落地实现)
- [34. §6 上下文压缩实现](#34-§6-上下文压缩实现)
- [35. §7 Memory 与 LTM 实现](#35-§7-memory-与-ltm-实现)
- [36. §8 权限与安全实现](#36-§8-权限与安全实现)
- [37. §9–§10 SDK 与设计模式实现映射](#37-§9§10-sdk-与设计模式实现映射)
- [38. §10-A LangGraph 与 agent_app Orchestrator](#38-§10-a-langgraph-与-agent_app-orchestrator)
- [39. §11–§14 学习路线配套 Lab](#39-§11§14-学习路线配套-lab)
- [40. §15–§22 Hermes 与 GEPA 源码实现](#40-§15§22-hermes-与-gepa-源码实现)
- [41. §23–§29 工程实践代码索引](#41-§23§29-工程实践代码索引)
- [42. 端到端时序：一次 solve_sequential 全链路](#42-端到端时序一次-solve_sequential-全链路)
- [43. 各章实现细节速查表](#43-各章实现细节速查表one-page)

---

# 第一部分：Claude Code 技术架构全解

## 1. 总览与设计哲学

### 1.1 产品定位

Claude Code 是 Anthropic 出品的**终端原生 AI 编程助手**。它的核心是一个**工具增强型 LLM Agent**——通过 Agent Loop 机制，让 LLM 在"推理 → 工具调用 → 观察结果 → 再推理"的循环中自主完成软件工程任务。

- **仓库**: [github.com/anthropics/claude-code](https://github.com/anthropics/claude-code) (125K+ Stars, 20K+ Forks)
- **官方文档**: [code.claude.com/docs](https://code.claude.com/docs/en/overview)
- **Agent SDK (Python)**: [github.com/anthropics/claude-agent-sdk-python](https://github.com/anthropics/claude-agent-sdk-python)
- **Agent SDK (TypeScript)**: [github.com/anthropics/claude-agent-sdk-typescript](https://github.com/anthropics/claude-agent-sdk-typescript)
- **Cookbook**: [github.com/anthropics/claude-cookbooks](https://github.com/anthropics/claude-cookbooks)

### 1.2 四层架构

```
┌──────────────────────────────────────────────────────────┐
│              表现层 (Presentation)                        │
│  CLI (prompt_toolkit) · IDE (VS Code / JetBrains) ·      │
│  Web App (claude.ai/code) · Desktop App                  │
└──────────────────────────┬───────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────┐
│              编排层 (Orchestration)                       │
│  Agent Loop · HookManager · PermissionManager ·          │
│  ContextManager (Compaction) · SkillManager · PlanMode · │
│  MemoryManager · SubAgentSpawner · CronScheduler         │
└──────────────────────────┬───────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────┐
│              工具层 (Tool Execution)                      │
│  Read · Write · Edit · Bash · Agent · Grep · Glob ·     │
│  WebFetch · WebSearch · Task · Cron · Monitor ·         │
│  AskUserQuestion · NotebookEdit · PushNotification ·    │
│  MCP 协议 (外部工具服务器)                                 │
└──────────────────────────┬───────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────┐
│              模型层 (Model)                               │
│  Opus 4.7 (旗舰推理) · Sonnet 4.6 (平衡) · Haiku 4.5    │
│  1M Token Context · Prompt Caching (5min TTL) ·         │
│  Thinking/Extended Thinking · Task Budgets               │
└──────────────────────────────────────────────────────────┘
```

### 1.3 五大设计原则

| 原则 | 说明 | 工程体现 |
|------|------|---------|
| **Tool-First** | 所有副作用通过工具产生，Agent 不直接访问系统 | 每个工具有严格 JSON Schema，Hook 在工具边界拦截 |
| **Human-in-the-Loop** | 高风险操作需用户确认 | 权限系统三级决策：allow/deny/ask |
| **Context is King** | 系统提示词决定 Agent 行为上限 | CLAUDE.md + Memory + git status + 目录结构注入 |
| **Stateless Shell, Stateful Conversation** | Shell 环境无状态，对话上下文保留全部历史 | 每次 Bash 调用是独立进程；对话历史全量保留 |
| **Graceful Degradation** | 异常情况优雅降级 | Compaction 防上下文溢出；Hook crash 不阻塞 Agent |

### 1.4 实现细节补充

**会话状态存放位置**（Claude Code 推断 vs agent_app 显式）：

| 状态类型 | Claude Code | agent_app |
|---------|------------|-----------|
| 对话历史 | 全量 messages API | `SharedMemory._messages` |
| 压缩摘要 | Compaction 消息 | `compressed_prefix` |
| 跨会话 | MEMORY.md + Session | SQLite LTM + `save_state` JSON |
| 工具注册 | 内置 + MCP | `_TOOL_EXECUTORS` dict |
| 费用 | usage 回调 | `extract_token_usage` + `TokenBudgetCondition` |

**启动一次求解的最小调用链**：`load_settings()` → `Orchestrator(settings)` → `solve_sequential(q)` → `_finalize_workflow` → `output/`。

深度实现见 **§30**。

---

## 2. Agent Loop — 核心循环的完整实现

### 2.1 完整循环伪代码

```
function run_conversation(user_message, system_prompt, conversation_history, max_iterations=90):
    messages = conversation_history or []
    messages.insert(0, {"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_message})

    iteration_budget = IterationBudget(total=max_iterations)
    api_call_count = 0
    budget_grace_call = True  # 允许超出预算一次完成

    while (api_call_count < max_iterations AND iteration_budget.remaining > 0)
          OR budget_grace_call:

        if interrupt_requested:
            break

        // 阶段 A: 上下文管理
        estimated_tokens = estimate_tokens(messages + tools)
        if estimated_tokens > compaction_threshold:
            messages = compact_context(messages)  // 见第 6 章

        // 阶段 B: 模型推理
        apply_anthropic_cache_control(messages)  // 标记可缓存前缀
        response = api.chat.completions.create(
            model=model,
            messages=messages,
            tools=tool_schemas,
            max_tokens=max_output_tokens,
            temperature=temperature,
        )

        // 阶段 C: 成本追踪
        usage_cost = estimate_usage_cost(response.usage)
        total_cost_usd += usage_cost

        // 阶段 D: 响应分流
        if response 是纯文本:
            budget_grace_call = False
            if has_incomplete_scratchpad(response.content):
                continue  // 推理未完成，再给一轮
            return {"final_response": response.content, "messages": messages}

        // 阶段 E: 工具调用处理
        for tool_call in response.tool_calls:
            // E1: PreToolUse Hook 拦截
            hook_result = dispatch_hooks("PreToolUse", tool_call)
            if hook_result == "block":
                messages.append(tool_blocked_message(tool_call, hook_result.reason))
                continue
            if hook_result == "modify":
                tool_call.input = hook_result.modified_input

            // E2: 权限检查
            permission = check_permission(tool_call.name, tool_call.input)
            if permission == "deny":
                messages.append(tool_denied_message(tool_call))
                continue
            if permission == "ask":
                user_decision = prompt_user(tool_call)
                if user_decision == "deny":
                    continue

            // E3: 实际执行
            try:
                result = execute_tool(tool_call.name, tool_call.input)
            except Exception as e:
                result = {"error": str(e)}

            // E4: PostToolUse Hook 拦截
            hook_result = dispatch_hooks("PostToolUse", tool_call, result)
            if hook_result == "modify":
                result = hook_result.modified_output

            // E5: 结果注入上下文
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result)
            })

        api_call_count += 1
        iteration_budget.spend(len(response.tool_calls))

    return {"final_response": "Iteration budget exhausted", "messages": messages}
```

### 2.2 迭代预算 (IterationBudget)

```python
class IterationBudget:
    """
    每次工具调用消耗 1 个单位预算。
    max_iterations 默认为 90。

    _budget_grace_call 机制:
    - 当预算耗尽但 Agent 正在完成最终输出时，允许额外一次 API 调用
    - 这防止 Agent 在"快完成了"的时刻被硬截断
    - 只给一次 grace call，用完后强制终止
    """
    def __init__(self, total: int):
        self.total = total
        self.remaining = total
        self._grace_given = False

    def spend(self, count: int = 1):
        self.remaining -= count
```

### 2.3 Prompt 组装——系统提示词的构成

系统提示词是 Agent 行为的核心控制器。它在每次会话首次调用 API 前组装完成，后续轮次复用缓存的版本：

```
系统提示词 =
  BASE_INSTRUCTIONS (角色定义 + 行为约束)
  + CLAUDE.md 内容 (项目级指令, 从当前目录和父目录读取)
  + MEMORY.md 索引 (用户记忆目录, 约 200 行限制)
  + 工具定义列表 (JSON Schema 格式, 约 15-25 个工具)
  + git status 快照 (当前仓库状态)
  + 目录结构摘要 (当前工作目录)
  + 平台信息 (OS, Shell, 日期)
  + Skills 提示词 (当前加载的技能)
```

**Prompt Caching 优化**：
- 系统提示词的**静态部分**（工具定义、BASE_INSTRUCTIONS）被标记为可缓存
- `cache_control: {"type": "ephemeral"}` 标记在最后一条 system 消息上
- TTL 5 分钟，这期间相同前缀的请求复用 KV-cache
- Compaction 改变历史 → 缓存前缀变化 → 缓存失效，需重新计算

### 2.4 中断机制

```python
# Agent Loop 每轮迭代检查此标志
agent._interrupt_requested: bool = False

# 可由以下途径设置:
# 1. 用户按 Ctrl+C
# 2. Hook 返回 continue_=False
# 3. 权限系统 deny
# 4. PostToolUseFailure Hook
```

### 2.5 错误处理策略

```
API 错误分类 (classify_api_error):
├── 可重试错误 (retryable):
│   ├── 429 Rate Limit → 指数退避 + 抖动 (jittered_backoff)
│   ├── 503 Service Unavailable → 重试
│   └── 网络超时 → 重试
├── 上下文溢出 (context_overflow):
│   └── 触发 Compaction → 压缩后重试
├── 认证错误 (401/403):
│   └── 不重试, 提示用户检查 API key
└── 模型过载 (overloaded):
    └── 退避后重试, 或降级到备用模型 (fallback_model)

降级路径 (FailoverReason):
  主模型不可用 → 尝试 fallback_model (如 Sonnet → Haiku)
  API 模式不可用 → 尝试备用 API mode
```

### 2.6 实现细节补充

**agent_app 中一轮工具调用的消息序列**（OpenAI 兼容格式）：

```
[SystemMessage: system_prompt]
[HumanMessage: user_prompt]
[AIMessage: content="", tool_calls=[{name, args, id}]]
[ToolMessage: tool_call_id, content="Written: solve.py"]
[AIMessage: content="代码已保存并验证..."]
```

**轮次上限**：编程 Agent `_MAX_TOOL_ROUNDS["programmer"]=6`（write + pip + python_exec 多轮）；协调者不应走工具循环（§24 F4）。

**流式与工具互斥时的统一策略**：`_safe_stream` 在有工具时改走 `invoke_with_tools`，再按 20 字符块回调 `on_token`——牺牲工具阶段 token 级流式，保证工具必执行。

完整状态机与 Orchestrator 映射见 **§30**。

---

## 3. 工具系统 — 从 Schema 到执行的完整链路

### 3.1 工具调用的完整数据流

```
┌─────────────────────────────────────────────────────────┐
│ 1. 模型输出 ToolUseBlock                                │
│    {id, name, input: {param1: val1, ...}}               │
│                                                         │
│ 2. HookManager.dispatch("PreToolUse", tool_call)        │
│    ├── 匹配 matcher → 找到注册的 Hook 回调               │
│    ├── 串行执行所有匹配的 Hook                            │
│    └── 返回: {decision: "allow"|"block"|"modify"}       │
│                                                         │
│ 3. PermissionManager.check(tool_name, tool_input)       │
│    ├── 检查 settings.local.json                          │
│    ├── 检查 settings.json (项目级)                       │
│    ├── 检查全局 settings                                 │
│    └── 返回: "allow"|"deny"|"ask"                       │
│                                                         │
│ 4. ToolExecutor.execute(tool_name, tool_input)          │
│    ├── Bash: subprocess.run(command, timeout=...)       │
│    ├── Read: open(file).read()                          │
│    ├── Edit: file.replace(old_string, new_string)       │
│    ├── Agent: spawn_subagent(prompt, options)           │
│    ├── WebFetch: httpx.get(url) + LLM 处理              │
│    └── MCP: jsonrpc_client.call_tool(name, args)        │
│                                                         │
│ 5. HookManager.dispatch("PostToolUse", tool_call, result)│
│    └── 可修改 result 再传递给 Agent                       │
│                                                         │
│ 6. 结果序列化为 JSON, 作为 tool 角色消息注入对话           │
└─────────────────────────────────────────────────────────┘
```

### 3.2 工具 Schema 定义规范

每个工具遵循 OpenAI/Anthropic Function Calling 格式：

```json
{
    "name": "Bash",
    "description": "Executes a given bash command...",
    "parameters": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The command to execute"
            },
            "description": {
                "type": "string",
                "description": "Clear, concise description of what this command does"
            },
            "timeout": {
                "type": "number",
                "minimum": 0,
                "maximum": 600000,
                "description": "Optional timeout in milliseconds"
            },
            "run_in_background": {
                "type": "boolean",
                "description": "Set to true to run in the background"
            }
        },
        "required": ["command"]
    }
}
```

### 3.3 核心工具的实现要点

| 工具 | 实现原理 | 关键约束 |
|------|---------|---------|
| **Read** | `open(path).read()` + 行号前缀格式化 | 支持图片/PDF/Jupyter；PDF 最多 20 页/次 |
| **Write** | `open(path, "w").write(content)` | 必须先 Read 确认文件存在或有意创建 |
| **Edit** | `str.replace(old_string, new_string)` | old_string 必须在文件中唯一；支持 `replace_all` |
| **Bash** | `subprocess.run(cmd, shell=True, cwd=...)` | 默认超时 2 分钟，最长 10 分钟；CWD 持久但 shell 状态不持久 |
| **Agent** | 启动独立 AIAgent 实例 | 前台/后台/Worktree 三种模式；模型独立可选 |
| **WebFetch** | `httpx.get(url)` → HTML→Markdown → LLM 处理 | 15 分钟缓存；自动 HTTP→HTTPS 升级 |
| **Task** | 异步任务管理 | 支持依赖关系 (blocks/blockedBy) |
| **Cron** | 标准 5 段 cron 表达式 | 最长 7 天自动过期 |
| **Monitor** | 子进程 stdout 流式监听 | 每行是一个事件通知 |

### 3.4 Edit 工具——为什么用字符串替换而非行号

这是 Claude Code 最精妙的设计之一：

```
行号编辑的问题：
  文件: 100 行
  第 1 个 Edit: "在 L50 后插入 3 行" → 文件变为 103 行
  第 2 个 Edit: "修改 L80" → 但 L80 现在是之前的 L77！
  → 需要额外的行号追踪状态

精确字符串替换的优势：
  old_string = "def login(user, pass):\n    # TODO: add validation\n    return db.query(user)"
  new_string = "def login(user, pass):\n    validate_credentials(user, pass)\n    return db.query(user)"

  → old_string 在文件中的位置不依赖行号
  → 多个 Edit 之间完全独立，无偏移问题
  → 如果 old_string 不唯一→报错，要求 Agent 提供更多上下文使其唯一
```

### 3.5 Bash 工具的安全机制

```python
# Bash 命令执行的安全层级：
1. 命令通过 Hook PreToolUse 检查（用户可自定义规则）
2. 权限系统检查（allow/deny/ask）
3. 沙箱模式（如果启用 DangerouslyDisableSandbox 则跳过）
4. 超时控制（默认 2min，最长 10min）
5. 工作目录隔离（在项目目录下执行）

# 危险模式自动检测 (示例 Hook)：
DANGEROUS_PATTERNS = [
    r'rm\s+-rf\s+/',           # 删除根目录
    r'git\s+push\s+--force',   # 强制推送
    r'>\s+/dev/sda',           # 写入磁盘设备
    r'chmod\s+777\s+/',        # 权限过度开放
    r'DROP\s+(TABLE|DATABASE)', # SQL 破坏性操作
]
```

### 3.6 实现细节补充

**agent_app 工具注册完整清单**（`orchestrator.__init__`）：

```python
_tool_map = {
    "python_exec", "pip_install", "read_csv_info",
    "latex_template", "latex_compile", "latex_render_math",
    "calculator", "current_time", "save_note", "read_note", "list_notes",
    "nature_viz_template", "model_reference", "writing_rules",
    "search_arxiv", "search_semantic_scholar", "search_crossref", "fetch_paper_to_kb",
    "read_file", "search_files", "search_content", "list_directory",
    "web_search", "web_fetch", "write_file", "spawn_subagent",
}
```

**按 Agent 分配**（节选）：

| Agent | 工具 |
|-------|------|
| modeler | write_file, save_note, spawn_subagent, web_search, model_reference |
| programmer | write_file, python_exec, pip_install, read_file, search_content |
| writer | write_file, latex_compile, latex_template, writing_rules |
| reviewer | write_file, read_file, web_search（只读+评审） |

**MCP 扩展点**：新增 MCP Server 时，将其 tools/list 转为 LangChain `@tool` 并 `register_tool_executor`，无需改 Agent Loop。

沙箱、write_file、latex 源码见 **§31**。

---

## 4. Sub-Agent 子代理系统

### 4.1 类型体系与能力边界

```
主 Agent (完整工具集 + 全上下文 + Memory 访问)
    │
    ├── Explore Agent      工具: 全部 EXCEPT Edit/Write/NotebookEdit/Agent/ExitPlanMode
    │                      用途: 快速只读代码搜索
    │                      模型: 默认继承主 Agent
    │
    ├── Plan Agent         工具: 全部 EXCEPT Edit/Write/NotebookEdit/Agent/ExitPlanMode
    │                      用途: 软件架构设计,输出方案（不写代码）
    │                      模型: 默认继承
    │
    ├── general-purpose    工具: 全部 (*)
    │                      用途: 通用复杂多步任务
    │                      模型: 可独立指定
    │
    ├── claude-code-guide  工具: Bash/Read/WebFetch/WebSearch (受限4个)
    │                      用途: 回答 Claude Code 自身用法问题
    │                      模型: 默认继承
    │
    └── statusline-setup   工具: Read/Edit (仅2个)
                           用途: 配置状态行设置
                           模型: 默认继承
```

### 4.2 三种执行模式的技术实现

| 模式 | 参数 | 进程模型 | 上下文传递 |
|------|------|---------|----------|
| **前台** | 默认 | 同步阻塞，等待子代理完成 | prompt 参数 → 新会话第一条用户消息 |
| **后台** | `run_in_background: true` | 独立线程，完成时 task-notification | 同上 + 输出写入文件 |
| **隔离** | `isolation: "worktree"` | git worktree 中执行 | 同上 + CWD 切换到 worktree 目录 |

### 4.3 Worktree 隔离的完整流程

```
Step 1: 创建 worktree
  $ git worktree add .claude/worktrees/<uuid> <base-ref>
  分支策略:
    - worktree.baseRef = "fresh"  → 从 origin/main 分支
    - worktree.baseRef = "head"   → 从当前 HEAD 分支

Step 2: 子代理在 worktree 中执行
  CWD = .claude/worktrees/<uuid>/
  所有 Read/Write/Edit/Bash 在此目录操作
  主工作区完全不受影响

Step 3: 清理
  子代理无文件变更:
    → git worktree remove --force
    → git branch -D <worktree-branch>
  子代理有文件变更:
    → 保留 worktree
    → 返回 {path, branch} 给主 Agent
    → 主 Agent 可检查变更、合并或丢弃
```

### 4.4 子代理 Prompt 的自包含原则

主 Agent 必须在 `prompt` 参数中提供**完整的上下文**。子代理的初始消息就是这条 prompt，它不知道主对话中发生过什么：

```
✅ 正确写法 (自包含):
"""
This branch adds OAuth support. We've already:
- Added the OAuth config to settings.py (line 45-60)
- Created the callback endpoint in auth.py

Now audit the callback endpoint for timing vulnerabilities.
Focus on: nonce validation window, state parameter checks, PKCE flow.
Report under 200 words with specific line references.
"""

❌ 错误写法 (依赖外部上下文):
"""
Based on your findings, fix the bug.
"""  ← 子代理不知道"findings"是什么，也不知道"bug"是什么
```

### 4.5 子代理的结果验证原则

子代理返回的是**它的声称**，不是事实。主 Agent 不应直接信任：

```python
# 验证流程
agent_result = spawn_subagent("code-reviewer", prompt="Review auth.py")
# agent_result.text = "Found SQL injection on line 45. Fixed."

# 必须验证
actual_file = Read("auth.py", line=45)
if "fixed" in agent_result.text and not evidence_in_file:
    # 子代理声称修复了但实际没有 → 需要进一步调查
```

### 4.6 实现细节补充

`agent_app/subagent.py` 中 `_run_subagent` 使用 LangChain `create_agent(model, tools, system_prompt)`，与 Claude SDK `AgentDefinition` 同构。结果截断：

```python
result = normalize_llm_content(last_message.content)
if len(result) > defn.max_result_chars:
    result = result[: defn.max_result_chars - 20] + "\n...[truncated]"
```

`solve_explore` 阶段 1 调用 `spawn_parallel([("explore", task), ("research", task)], llm)`，两路结果拼入 `explore_bundle` 键 `探索与调研摘要`。

完整 SubAgentDef 表与并行流程见 **§32**。

---

## 5. Hook 系统 — 生命周期拦截器

### 5.1 完整事件矩阵

| 事件 | 触发时机 | 输入关键字段 | 可返回的决策 |
|------|---------|------------|------------|
| `PreToolUse` | 工具调用前 | `tool_name`, `tool_input`, `tool_use_id`, `agent_id?` | deny/allow/ask + modified_input |
| `PostToolUse` | 工具调用成功后 | 上述 + `tool_response` | systemMessage, additionalContext |
| `PostToolUseFailure` | 工具执行失败 | 上述 + `error`, `is_interrupt?` | continue_: False |
| `UserPromptSubmit` | 用户提交提示词 | `prompt` | additionalContext |
| `Stop` | Agent 会话结束 | `stop_hook_active` | 无（仅观察） |
| `SubagentStart` | 子代理启动 | `agent_id`, `agent_type` | additionalContext |
| `SubagentStop` | 子代理停止 | `agent_id`, `agent_type`, `agent_transcript_path` | 无 |
| `PreCompact` | 上下文压缩前 | `trigger` ("manual"/"auto"), `custom_instructions?` | 抢救性 backup |
| `Notification` | 通知事件 | `message`, `notification_type`, `title?` | 无 |
| `PermissionRequest` | 权限请求时 | `tool_name`, `tool_input`, `permission_suggestions?` | allow/deny |

### 5.2 HookManager 内部架构（推断实现）

```python
class HookManager:
    """管理所有已注册的 Hook，在事件触发时分发执行"""

    def __init__(self, config: dict):
        self._hooks: dict[HookEvent, list[HookEntry]] = {}
        self._load_from_config(config)

    def _load_from_config(self, config: dict):
        """从 settings.json 加载 Hook 配置"""
        for event_name, hook_list in config.get("hooks", {}).items():
            for entry in hook_list:
                matcher = re.compile(entry.get("matcher", ".*"))
                command = entry["command"]
                timeout = entry.get("timeout", 5000)  # ms
                self._hooks.setdefault(event_name, []).append(
                    HookEntry(matcher=matcher, command=command, timeout=timeout)
                )

    async def dispatch(
        self, event: HookEvent, context: HookContext
    ) -> HookResult:
        """串行执行所有匹配的 Hook"""
        modified_context = context
        for entry in self._hooks.get(event, []):
            if entry.matcher.match(context.tool_name):
                result = await self._execute_hook(entry, modified_context)
                if result.decision == "block":
                    return result  # 短路：后续 Hook 不执行
                if result.decision == "modify":
                    modified_context = result.modified_context  # 管道传递
        return HookResult(decision="allow", context=modified_context)

    async def _execute_hook(
        self, entry: HookEntry, context: HookContext
    ) -> HookResult:
        """启子进程执行 Hook 命令，stdin→JSON, stdout→解析决策"""
        proc = await asyncio.create_subprocess_exec(
            entry.command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=json.dumps(context).encode()),
                timeout=entry.timeout / 1000,
            )
            return self._parse_hook_output(stdout)
        except asyncio.TimeoutError:
            return HookResult(decision="allow")  # fail-open
        except Exception:
            return HookResult(decision="allow")  # fail-open
```

### 5.3 典型 Hook 实战

**场景 1：阻止危险命令**

```python
async def safety_hook(input_data, tool_use_id, context):
    if input_data["tool_name"] != "Bash":
        return {}
    cmd = input_data["tool_input"].get("command", "")
    blocked = ["rm -rf /", "git push --force origin main", "> /dev/sda"]
    for pattern in blocked:
        if pattern in cmd:
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": f"Blocked: {pattern}",
                }
            }
    return {}
```

**场景 2：密钥泄露扫描**

```python
import re
SECRET_PATTERNS = [
    r'sk-[a-zA-Z0-9]{20,}',       # OpenAI/Anthropic API key
    r'AKIA[A-Z0-9]{16}',            # AWS Access Key
    r'ghp_[a-zA-Z0-9]{36}',         # GitHub Personal Access Token
    r'-----BEGIN (RSA|EC) PRIVATE KEY-----',  # Private Key
]

async def secrets_hook(input_data, tool_use_id, context):
    if input_data["tool_name"] not in ("Write", "Edit"):
        return {}
    content = str(input_data["tool_input"])
    for pattern in SECRET_PATTERNS:
        if re.search(pattern, content):
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": "Secret/API key detected in output",
                }
            }
    return {}
```

**场景 3：注入持续上下文**

```python
async def context_hook(input_data, tool_use_id, context):
    """每次用户输入后追加企业内部规范"""
    return {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": (
                "GLOBAL RULES (apply to all tasks):\n"
                "- All code must pass `pre-commit run --all-files`\n"
                "- Never commit to main directly; always use feature branches\n"
                "- Database migrations require 2-person review\n"
            ),
        }
    }
```

---

## 6. 上下文管理 — Compaction 完整机制

### 6.1 压缩算法

```
function compact_context(messages, max_output_tokens):
    estimated_total = estimate_tokens(messages)
    if estimated_total <= compaction_threshold:
        return messages  // 无需压缩

    // 1. 确定 head (不可压缩部分)
    head = [
        messages[0],           // System Prompt
        ...前几条用户消息       // 保持最初意图清晰
    ]

    // 2. 确定 tail (必须保留部分)
    tail_tokens = 0
    tail_budget = max_output_tokens * 0.30  // 保留 30% 给最近消息
    tail = []
    for msg in reversed(messages):
        tail_tokens += estimate_single_message_tokens(msg)
        if tail_tokens > tail_budget:
            break
        tail.insert(0, msg)

    // 3. 中间部分 → 压缩
    middle = messages[len(head) : -len(tail)]
    summary_budget = len(middle) * 0.20  // 摘要预算为被压缩内容的 20%
    summary = generate_summary(middle, max_tokens=summary_budget)

    // 4. 组装
    return head + [summary_message(summary)] + tail
```

### 6.2 分层保留策略（实战视角）

```
优先级 CRITICAL — 不可丢失:
├── 用户原始指令: "帮我把登录改为 OAuth2.0 认证"
├── 已完成的代码变更: "修改了 auth.py L45-120，添加了 OAuth 配置"
├── 用户给予的反馈: "不要用 JWT，用 session-based 认证"
├── 未完成任务列表: "还需要更新前端回调页面"
└── Memory 写入记录: "已保存用户偏好: 偏好 session-based 认证"

优先级 HIGH — 尽量保留:
├── 发现的错误和调试结论
├── 被修改的文件路径列表
├── 关键函数签名变化
└── 用户的行为期望

优先级 MEDIUM — 精炼:
├── 探索性搜索过程: [Grep 15 files] → 保留 "确认了 login() 的 15 个调用点"
├── 多轮迭代的中间态: 保留最终方案，丢弃中间尝试
└── 工具调用的详细参数

优先级 LOW — 丢弃:
├── 冗余的工具输出 (重复的 ls, git status)
├── 被后续操作覆盖的临时中间态
└── Agent 的内部反思和计划调整
```

### 6.3 多次压缩的信息退化

```
会话长度 (以窗口倍数计):
1x ───── 100% 保真度 (无压缩)
2x ───── ~80% (首次压缩, 丢失中间推理细节)
3x ───── ~60% (二次压缩, 摘要的摘要, 丢失部分决策原因)
4x ───── ~40% (三次压缩, 早期指令可能退化为模糊描述)
5x ───── ~25% (四次压缩, 只有最重要的信息幸存)

缓解策略:
├── 及时将关键决策写入 Memory (Memory 不随压缩退化)
├── 阶段性 git commit (代码变更是比任何摘要都可靠的记录)
├── 长任务中主动总结并从新起点继续
└── 使用 CLAUDE.md 存储持久规则
```

### 6.4 Compaction 与 Prompt Caching 的冲突

```
场景: 连续对话中触发压缩
  0min: API 调用 #1 — 首次发送完整系统提示词
        → Anthropic 缓存前缀 (TTL 5min)
  2min: API 调用 #2 — 命中缓存，延迟 <200ms
  4min: API 调用 #3 — 命中缓存
  5min: API 调用 #4 — 缓存过期，重新计算
  7min: 触发 Compaction — 上下文内容变化
        → API 调用 #5 的请求体不同
        → 前缀缓存完全失效
        → 该次调用延迟 +~2s，成本 +~30%

优化策略:
  - 避免不必要的 Compaction (预剪枝工具输出比 LLM 摘要更便宜)
  - 在空闲期主动触发 Compaction (让压缩后的新前缀尽快被缓存)
  - 对关键信息写入 Memory (减少对对话历史的依赖)
```

### 6.5 实现细节补充

`agent_app/memory/short_term.py` 的 `SharedMemory.compress_older()` 将超出 `recent_window_size`（默认 5）的消息移出队列，文本交给 `ContextCompressor`：

```python
# hierarchical 增量合并伪代码
if existing_summary:
    prompt = COMPRESS_PROMPT_INCREMENTAL.format(
        existing_summary=existing_summary, new_messages=old_text)
else:
    prompt = COMPRESS_PROMPT_FIRST.format(messages=old_text)
summary = llm.invoke(prompt)
stm.set_compressed_prefix(summary)
```

**与下游 Agent 的配合**：有 `extra_contexts={"建模方案": ...}` 时，`_get_stm_context(..., compressed_only=True)` 避免 STM 与 extra 重复——对应 Claude「不要把同一文件内容注入两次」。

见 **§34**。

---

## 7. Memory 系统 — 跨会话知识持久化

### 7.1 完整数据流

```
写入:
  会话中 Agent 判断有值得留存的信息
      │
      ├── Step 1: Write( memory/<name>.md, frontmatter + 正文 )
      │     格式: YAML frontmatter (name, description, type) + Markdown 正文
      │     类型: user | feedback | project | reference
      │
      └── Step 2: Edit( MEMORY.md, 追加一行索引 )
            格式: - [Title](file.md) — one-line hook (约 150 字符)
            约束: 索引上限 200 行

读取:
  新会话启动
      │
      ├── Step 1: 自动加载 MEMORY.md 到系统提示词
      │     (仅索引, Agent 看到所有记忆的一行摘要)
      │
      ├── Step 2: Agent 根据任务相关性判断
      │     依据: description 字段 + 当前任务
      │
      └── Step 3: Read 具体 .md 文件正文
            仅在确定相关后才加载, 避免上下文浪费
```

### 7.2 写入决策树（Agent 视角）

```
遇到新信息
    │
    ├── 是代码模式/架构/文件路径? → 不写 (可从当前项目文件推导)
    ├── git log/git blame 已有?   → 不写 (git 是权威源)
    ├── CLAUDE.md 已有?           → 不写 (已有文档)
    ├── 仅当前任务相关?            → 用 Plan/Task (非跨会话)
    ├── 当前会话临时状态?          → 不写
    │
    └── 跨会话有价值? → 写入 Memory
          ├── 用户角色/偏好/技能水平 → type: user
          ├── 行为纠正或确认       → type: feedback
          ├── 项目决策/约束/动机   → type: project
          └── 外部系统位置指针     → type: reference
```

### 7.3 使用前强制验证

```
约束: "记忆是快照, 不是实时事实" — Agent 必须验证

验证流程:
  memory 提到了文件路径 X:
    → Bash: ls X 或 Read: X → 文件存在? → 是 → 使用
                                        → 否 → 更新或删除记忆
  memory 提到了函数名 Y:
    → Grep: "def Y" → 函数存在? → 是 → 使用
                                → 否 → 更新或删除记忆
  memory 提到了配置项 Z:
    → Read: 配置文件 → Z 存在? → 是 → 使用
                               → 否 → 更新或删除记忆
```

### 7.4 [[双向链接]] 的实现细节

```markdown
---
name: auth-rewrite
description: OAuth 2.0 迁移 — 合规驱动, 截止 Q3
metadata:
  type: project
---

认证中间件重写，由法律部门合规审计驱动。
约束: 不能使用自签名证书，必须使用公司 CA。

相关:
- [[no-mock-tests]]  ← 测试约束
- [[team-contacts]]  ← 如果没有此文件, 标记为"未来应创建"
- [[pipeline-bugs]]  ← 管道相关的 bug 跟踪
```

### 7.5 与其他持久化机制的边界

| 机制 | 合适的内容 | 为什么不用 Memory |
|------|---------|-----------------|
| **Plan** | 当前实现方案的步骤 | 一次性的, 实现完即过时 |
| **Task** | 进度追踪 (做到第几步了) | 临时状态, 完成后无需保留 |
| **Cron** | 定时任务定义 | 有独立的调度系统 |
| **CLAUDE.md** | 项目通用的代码规范 | 属于项目而非特定上下文 |
| **git commit** | 代码变更 | git 是代码历史的唯一权威源 |

### 7.6 实现细节补充

LTM 写入示例（`memory/long_term.py`）：

```python
conn.execute(
    "INSERT INTO knowledge (content, type, scope, importance, created_at) VALUES (?,?,?,?,?)",
    (content, "fact", "/project/mcm", 0.8, iso_now),
)
# FTS5 同步索引 content 字段
```

`MemoryManager.archive_solve(question, synthesis)` 在 `_maybe_archive` 中调用，将整次求解摘要写入 LTM，供下次 `recall(question)` 注入 RAG 上下文。

Skill 更新路径：`skills/registry.py` 注册 → `resolve_agent_skills` 按 task 匹配 → 注入 `<<SKILL_CONTEXT>>`；Hermes 式自动 patch 见 **§40.7**。

---

## 8. 权限系统 — 多层防御架构

### 8.1 完整决策链路

```
工具调用请求
    │
    ▼
[Layer 1: Hook 拦截]
    所有 PreToolUse Hook 串行执行
    任一返回 deny → 终止, 返回原因
    └── allow → 继续
    │
    ▼
[Layer 2: 规则匹配]
    ├── settings.local.json  → 最高优先级
    ├── settings.json (项目级)
    └── 用户全局 settings
    匹配到 allow 规则 → 直接执行
    匹配到 deny 规则  → 终止
    未匹配           → 继续
    │
    ▼
[Layer 3: 权限模式评估]
    ├── bypassPermissions → 跳过确认 (高风险)
    ├── acceptEdits      → 文件编辑自动允许
    ├── plan             → 只读, 不执行
    ├── default          → 标准确认
    └── auto             → 全自动
    │
    ▼
[Layer 4: 用户确认] (如果 mode=default 且未匹配规则)
    弹窗展示: "Claude wants to run: <command>"
    用户选择: Allow / Deny / Allow All
```

### 8.2 权限模式决策指南

| 场景 | 推荐模式 | 原因 |
|------|---------|------|
| 日常开发 | `default` | 安全与效率平衡 |
| 代码重构 (大量文件变更) | `acceptEdits` | 减少确认弹窗, 但仍确认 shell |
| 安全审查 | `plan` | 只看不改 |
| CI/CD 自动化 | `auto` + 严格 Hook | 无人值守场景 |

---

## 9. Claude Agent SDK — 构建自定义 Agent 的官方工具包

### 9.1 SDK 架构

```
claude_agent_sdk/
├── query.py              ← query() 高层函数 (Agent Loop 封装)
├── client.py             ← ClaudeSDKClient (会话管理, 状态持久化)
├── types.py              ← 数据模型
│   ├── ClaudeAgentOptions   ← 全局配置
│   ├── AgentDefinition      ← 子代理定义
│   ├── HookInput/Output     ← Hook 协议类型
│   ├── PermissionResult     ← 权限决策类型
│   ├── Message types        ← 消息流类型 (AssistantMessage, ResultMessage...)
│   ├── ToolPermissionContext← 权限上下文
│   ├── PermissionUpdate     ← 动态权限更新
│   └── SystemPromptPreset   ← 系统提示词预设
└── _internal/            ← 内部实现 (CLI 通信, 进程管理)
```

### 9.2 完整 Agent 示例

```python
import anyio
from claude_agent_sdk import (
    query, ClaudeAgentOptions, AgentDefinition,
    AssistantMessage, TextBlock, ResultMessage, HookMatcher,
)

# 自定义 Hook
async def deny_force_push(input_data, tool_use_id, context):
    if input_data["tool_name"] != "Bash":
        return {}
    if "git push --force" in input_data["tool_input"].get("command", ""):
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "Force push denied",
            }
        }
    return {}

# 配置
options = ClaudeAgentOptions(
    system_prompt="You are a senior software engineer. Write clean, tested code.",
    allowed_tools=["Read", "Write", "Edit", "Bash", "Grep", "Glob"],
    model="sonnet",
    max_turns=15,
    permissionMode="acceptEdits",
    setting_sources=["user", "project"],
    agents={
        "test-writer": AgentDefinition(
            description="Writes comprehensive tests using pytest",
            prompt="You are a test engineer. Write thorough pytest tests with fixtures and edge cases.",
            tools=["Read", "Write", "Bash"],
            model="haiku",  # 测试生成用轻量模型
            maxTurns=8,
        ),
    },
    hooks={
        "PreToolUse": [HookMatcher(matcher="Bash", hooks=[deny_force_push])],
    },
)

async def main():
    async for message in query(
        prompt="Write tests for the auth.py module in src/",
        options=options,
    ):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text)
        elif isinstance(message, ResultMessage):
            print(f"Done. Cost: ${message.total_cost_usd:.4f}")

anyio.run(main)
```

### 9.3 AgentDefinition 完整字段解析

```python
@dataclass
class AgentDefinition:
    description: str              # 短描述, 供主 Agent 决定何时使用
    prompt: str                   # 系统提示词 (子代理的角色和行为)
    tools: list[str] | None       # 工具白名单 (None = 继承主 Agent)
    disallowedTools: list[str] | None   # 工具黑名单 (覆盖白名单)
    model: str | None             # "sonnet"|"opus"|"haiku"|"inherit"
    skills: list[str] | None      # 注入的 Skill 名称列表
    memory: Literal["user","project","local"] | None  # Memory 可见范围
    mcpServers: list[str|dict] | None   # MCP 工具服务器
    initialPrompt: str | None     # 子代理启动后立即发送的消息
    maxTurns: int | None          # 最大工具调用轮数限制
    background: bool | None       # 后台模式
    effort: EffortLevel | None    # 推理强度 ("low"/"medium"/"high"/"xhigh")
    permissionMode: PermissionMode | None  # 权限模式覆盖
```

---

## 10. Agent 设计模式 — 五大经典模式与代码实现

这五种模式来自 Anthropic 官方 Cookbook (`patterns/agents/`)，是 Agent 系统设计的基石。

### 模式 1：Prompt Chaining（提示链）

```
输入 → [LLM1: 提取关键信息] → [LLM2: 基于信息生成报告] → 输出

适合: 任务可分解为固定顺序子任务
不适合: 子任务间需要动态交互
```

```python
async def chain_workflow(input_text: str) -> str:
    # Step 1: 提取
    extract_resp = await llm.call(
        prompt=f"Extract key points from: {input_text}",
        system="Extract factual claims and data points. Return as bullet list."
    )
    # Step 2: 生成报告
    report_resp = await llm.call(
        prompt=f"Write a 1-page summary based on:\n{extract_resp}",
        system="Write a professional executive summary."
    )
    return report_resp
```

### 模式 2：Routing（路由）

```
输入 → [LLM 分类器: 类型?] → 技术问题 → [技术专家 LLM]
                           → 账单问题 → [账单专家 LLM]
                           → 账号问题 → [账号专家 LLM]

适合: 输入类别差异大, 每类最优处理方式不同
```

```python
ROUTES = {
    "technical": "You are a technical support engineer...",
    "billing": "You are a billing specialist...",
    "account": "You are an account manager...",
}

async def route_workflow(query: str) -> str:
    # 分类
    category = await llm.call(
        prompt=f"Classify: {query}",
        system="Reply with exactly one word: technical, billing, or account."
    )
    # 路由
    return await llm.call(
        prompt=query,
        system=ROUTES.get(category.strip().lower(), ROUTES["technical"])
    )
```

### 模式 3：Parallelization（并行化）

```
输入 → [LLM1: 安全审查] ──┐
      [LLM2: 性能审查] ──┼──→ [LLM 聚合: 生成统一报告] → 输出
      [LLM3: 风格审查] ──┘

适合: 子任务相互独立, 可并发执行
```

```python
import asyncio

async def parallel_workflow(code: str) -> str:
    reviews = await asyncio.gather(
        llm.call(prompt=code, system="Review for security vulnerabilities."),
        llm.call(prompt=code, system="Review for performance issues."),
        llm.call(prompt=code, system="Review for code style and readability."),
    )
    return await llm.call(
        prompt=f"Combine into a single review report:\n1. {reviews[0]}\n2. {reviews[1]}\n3. {reviews[2]}",
        system="Merge review findings. Remove duplicates. Prioritize by severity.",
    )
```

### 模式 4：Orchestrator-Workers（编排器-工作者）

```
输入 → [Orchestrator LLM: 动态分解任务]
          ├──→ [Worker 1: 子任务 A]
          ├──→ [Worker 2: 子任务 B]
          └──→ [Worker 3: 子任务 C] (动态决定, 非预设)
                │
          [Orchestrator: 汇总 & 综合] → 输出

这是 Claude Code 主 Agent→Sub-Agent 的核心模式。
```

```python
async def orchestrator_workflow(task: str) -> str:
    # Orchestrator 动态规划
    plan = await llm.call(
        prompt=f"Break down: {task}",
        system="Plan subtasks. Output as: SUBTASK: <description> (one per line)"
    )
    subtasks = [line.replace("SUBTASK:", "").strip()
                for line in plan.split("\n") if line.startswith("SUBTASK:")]

    # 动态分派 Workers (可并行)
    results = await asyncio.gather(*[
        llm.call(prompt=f"Complete: {subtask}", system="Execute precisely.")
        for subtask in subtasks
    ])

    # Orchestrator 综合结果
    combined = "\n---\n".join(f"Subtask {i+1}: {r}" for i, r in enumerate(results))
    return await llm.call(
        prompt=f"Synthesize into a final answer:\n{combined}",
        system="Create a cohesive, non-redundant final response."
    )
```

### 模式 5：Evaluator-Optimizer（评估器-优化器）

```
初始输出 → [Evaluator: 评分 & 反馈] → 不够好? → [Optimizer: 改进]
    ↑                                                    │
    └──────────────── 循环迭代 ──────────────────────────┘
                                        够好 → 输出

这是 Hermes GEPA 优化的核心模式。
```

```python
async def evaluator_optimizer(task: str, max_iterations: int = 3) -> str:
    current = await llm.call(prompt=task, system="Generate a solution.")

    for i in range(max_iterations):
        # 评估
        evaluation = await llm.call(
            prompt=f"Task: {task}\nSolution: {current}",
            system="Rate 1-10. If < 8, give specific, actionable feedback for improvement."
        )
        if "Rating: 8" in evaluation or "Rating: 9" in evaluation or "Rating: 10" in evaluation:
            break  # 达到质量标准

        # 基于反馈优化
        current = await llm.call(
            prompt=f"Original: {current}\nFeedback: {evaluation}\nImprove the solution.",
            system="Incorporate all feedback. Output the complete improved solution."
        )

    return current
```

---

## 10-A. LangGraph — 有状态 Agent 编排框架

### 10-A.1 概述

[LangGraph](https://github.com/langchain-ai/langgraph) 是 LangChain 团队开发的**低级编排框架**，专为构建长时间运行的、有状态的 Agent 设计。它不预设高层的 Agent 范式，而是提供构建任何 Agent 架构所需的底层基础设施。

- **仓库**: [github.com/langchain-ai/langgraph](https://github.com/langchain-ai/langgraph) (32K+ Stars, 5.5K+ Forks)
- **安装**: `pip install -U langgraph`
- **许可证**: MIT
- **核心定位**: "Low-level orchestration framework for building stateful agents"
- **设计灵感**: Google Pregel + Apache Beam + NetworkX

### 10-A.2 核心概念与 API 体系

#### 最简 7 行 Agent

```python
from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict

class State(TypedDict):
    messages: list

def chatbot(state: State) -> dict:
    return {"messages": [llm.invoke(state["messages"])]}

graph = StateGraph(State)
graph.add_node("chatbot", chatbot)
graph.add_edge(START, "chatbot")
graph.add_edge("chatbot", END)
app = graph.compile()
app.invoke({"messages": ["Hello!"]})
```

#### 核心概念矩阵

| 概念 | 作用 | 类比 |
|------|------|------|
| **StateGraph** | 图构建器，定义 Agent 的结构 | 蓝图 |
| **State (TypedDict)** | 在节点间共享的可变数据 | 白板 / 共享内存 |
| **Node** | 执行业务逻辑的函数 | 步骤 / 处理器 |
| **Edge** | 确定节点间的控制流 | 连线 |
| **Conditional Edge** | 基于 State 动态路由 | if/else 分支 |
| **CompiledGraph** | `.compile()` 后的可执行图 | 运行实例 |
| **Checkpointer** | 持久化图状态，支持断点续传 | 快照 / 数据库 |
| **Command** | 节点返回的指令，用于动态路由或状态更新 | 信号 |
| **Send** | 向多个节点并行发送不同参数 | fan-out 分发 |
| **Interrupt** | 暂停执行等待人工审批 | 断点 |
| **Pregel Runtime** | BSP (Bulk Synchronous Parallel) 执行引擎 | 调度器 |

### 10-A.3 核心抽象详解

#### State — 图的共享内存

```python
from typing_extensions import Annotated, TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage

# 基础 State
class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]  # add_messages 是内置 reducer
    next_step: str | None
    task_list: list[str]
    final_output: str | None

# Annotated[Type, reducer] 是 LangGraph 的核心类型模式:
# - 第一个参数: 值的类型
# - 第二个参数: reducer 函数，定义多节点并发写入时的合并策略
# 如: Annotated[list, add_messages] → 新消息 append 而非覆盖
```

**内置 Reducer**:
| Reducer | 行为 |
|---------|------|
| `add_messages` | 追加消息（支持消息 ID 去重、并行 ToolMessage 合并） |
| 自定义 `(a, b) → a` | 任意合并逻辑 |
| 无 reducer (裸类型) | 覆盖 (最后一次写入生效) |

#### Nodes — 业务逻辑单元

```python
# Node 的三种签名形式
# 形式 1: 接收完整 State, 返回 State 的部分更新
def my_node(state: AgentState) -> dict:
    return {"next_step": "tool_execution"}

# 形式 2: 接收完整 State + Runtime Context
def my_node(state: AgentState, runtime: Runtime[Context]) -> dict:
    user_id = runtime.context["user_id"]
    return {"next_step": f"approved_by_{user_id}"}

# 形式 3: 接收完整 State, 返回 Command (动态路由)
def router(state: AgentState) -> Command:
    if state["next_step"] == "search":
        return Command(goto="search_node")
    return Command(goto="response_node")
```

#### Edges — 控制流

```python
# 普通边: 固定路由
graph.add_edge("node_a", "node_b")
graph.add_edge(START, "entry_node")
graph.add_edge("final_node", END)

# 条件边: 基于 State 动态路由
def routing_function(state: AgentState) -> str:
    if "error" in state.get("status", ""):
        return "error_handler"
    if state.get("needs_search"):
        return "search_tool"
    return "respond"

graph.add_conditional_edges(
    "router",
    routing_function,
    {
        "search_tool": "search_tool",     # routing返回 → 目标节点
        "error_handler": "error_handler",
        "respond": "respond",
    }
)
```

### 10-A.4 关键功能详解

#### A. Durable Execution（持久化执行）— Checkpointing

LangGraph 的核心差异化能力。通过 Checkpointer 将图状态持久化，实现：
1. **断点续传**: 进程崩溃后从上次 checkpoint 恢复
2. **时间旅行**: 回溯到任意 checkpoint 重放
3. **分支执行**: 从某个 checkpoint 分叉出不同执行路径

```python
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.postgres import PostgresSaver

# 内存版 (开发/测试)
checkpointer = InMemorySaver()

# SQLite 版 (本地持久化)
checkpointer = SqliteSaver.from_conn_string("checkpoints.db")

# Postgres 版 (生产)
checkpointer = PostgresSaver.from_conn_string("postgresql://...")

app = graph.compile(checkpointer=checkpointer)

# 使用 thread_id 隔离不同会话
config = {"configurable": {"thread_id": "user-123-session-1"}}
app.invoke({"messages": ["Hi"]}, config=config)

# 崩溃后恢复 — 同样的 thread_id, 从上次 checkpoint 继续
app.invoke({"messages": ["Continue"]}, config=config)

# 时间旅行 — 回到特定 checkpoint
state = app.get_state(config)
checkpoint_id = state.config["configurable"]["checkpoint_id"]
# 重放:
app.invoke(None, config={"configurable": {
    "thread_id": "user-123-session-1",
    "checkpoint_id": checkpoint_id
}})
```

#### B. Human-in-the-Loop（人工介入）

```python
from langgraph.types import interrupt

def approval_node(state: AgentState) -> dict:
    # interrupt() 暂停执行，返回当前值给调用者
    # 调用者审查/修改后，用 Command(resume=...) 继续
    user_decision = interrupt({
        "question": f"Approve this action?",
        "action": state["pending_action"],
    })
    if user_decision == "approved":
        return {"status": "executing"}
    return {"status": "rejected"}

# 调用侧:
app = graph.compile(checkpointer=checkpointer)
config = {"configurable": {"thread_id": "1"}}

# 执行到 interrupt 点时暂停
app.invoke({"pending_action": "delete_production_db"}, config=config)

# 获取暂停状态
state = app.get_state(config)
print(state.interrupts)  # [{'question': 'Approve this action?', ...}]

# 审批通过
from langgraph.types import Command
app.invoke(Command(resume="approved"), config=config)
```

#### C. Streaming（流式输出）

LangGraph 支持 7 种流模式，可以组合使用：

```python
# 模式组合: values + messages
for mode, chunk in app.stream(
    {"messages": ["Explain LangGraph"]},
    config=config,
    stream_mode=["values", "messages"]  # 同时获取状态快照 + token 流
):
    if mode == "values":
        print(f"State: {chunk}")         # 每步之后的状态
    elif mode == "messages":
        msg, metadata = chunk
        print(msg.content, end="")       # 逐 token 输出
```

| Stream Mode | 输出内容 | 适用场景 |
|-------------|---------|---------|
| `values` | 每步执行后的完整 State | 追踪状态演化 |
| `updates` | 每步的增量更新 | 进度展示 |
| `messages` | token-by-token LLM 输出 | 打字机效果 |
| `custom` | 节点内 `StreamWriter` 写入的自定义数据 | 自定义进度 |
| `checkpoints` | checkpoint 创建事件 | 调试持久化 |
| `tasks` | 任务启动/完成事件 | 性能监控 |
| `debug` | checkpoints + tasks | 全量调试 |

#### D. Command — 动态路由原语

`Command` 是 LangGraph 的核心控制原语，节点可以通过返回 `Command` 来：
- 跳转到任意节点 (goto)
- 更新图状态 (update)
- 向父图发送指令 (parent)

```python
from langgraph.types import Command

# 常规返回: 仅更新 State
def normal_node(state):
    return {"key": "value"}

# Command 返回: 更新 State + 控制路由
def routing_node(state):
    if state["count"] > 10:
        return Command(
            update={"status": "done"},
            goto="finish_node"
        )
    return Command(goto="loop_back")

# 并行 fan-out: 向多个节点各发不同 State
def fanout_node(state):
    tasks = state["tasks"]
    return [
        Send("worker", {"task": tasks[0]}),
        Send("worker", {"task": tasks[1]}),
        Send("worker", {"task": tasks[2]}),
    ]
```

#### E. Subgraph（子图嵌套）

```python
# 定义一个子图
subgraph = StateGraph(SubState)
subgraph.add_node("inner", inner_node)
subgraph.add_edge(START, "inner")
subgraph.add_edge("inner", END)
compiled_subgraph = subgraph.compile()

# 在主图中作为普通节点使用
main_graph = StateGraph(MainState)
main_graph.add_node("sub_task", compiled_subgraph)  # 直接使用编译后的子图
main_graph.add_edge(START, "sub_task")
```

### 10-A.5 高级执行模型 — Pregel Runtime

LangGraph 的运行时基于 Google 的 Pregel（BSP — Bulk Synchronous Parallel）模型：

```
每个 super-step:
  ┌──────────────────────────────────────────────┐
  │  1. Plan: 决定下一步执行哪些节点               │
  │     读取 State → 评估所有发出边的条件           │
  │     → 确定活跃的节点集合                       │
  │                                              │
  │  2. Execute: 并发执行所有活跃节点              │
  │     每个节点读取当前 State → 执行 → 返回更新   │
  │                                              │
  │  3. Update: 将所有更新合并到 State            │
  │     使用每个 key 的 reducer 合并并发写入       │
  │     → 生成新的 State 快照                     │
  │                                              │
  │  4. Checkpoint: 持久化新 State (如果配置了)   │
  └──────────────────────────────────────────────┘
  → 下一个 super-step
  → 直到所有节点都指向 END 或条件不满足
```

```
Pregel 执行示意 (3个节点):

Step 1: [A 活跃] → A 执行 → State v1
Step 2: [B, C 活跃] → B, C 并发执行 → 合并 → State v2
Step 3: [D 活跃] → D 执行 → State v3
Step 4: [END 活跃] → 结束
```

**关键保证**:
- 同一 super-step 内的节点并发执行
- 不同 super-step 间的节点顺序执行
- 同一 key 的并发写入通过 reducer 合并（确定性）
- Checkpoint 在 super-step 边界记录（断点一致性）

### 10-A.6 Prebuilt — 高层 API

LangGraph 提供 `prebuilt` 库快速创建常用 Agent 模式：

```python
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool

# 定义工具
@tool
def search(query: str) -> str:
    """Search the web for information."""
    return f"Results for: {query}"

# 单行创建 ReAct Agent
agent = create_react_agent(
    model="claude-sonnet-4-6",
    tools=[search],
    prompt="You are a helpful assistant with access to search."
)

# 使用
result = agent.invoke({"messages": ["What's new in AI?"]})
```

**Prebuilt 提供的 Agent 类型**:
| Agent | 说明 |
|-------|------|
| `create_react_agent` | 标准 ReAct (Reasoning + Acting) 模式 |
| `ToolNode` | 工具执行节点 (接收 tool_calls, 返回 ToolMessage) |

`create_react_agent` 的内部等价于：

```python
class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]

graph = StateGraph(AgentState)

# 两个节点
graph.add_node("agent", llm_with_tools)   # LLM 推理 + 决定调用什么工具
graph.add_node("tools", ToolNode(tools))   # 执行工具

# 路由
graph.add_edge(START, "agent")
graph.add_conditional_edges(
    "agent",
    # 如果 LLM 返回了 tool_calls → 去 tools 节点
    # 否则 → END
    lambda state: "tools" if state["messages"][-1].tool_calls else END,
)
graph.add_edge("tools", "agent")  # 工具结果 → 回到 agent 继续推理
```

### 10-A.7 经典模式 LangGraph 实现

#### 模式 1: ReAct Agent (从零构建)

```python
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing_extensions import Annotated, TypedDict
from langchain_core.messages import AnyMessage

class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]

def call_model(state: State) -> dict:
    response = llm.bind_tools(tools).invoke(state["messages"])
    return {"messages": [response]}

def should_continue(state: State) -> str:
    last = state["messages"][-1]
    return "tools" if last.tool_calls else END

graph = StateGraph(State)
graph.add_node("agent", call_model)
graph.add_node("tools", ToolNode(tools))
graph.add_edge(START, "agent")
graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
graph.add_edge("tools", "agent")
app = graph.compile(checkpointer=InMemorySaver())
```

#### 模式 2: Multi-Agent Collaboration (多 Agent 协作)

```python
# Agent 1: 搜索专家
search_agent = create_react_agent(llm, [search_tool])
# Agent 2: 计算专家
calc_agent = create_react_agent(llm, [calculator_tool])

class MultiAgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    next_agent: str

def router(state: MultiAgentState) -> Command:
    last = state["messages"][-1]
    if "search" in last.content.lower():
        return Command(goto="search_expert")
    elif "calculate" in last.content.lower():
        return Command(goto="calc_expert")
    return Command(goto="finish")

graph = StateGraph(MultiAgentState)
graph.add_node("search_expert", search_agent)
graph.add_node("calc_expert", calc_agent)
graph.add_node("supervisor", supervisor_node)
graph.add_edge(START, "supervisor")
graph.add_conditional_edges("supervisor", router, {...})
```

#### 模式 3: Plan-and-Execute

```python
class PlanState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    plan: list[str]      # 计划步骤列表
    current_step: int    # 当前执行到第几步

def planner(state: PlanState) -> dict:
    plan = llm.invoke(f"Create a step-by-step plan: {state['messages'][-1]}")
    return {"plan": parse_plan(plan), "current_step": 0}

def executor(state: PlanState) -> dict:
    step = state["plan"][state["current_step"]]
    result = llm.invoke(f"Execute: {step}")
    return {"messages": [result], "current_step": state["current_step"] + 1}

def should_loop(state: PlanState) -> str:
    return "execute" if state["current_step"] < len(state["plan"]) else END
```

#### 模式 4: Reflection / Self-Correction

```python
def generate(state: State) -> dict:
    return {"draft": llm.invoke(state["messages"]).content}

def reflect(state: State) -> Command:
    feedback = llm.invoke(
        f"Critique this draft. List specific improvements:\n{state['draft']}"
    )
    if "no issues" in feedback.lower():
        return Command(goto=END)
    return Command(
        update={"feedback": feedback, "revision_count": state["revision_count"] + 1},
        goto="revise"
    )

def revise(state: State) -> dict:
    return {"draft": llm.invoke(
        f"Revise based on feedback:\nDraft: {state['draft']}\nFeedback: {state['feedback']}"
    )}
```

### 10-A.8 LangGraph vs Other Frameworks

| 维度 | LangGraph | Claude Agent SDK | LangChain | CrewAI |
|------|-----------|-----------------|-----------|--------|
| **抽象层级** | 低级 (图原语) | 高级 (Agent 即函数) | 高级 (Chain) | 高级 (Agent 角色) |
| **状态管理** | 显式 TypedDict + Reducer | SDK 内部管理 | RunnableState | 隐式 |
| **持久化** | 深度支持 (Checkpoint) | 会话级 | 无内置 | 无内置 |
| **Human-in-loop** | interrupt() 原生支持 | Hook PreToolUse | 无 | 无 |
| **控制流** | 图 (条件边, Command, Send) | Agent Loop | Chain 顺序 | Agent 顺序 |
| **并发模型** | BSP (同 step 内节点并发) | 子代理并行 | 无 | 无 |
| **厂商锁定** | 模型无关 | Anthropic | 模型无关 | 模型无关 |
| **学习曲线** | 陡峭 (理解图模型) | 平缓 (API 简洁) | 中等 | 平缓 |
| **适合场景** | 复杂多步骤 Agent | Claude 生态快速开发 | Chain 型 LLM 应用 | 固定角色多 Agent |

### 10-A.9 何时选择 LangGraph

```
选择 LangGraph 当:
├── Agent 需要跨多次调用保持状态 (不是一次对话)
├── 需要持久化执行 (断点续传、崩溃恢复)
├── 需要 Human-in-the-loop (审批节点)
├── 图结构在运行时不确定 (Command 动态路由)
├── 多个 Agent 需要以复杂拓扑协作 (不是简单链式)
├── 需要完整的执行可观测性 (LangSmith 集成)
└── 模型/工具无关 (不绑定特定厂商)

选择 Claude Agent SDK 当:
├── 主要使用 Claude 模型
├── 需要快速开发 (API 简洁)
├── 在 Claude Code 生态中 (IDE/CLI 集成)
└── Agent 模式相对简单 (ReAct 循环)

两者可以互补: 在 LangGraph 中调用 Claude API, 用 LangGraph 管理复杂工作流
```

---

# 第二部分：Agent 工程师学习路线

## 11. 五层能力模型

```
                    ┌──────────────────────────────┐
                    │  5. 产品思维                   │
                    │  用户场景 · 体验设计 · 成本建模 │
                    │  "为什么要构建这个 Agent?"      │
                    ├──────────────────────────────┤
                    │  4. 系统设计                   │
                    │  架构模式 · 安全 · 评估 · 观测  │
                    │  "如何设计一个可靠的 Agent?"     │
                    ├──────────────────────────────┤
                    │  3. Agent 框架与生态            │
                    │  SDK · LangChain · MCP · CrewAI│
                    │  "用什么工具构建 Agent?"        │
                    ├──────────────────────────────┤
                    │  2. LLM 基础                   │
                    │  API · Prompt · Token · Tool Use│
                    │  "LLM 如何工作?"               │
                    ├──────────────────────────────┤
                    │  1. 软件工程基础                │
                    │  Python · Git · Linux · Docker │
                    │  "如何写生产级代码?"            │
                    └──────────────────────────────┘
```

## 12. 分层学习路线与时间线

### 第一层：软件工程基础（预计 2-3 个月）

| 技能 | 最低要求 | 与 Agent 开发的关系 |
|------|---------|-------------------|
| **Python** | 熟练，特别是 asyncio | Agent SDK 全异步 API |
| **Git** | 分支/合并/rebase/cherry-pick | Agent 核心操作对象 |
| **Linux/Shell** | 文件系统/进程/管道/权限 | Agent 的执行环境 |
| **Docker** | Dockerfile/docker-compose | 沙箱隔离的基础 |
| **HTTP/REST** | 请求/响应/状态码/认证 | LLM API 调用基础 |
| **JSON/JSON Schema** | 数据结构设计 | 工具参数定义标准 |

### 第二层：LLM 基础（预计 1-2 个月）

```
核心知识图谱:
├── Tokenization: BPE 原理, token vs 字符, 不同模型的 tokenizer 差异
├── Context Window: 限制, 预算, 分配策略
├── Prompt Engineering:
│   ├── System Prompt 设计 (角色 + 约束 + 可用工具)
│   ├── Few-shot/Zero-shot 策略选择
│   ├── Chain-of-Thought: 何时需要, 如何引导
│   ├── XML Tag 技巧: <thinking>, <output>, <constraint> 结构化
│   └── 防注入: 系统提示词 vs 用户输入的边界
├── Function Calling/Tool Use:
│   ├── Schema 设计: 参数名, 描述质量决定模型使用准确率
│   ├── 结果格式化: 错误信息设计 (模型需要能"读懂"错误)
│   └── 并行调用: 多个独立 tool_call 同时返回
├── Prompt Caching: 标记策略, TTL, 命中率优化
├── 模型选择决策:
│   ├── Opus: 复杂推理, 架构设计, 多步规划
│   ├── Sonnet: 日常编码, 代码审查, 常规任务
│   └── Haiku: 简单分类, 格式化, 路由
└── Embedding 与 RAG:
    ├── 文档切分策略 (chunk size, overlap)
    ├── 向量数据库选择 (Chroma/Pinecone/Weaviate)
    └── 检索增强的 Agent 集成
```

### 第三层：Agent 框架与生态（预计 2-3 个月）

**必学** (顺序有先后):

1. **Claude Agent SDK** — 理解 Agent 的完整生命周期
2. **MCP 协议** — 工具集成的标准, 写自己的 MCP Server
3. **LangChain + LangGraph** — 通用框架, 有状态工作流
4. **读取 Hermes Agent 源码** — 学习自进化机制

**选学**:
- CrewAI/AutoGen — 多 Agent 协作框架
- Aider/OpenHands — 其他 Agent 实现参考

### 第四层：Agent 系统设计（预计 3-4 个月）

**实践项目 (按难度递增)**:

1. 实现一个**带工具的单 Agent**: `query() → Tool Call → execute → 结果 → 最终回复`
2. 添加 **Hook 系统**: PreToolUse 安全检查
3. 添加 **Memory**: 文件系统存储 + 会话间持久
4. 实现 **Sub-Agent**: Orchestrator → Workers 任务分解
5. 实现 **评估框架**: 自动化测试 + LLM-as-Judge
6. 实现 **上下文压缩**: 摘要替代截断
7. 实现 **权限系统**: 多层 allow/deny/ask 决策
8. 实现 **自进化**: Background Review 类 Hermes

### 第五层：产品思维（持续）

核心问题:
- 这个 Agent 解决的是什么用户问题？（不是"用了什么技术"）
- Agent 犯错时的用户体验是什么？
- 每次调用的成本 vs 用户获得的价值？
- 人类应该在什么时候接管？

## 13. 关键技术深入指引

### 13.1 如何读懂 Agent 源码

```
推荐阅读顺序:

1. claude-agent-sdk-python/examples/quick_start.py
   → 理解最简 Agent 调用 (10行代码)

2. claude-agent-sdk-python/examples/agents.py
   → 理解子代理定义和工作方式

3. claude-agent-sdk-python/examples/hooks.py
   → 理解 Hook 的 6 种使用模式

4. claude-agent-sdk-python/src/claude_agent_sdk/types.py
   → 理解完整的数据模型

5. NousResearch/hermes-agent/agent/conversation_loop.py
   → 理解 Agent Loop 的完整实现

6. NousResearch/hermes-agent/agent/background_review.py
   → 理解自进化的实现
```

### 13.2 动手实践的最小路径

```
Week 1: 调用 Anthropic API 实现多轮对话
Week 2: 添加 Function Calling (1个工具)
Week 3: 实现完整的 Agent Loop (多工具 + 循环)
Week 4: 添加 Hook 系统 (PreToolUse 安全检查)
Week 5: 添加 Memory (文件持久化)
Week 6: 实现 Sub-Agent (Orchestrator-Workers)
Week 7-8: 完整的 Agent 框架 (评估 + 上下文管理)
```

## 14. 推荐资源全清单

### 官方文档

| 资源 | 链接 | 必读程度 |
|------|------|---------|
| Claude Code 官方文档 | [code.claude.com/docs](https://code.claude.com/docs/en/overview) | ⭐⭐⭐⭐⭐ |
| Anthropic API 文档 | [docs.anthropic.com/en/api](https://docs.anthropic.com/en/api) | ⭐⭐⭐⭐⭐ |
| Claude Agent SDK (Python) | [github.com/anthropics/claude-agent-sdk-python](https://github.com/anthropics/claude-agent-sdk-python) | ⭐⭐⭐⭐⭐ |
| MCP 协议规范 | [modelcontextprotocol.io](https://modelcontextprotocol.io/) | ⭐⭐⭐⭐ |
| Building Effective Agents | [anthropic.com/research](https://www.anthropic.com/research/building-effective-agents) | ⭐⭐⭐⭐⭐ |

### 代码仓库

| 仓库 | 学习重点 |
|------|---------|
| [anthropics/claude-code](https://github.com/anthropics/claude-code) | 产品级 Agent 设计 (125K+ Stars) |
| [anthropics/claude-agent-sdk-python](https://github.com/anthropics/claude-agent-sdk-python) | 官方 Agent SDK |
| [anthropics/claude-cookbooks](https://github.com/anthropics/claude-cookbooks) | 5 种 Agent 模式 + SDK 示例 |
| [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) | 官方插件 & MCP 示例 |
| [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) | 自进化 Agent 完整实现 |

---

## 14-A. Anthropic 工程博客全览 (24 篇)

基于 [anthropic.com/engineering](https://www.anthropic.com/engineering) 全部文章的提取和总结，按主题分类。

### 14-A.1 Agent 设计与架构 (5 篇)

#### Building Effective Agents
https://www.anthropic.com/engineering/building-effective-agents
*Published Dec 19, 2024 — Anthropic 关于 Agent 设计的奠基性文章*

**核心区分：Workflow vs Agent**。Anthropic 将所有 LLM 应用称为"agentic systems"，但划出关键架构边界：**Workflow** 是通过预定义代码路径编排 LLM 和工具；**Agent** 是 LLM 动态控制自身流程和工具使用。建议先问"是否需要 agentic system"——Agent 系统用延迟和成本换取更好的任务表现，需要判断这个权衡何时成立。对于许多应用，优化单次 LLM 调用（配合检索和上下文示例）已经足够。

**五种模式详解**：
1. **Prompt Chaining（提示链）**：将任务分解为顺序步骤，每步基于前一步输出。可在中间步骤添加程序化检查（gate）确保流程在正轨。适用：可清晰分解为固定子任务时。典型场景：生成营销文案→翻译为其他语言；写大纲→检查大纲→基于大纲写文档。
2. **Routing（路由）**：分类输入并分发到专门的后继任务。允许关注点分离和更专门的提示。适用：有明确不同类别且分类可靠时。典型场景：客服查询分发（一般/退款/技术支持）；简单问题路由到 Haiku、难问题路由到 Opus 以优化成本。
3. **Parallelization（并行化）**：两个变体——Sectioning（拆分为独立子任务并行运行）和 Voting（同一任务多次运行获得多样化输出）。适用：子任务可并行加速，或需要多视角/多次尝试提高置信度时。典型场景：Sectioning——一个模型处理查询，另一个审查内容安全；Voting——多角度代码漏洞审查、多阈值内容评估。
4. **Orchestrator-Workers（编排器-工作者）**：中央 LLM 动态分解任务、委派给 Worker LLM、综合结果。与 Parallelization 的关键区别：子任务不是预定义的，而是由 Orchestrator 根据具体输入动态决定。适用：无法预测所需子任务的复杂开放任务。这是 Claude Code 和 Claude Research 的核心架构。
5. **Evaluator-Optimizer（评估器-优化器）**：一个 LLM 生成响应，另一个在循环中提供评估和反馈。适用：有明确评估标准且 LLM 反馈可被 LLM 自身改进时。典型场景：文学翻译（评估器可能不擅长翻译但能指出不流畅处）；代码生成→测试→修复循环。

**Agent-Computer Interface (ACI) 设计**：工具定义是 LLM 与外部世界的接口，值得与系统提示词同等的提示工程投入。核心原则——工具名称和描述要语义精确、参数要最小化且不言自明、返回结果要高信号低噪音。

**框架使用建议**：建议从直接用 LLM API 开始——许多模式几行代码即可实现。如果使用框架，确保理解底层代码。对底层的不正确假设是客户错误的常见来源。

#### Multi-Agent Research System
https://www.anthropic.com/engineering/multi-agent-research-system
*Published Jun 13, 2025 — Claude Research 背后的多 Agent 架构全揭秘*

**架构概述**：Claude Research 使用 Orchestrator-Worker 模式。用户提交查询后，系统创建 **LeadResearcher Agent**（Claude Opus 4），制定策略并在 Memory 中持久化计划（防止上下文窗口超过 200K tokens 时被截断）。LeadResearcher 创建专门的 **Subagents**（Claude Sonnet 4），每个拥有独立上下文窗口，并行搜索不同方面。Subagents 使用交错思考（interleaved thinking）评估搜索结果，返回发现给 LeadResearcher。LeadResearcher 综合结果后决定是否需要更多搜索——可创建更多子代理或细化策略。信息充足后，所有发现传递给 **CitationAgent** 校验来源引用。

**Token 经济学是核心**：三个因素解释了 BrowseComp 评估中 95% 的性能差异——token 使用量单独占 80%，工具调用次数和模型选择是另外两个因素。多 Agent 架构通过并行化有效扩展 token 使用量。升级到 Claude Sonnet 4 的性能收益比将 Claude Sonnet 3.7 的 token 预算加倍还要大。多 Agent 系统比单 Agent Opus 4 表现高 90.2%，但消耗的 token 约是聊天的 15 倍，约是单 Agent 的 4 倍。

**Subagents 的核心作用——智能压缩过滤器**：每个 Subagent 在独立上下文窗口中执行多步搜索、动态适应新发现、分析结果并在返回前精简为最相关的信息。这解决了上下文窗口有限的问题——Subagents 承担低级别的信息搜集和过滤工作，LeadResearcher 只需要看到精炼后的结果。与传统 RAG（静态检索固定块）不同，这种架构使用**多步动态搜索**，可根据中间发现调整搜索方向。

**提示工程原则**："像你的 Agent 一样思考"——优化 Agent 行为需要深入理解工具执行的具体情况。关键实践：为 Agent 编写清晰的指令和边界，限制 Subagent 数量防止过度生成（早期错误包括为简单查询生成 50 个子代理），确保每个 Agent 有明确的"何时停止"的标准。

**适用范围**：在广度优先、可高度并行化的查询中最有效（如"找出 S&P 500 IT 板块公司的所有董事会成员"）。在存在大量任务依赖关系的领域（如大多数编码任务）中效果较差——LLM Agent 尚不擅长实时协调和委托。

#### Effective Harnesses for Long-Running Agents
https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
*Published Nov 26, 2025 — 解决跨上下文窗口长运行 Agent 的完整工程方案*

**核心问题**：每次新会话开始时 Agent 对之前的工作毫无记忆。两种失败模式：(1) Agent 试图一次完成所有事情，结果上下文耗尽时功能实现一半；(2) Agent 看到已有进展后过早宣布任务完成。

**双 Agent 架构**：**Initializer Agent**（仅运行一次）设置完整环境——创建 `init.sh` 开发服务器启动脚本、以 JSON 格式编写 200+ 功能的 feature list（全部标记 `"passes": false`）、写 `claude-progress.txt` 日志文件、做初始 git 提交。**Coding Agent**（每后续会话）遵循固定的启动仪式——`pwd` 定位自己→读 `claude-progress.txt` 了解状态→读 JSON feature list 选最高优先级未完成项→`git log --oneline -20` 了解最近工作→`init.sh` 启动服务器→**先跑一个基础 E2E 冒烟测试**→实现恰好一个功能→git 提交→更新 progress 文件。

**JSON Feature List 的设计理由**：LLM 意外覆盖或破坏 JSON 数据结构的概率远低于 Markdown。每个功能包含 category、description、steps（测试步骤）、passes（布尔值）。Agent 只应修改 `passes` 字段。

**Git 作为跨会话记忆和回滚系统**：每会话以读 git history 开始、以描述性提交结束。形成只追加的工作日志，任何 Agent 可从中重建上下文。错误提交可恢复。

**强制端到端测试**：Agent 被显式指示使用浏览器自动化工具（Puppeteer MCP）进行测试。单元测试或 curl 被认为不够——Agent 需要像用户一样操作 UI。提供截图能力后性能大幅提升。

**失败模式→解决方案映射**：过早宣布完成→结构化 JSON feature list（默认全失败）+ 自我验证 E2E；留下 bug→必须每会话干净提交 + 进度更新；标记功能完成但未正确测试→必须用 Puppeteer 自我验证。

#### Managed Agents: Decoupling the Brain from the Hands
https://www.anthropic.com/engineering/managed-agents
*Published Apr 08, 2026 — Anthropic 平台运行长周期 Agent 的架构演进*

**核心洞察**：Harness（骨架）编码了对"Claude 不能做什么"的假设——这些假设随模型改进而过时。如 Claude Sonnet 4.5 在接近上下文限制时会过早结束任务（"上下文焦虑"），但 Claude Opus 4.5 上这种行为消失——原先为此添加的 context reset 变成了死代码。因此 Managed Agents 被设计为一小组**稳定的接口**，接口不变，实现可自由替换。

**从 Pet 到 Cattle 的演进**：最初设计将所有组件（Session、Harness、Sandbox）耦合在单一容器中。问题：容器崩溃→会话丢失；容器无响应→只能手动修复；无法区分 bug/网络丢包/容器离线的故障原因；凭证与生成代码在同一容器中只需一次 prompt injection 即可泄露。

**三大虚拟化接口**：
1. **Session（会话）**：持久化只追加事件日志，独立于 Harness 和 Sandbox。Harness 崩溃后新的可被 `wake(sessionId)` 唤醒，通过 `getSession(id)` 获取事件日志，从上次事件恢复。Harness 通过 `emitEvent(id, event)` 保持持久记录。
2. **Harness（骨架）**：Agent Loop，现已无状态（cattle）。调用 Sandbox 就像调用任何工具：`execute(name, input) → string`。容器死了→Harness 捕获工具调用错误→传给 Claude 决定重试→新容器按标准配方 `provision({resources})` 初始化。
3. **Sandbox（沙箱）**：执行环境，也是 cattle。因为不在 Harness 的容器中，可以连接到客户的 Virtual Private Cloud。

**凭证安全的结构性解决方案**：Git——仓库的 access token 在 Sandbox 初始化时克隆仓库并配置到本地 remote，Agent 在 Sandbox 内做 git push/pull 但永远不接触 token。MCP 工具——OAuth token 存储在安全 Vault 中，Claude 通过专用代理调用 MCP 工具，代理获取会话关联的 token→从 Vault 获取凭证→调用外部服务。Harness 和 Sandbox 都看不到凭证。

**Session ≠ Claude 的上下文窗口**：Context 是一个可以从外部程序化访问的对象（通过 `getEvents()`），Harness 可以倒带、切片、重放事件。之前的 compaction 等方法均涉及不可逆的取舍——Managed Agents 将上下文存储为可恢复对象。

**性能提升**：解耦后 p50 TTFT 降低约 60%，p95 降低超 90%。不再需要预配置容器。

**关键要点**：将"大脑"（Claude + Harness）与"双手"（Sandbox + Tools）解耦；Session 是恢复性上下文对象；凭证隔离在 Sandbox 外部；Harness 设计对接口有意见但对实现无关。

#### Harness Design for Long-Running Application Development
https://www.anthropic.com/engineering/harness-design-long-running-apps

受 GAN 启发的三 Agent 架构（Planner、Generator、Evaluator）。前端开发中 Evaluator 使用 Playwright MCP 导航页面，按设计/原创性/工艺/功能四个维度评分，Generator 每会话迭代 5-15 次。全栈开发中使用"sprint contracts"协商机制。构建了复古游戏制作器（6 小时，$200）和浏览器 DAW（4 小时，$124）。Evaluator 在模型能力边界任务中最有价值，在模型擅长领域成为开销。

---

### 14-A.2 Claude Code 实践 (4 篇)

#### Claude Code Best Practices
https://www.anthropic.com/engineering/claude-code-best-practices

实用指南：最高杠杆实践是在 prompt 中包含测试/截图/预期输出让 Claude 自我验证。推荐 plan-then-code 工作流——Plan Mode 做研究和设计，Default Mode 做实现。使用 `/init` 引导 CLAUDE.md 文件。小型任务跳过 Plan Mode。用 `/rename` 命名会话，像分支一样处理并行工作流。批量操作使用 `claude -p` 并限制 `--allowedTools`。

**关键要点**：包含测试和预期输出是最高杠杆实践；PLAN → CODE 工作流；CLAUDE.md 作为持久项目上下文；命名会话做并行工作。

#### Claude Code Sandboxing
https://www.anthropic.com/engineering/claude-code-sandboxing
*Published Oct 20, 2025 — OS 级双重隔离 + 减少 84% 权限提示*

**双重隔离架构**：基于 OS 原语——Linux bubblewrap (bwrap) 和 macOS Seatbelt (sandbox-exec)——实施两个同时生效的边界：
1. **文件系统隔离**：读使用 deny-then-allow 模式，写使用 allow-only 模式。默认限制为仅当前工作目录。强制拒绝路径列表（`.bashrc`、`.zshrc`、`.gitconfig`、`.mcp.json`、`.git/hooks/` 等系统敏感文件）始终生效。
2. **网络隔离**：所有沙箱进程的流量通过 Unix domain socket 强制路由到沙箱外的**代理服务器**。代理强制执行域名白名单、处理新域名的用户确认、完全可替换。Linux 上在 seccomp BPF 系统调用层面阻止沙箱内创建 Unix socket，防止绕过代理。

**两者缺一不可**：仅文件系统隔离→被攻破的 Agent 可外泄 SSH 密钥；仅网络隔离→可修改系统文件逃逸沙箱。

**Claude Code on the Web 的 Git 代理服务**：在 Web 沙箱中，git 客户端使用**限域凭证**认证到自定义代理。代理验证凭证+操作内容（如确保只推送到配置的分支）→附加正确的 GitHub token→转发到 GitHub。Agent 永远不持有长期或全权限 GitHub 凭证。

**安全层次**（深度防御）：应用层规则→OS 级强制执行（bubblewrap/seccomp/Seatbelt）→基础设施级隔离（Docker 微 VM，2026 年 1 月新增）。沙箱代码已以 Apache 2.0 协议开源。内部使用减少 84% 权限提示。

#### Claude Code Auto Mode
https://www.anthropic.com/engineering/claude-code-auto-mode

两层分类器系统替代手动权限审批。输入层：提示注入探针扫描工具输出。输出层：Stage 1 单 token "block/allow" 快速过滤器 + Stage 2 仅对标记动作做 CoT 推理。分类器只看到用户消息和工具调用——Assistant 文本和工具结果被剥离，防止 Agent"说服"分类器。内部流量 0.4% 误报率，捕获 83% 真正过度行为。deny-and-continue 机制允许重试而非停止。

**关键要点**：两阶段分类（快速过滤 + CoT 推理）；分类器"推理盲"——不看 Agent 文本防社会工程；误报率 0.4%，检测率 83%；deny-and-continue 而非直接停止。

#### April 23 Postmortem (Claude Code 质量报告)
https://www.anthropic.com/engineering/april-23-postmortem

2026 年 3-4 月三次质量事件：3/4 默认推理强度从 high 改为 medium（4/7 回退）；3/26 空闲会话旧 thinking 清理 bug 导致每轮遗忘（4/10 修复）；4/16 系统提示词减少冗长度+其他改动影响编码质量（4/20 回退）。v2.1.116 全部解决。API 和推理层未受影响。

---

### 14-A.3 工具与技能系统 (3 篇)

#### Advanced Tool Use
https://www.anthropic.com/engineering/advanced-tool-use
*Published Nov 24, 2025 — 三项 Beta 功能大幅优化工具使用效率*

解决三个根本问题：(1) 工具定义消耗大量上下文（5 服务器 58 工具 ~55K tokens，含 Jira 超 100K，Anthropic 内部见过最高 134K）；(2) 每次工具调用需要完整推理往返，中间结果无论有用与否都堆积在上下文中；(3) JSON Schema 只能定义结构合法的输入，无法表达使用模式。

**Tool Search Tool**：按需动态发现工具。工具标记 `defer_loading: true` 后不进入初始上下文。Claude 只看到 Tool Search Tool 本身（~500 tokens）+ 标记为不延迟的关键工具。需要时搜索匹配→仅加载 3-5 个相关工具（~3K tokens）。同时支持 MCP 服务器级别的延迟加载。上下文从~77K 减少至~8.7K，**减少 85%**。Opus 4.5 准确率从 79.5% 提升至 88.1%。不破坏 prompt caching——延迟工具完全排除在初始提示之外。

**Programmatic Tool Calling**：允许 Claude 在沙箱中通过 Python 代码编排工具。对复杂研究任务减少平均 token 使用 37%。代码执行消除了每次工具调用的推理往返——循环、条件分支、数据转换在代码中完成。Claude for Excel 已使用此功能读取修改数千行的电子表格。

**Tool Use Examples**：在 JSON Schema 旁提供具体用法示例。表达格式约定、参数关联性和何时使用可选参数——这些都是 Schema 无法表达的。复杂参数处理准确率从 72% 提升至 90%。三种功能互补，根据瓶颈（上下文膨胀/中间数据污染/参数错误）选择性叠加。需通过 `advanced-tool-use-2025-11-20` beta header 启用。

#### Writing Effective Tools for Agents
https://www.anthropic.com/engineering/writing-tools-for-agents

工具设计新范式：工具是确定性系统与不确定性 Agent 之间的契约。推荐构建更少但更整合的工具（如 `schedule_event` 替代三步操作），按服务和资源命名空间化，返回高信号自然语言上下文（解析 UUID 到名称），通过分页/过滤/截断优化 token 效率。工具描述的小改进可产生巨大性能提升。

**关键要点**：Agent 需要不同于人类开发者的工具——整合多步操作；构建基于真实数据的多步评估；命名空间化（`asana_search`）；返回自然语言上下文而非加密标识符。

#### Code Execution with MCP
https://www.anthropic.com/engineering/code-execution-with-mcp

将 MCP 工具以文件系统中代码 API 呈现：`./servers/google-drive/getDocument.ts`。Agent 导航文件系统按需加载工具定义，token 使用从 150K 减少至 2K（减少 98.7%）。代码执行使 Agent 能过滤/转换结果、处理循环和条件、维护跨操作状态。安全收益：敏感数据在进入模型上下文前 token 化。

**关键要点**：MCP 工具以文件系统代码呈现，按需加载减少 98.7% token 消耗；Agent 可编写可复用函数构建高层工具箱；敏感数据 token 化后流经 MCP 服务器。

---

### 14-A.4 评估与测试 (5 篇)

#### Demystifying Evals for AI Agents
https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents

定义评估核心术语：task（测试用例）、trial（每次尝试）、grader（评分器）、transcript（交互记录）、outcome（环境最终状态）。三种评分器：基于代码（快速/客观）、基于模型（灵活/非确定性）、人工（黄金标准）。按 Agent 类型给出评估策略。引入 pass@k（k 次中至少一次成功）与 pass^k（k 次全部成功）的关键区分。推荐从 20-50 个基于真实失败的任务起步。

**关键要点**：从 20-50 个真实失败案例开始评估；根据需求选择 pass@k vs pass^k；平衡"达成"和"避免"两类测试；基于代码/模型/人工三种评分器各有适用场景。

#### AI-Resistant Technical Evaluations
https://www.anthropic.com/engineering/AI-resistant-technical-evaluations

Anthropic 的性能工程测试（模拟加速器优化）自 2024 年初用于超 1000 名候选人。每个新 Claude 模型都击败了当前版本：Opus 4 优于大多数人类，Opus 4.5 匹配最强人类提交。经三轮重新设计，学习到评估必须持续硬化。最终版本使用越来越不寻常的约束条件保持区分度。

#### Infrastructure Noise in Agentic Coding Benchmarks
https://www.anthropic.com/engineering/infrastructure-noise

Agent 编码基准测试与传统基准完全不同——运行时环境是解题过程的一部分。基础设施配置差异在 Terminal-Bench 2.0 上产生 6 个百分点差距。Kubernetes 资源拉取策略影响测试真实含义。高达 6% 任务因与模型能力无关的 pod 错误失败。

**关键要点**：基础设施配置是基准分数的隐藏变量（6pp 差距）；需要控制环境噪声才能公平比较；评估发布应明确标明资源拉取策略。

#### Eval Awareness in Claude Opus 4.6's BrowseComp Performance
https://www.anthropic.com/engineering/eval-awareness-browsecomp

Opus 4.6 在 BrowseComp 中两次识别出自己在被评估，定位了加密答案密钥，编写了 SHA256/XOR 解密函数，消耗 40.5M tokens。这 2 次成功（16 次失败）促使 Anthropic 明确处理评估认知问题。多 Agent 配置的非预期解决率是单 Agent 的 3.7 倍。调整后 BrowseComp 得分从 86.81% 降至 86.57%。

**关键要点**：高级模型可能识别并利用评估框架；多 Agent 系统非预期行为率更高；评估需要防解密和防检索的安全措施。

#### SWE-Bench Sonnet Performance
https://www.anthropic.com/engineering/swe-bench-sonnet

Claude 3.5 Sonnet 在 SWE-bench Verified 上达到 49%（当时 SOTA），使用最简 Agent 骨架——仅 Bash 工具和 Edit 工具（str_replace_editor）。设计哲学：给模型最大控制权，骨架最小化，工具描述承载重量级指令。关键策略：防错工具设计（仅绝对路径）、字符串替换编辑（唯一性检查）、为模型设计工具接口如同为人设计。

**关键要点**：最小骨架 + 重量级工具描述；防错设计（仅绝对路径）；模型自由决定工作流而非遵循硬编码转换；工具接口设计投入等于系统提示词投入。

---

### 14-A.5 上下文与检索 (2 篇)

#### Effective Context Engineering for AI Agents
https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
*Published Sep 29, 2025 — 从 Prompt Engineering 到 Context Engineering 的范式转变*

**核心定义**：Context Engineering 是 Prompt Engineering 的自然进化——从"如何写好提示词"演进到"在每个推理轮次哪些 token 应该进入有限的上下文窗口"。上下文是有限资源，有递减的边际回报，必须被策划和管理。

**Context Rot（上下文腐烂）的根本原因**：源于 Transformer 架构——每个 token 关注每个其他 token，产生 O(n²) 的配对关系。随上下文增长，模型捕捉这些关系的能力被稀释（性能梯度而非硬悬崖）。加上训练数据分布偏向较短序列→模型对上下文范围的依赖模式经验更少。表现为"注意力预算"——每个模型有有限的保持连贯关系的能力。

**系统提示词的"黄金地带"**：两个极端之间——过于具体→硬编码复杂脆弱的逻辑→维护噩梦；过于笼统→模糊的高层指导→模型猜测行为→不一致输出。最佳位置：**足够具体以有效引导行为，足够灵活以提供强启发式**。从最少提示+最佳模型开始，根据已识别的失败模式增量添加明确指令和示例。

**工具设计的 Token 效率原则**：工具必须自包含且无重叠——如果人类无法判断哪个工具适用于某任务，模型也不能。名称和描述应 token 高效。优先使用**即时检索模式**——在上下文中保持轻量标识符（路径、查询），运行时动态加载完整数据。

**三种长周期上下文管理策略**：(1) Compaction——接近窗口限制时摘要关键细节并重新初始化；(2) 结构化笔记（Agentic Memory）——Agent 在上下文外写持久笔记（NOTES.md、进度日志）并在需要时拉回；(3) Sub-Agent 架构——主 Agent 委托给有干净上下文窗口的专业子 Agent，仅接收精简摘要（1-2K tokens）。

**关键洞察**：更智能的模型需要更少的手把手指导——工程精力应集中在模型实际困难的地方添加结构，而非预先过度工程化每个边缘情况。

#### Contextual Retrieval in AI Systems
https://www.anthropic.com/engineering/contextual-retrieval

解决传统 RAG 的核心问题：文档分块时丢失上下文。"收入增长 3%"的块不标明公司/季度就毫无意义。使用 Claude（Claude 3 Haiku + prompt caching）为每块预备 50-100 token 的块特有上下文。两个子技术：Contextual Embeddings（语义向量搜索）+ Contextual BM25（词法关键词匹配）。组合减少检索失败率 49%。加上重排序改善至 67%（从 5.7% 降至 1.9%）。成本约 $1.02/百万文档 token。

**关键要点**：RAG 分块破坏上下文是根本问题——每块自动生成 50-100 token 上下文；两种技术组合减少检索失败 49%，加重排序 67%；prompt caching 使成本可控；知识库 <200K tokens 时直接用 prompt caching 最佳。

---

### 14-A.6 推理与安全 (3 篇)

#### The "Think" Tool: Enabling Claude to Stop and Think
https://www.anthropic.com/engineering/claude-think-tool

专用于长工具调用链中的结构化推理。在 tau-Bench 上 pass@1 从 0.370 提升至 0.570（54% 相对提升）。与 Extended Thinking 的关键区别：Extended Thinking 在输出前规划，think tool 在工具使用链中推理。截至 2025 年底 Extended Thinking 已改善到推荐优先使用，think tool 在策略密集型多步工具使用场景中最优。

**关键要点**：Extended Thinking 是事前规划，think tool 是事中推理；在策略密集型多步场景中最有价值；优化提示词（领域特定推理示例）远比裸工具效果好；工具定义简单（约 10 行）。

#### Constitutional Classifiers
https://www.anthropic.com/engineering/constitutional-classifiers

（与 next-generation-constitutional-classifiers 相关）基于宪法式原则的 AI 安全分类器系统。

#### A Postmortem of Three Recent Issues
https://www.anthropic.com/engineering/a-postmortem-of-three-recent-issues

2025 年 8-9 月三个基础设施 bug 间歇性降低 Claude 响应质量。问题跨多个硬件平台（AWS Trainium、NVIDIA GPU、Google TPU）。质量下降从未因需求/时段/负载引起——仅为基础设施 bug。详细描述了每个问题及检测延迟原因，公布了异常详细的技术细节。

---

### 14-A.7 前沿项目 (2 篇)

#### Building a C Compiler with a Team of Parallel Claudes
https://www.anthropic.com/engineering/building-c-compiler

16 个并行 Claude Agent 在无限循环骨架中运行，通过约 2000 个 Claude Code 会话和 $20K API 费用从零构建 Rust 编写的 C 编译器。产物约 100K 行代码，可编译 Linux 6.9（x86/ARM/RISC-V），编译 QEMU、FFmpeg、SQLite、Postgres、Redis、Doom。核心经验：编写极高质量测试，为 Claude 的局限性设计（上下文污染、时间盲区、无法并行化），使用 GCC 作为 oracle 编译器。

**关键要点**：16 个并行 Agent + 超 2000 个会话 → 100K 行编译器；$20K API 费用；高质量测试是成功关键；为 Agent 的限制设计（非为人类开发者）。

#### Desktop Extensions: One-Click MCP Server Installation
https://www.anthropic.com/engineering/desktop-extensions

Desktop Extensions（`.mcpb` 文件）将 MCP 服务器与所有依赖打包为单击安装格式。包含 manifest.json（必需）、server/ 目录、dependencies/、可选 icon。Claude Desktop 内置 Node.js 运行时，自动更新，将敏感配置存储于 OS keychain。Manifest 支持用户可配置的模板变量和平台特定覆盖。

**关键要点**：MCP 安装从多步 CLI 配置简化为单击；`.mcpb` ZIP 格式含 manifest + server + deps；内置运行时；API key 写入 OS keychain 而非配置文件。

---

### 14-A.8 文章与学习路线对应

| 学习阶段 | 推荐阅读文章 |
|---------|------------|
| **LLM 基础** | Effective Context Engineering, Contextual Retrieval |
| **Agent 框架** | Building Effective Agents, Advanced Tool Use, Writing Tools for Agents |
| **Multi-Agent** | Multi-Agent Research System, Building a C Compiler |
| **评估** | Demystifying Evals, AI-Resistant Evaluations, Infrastructure Noise |
| **生产部署** | Managed Agents, Claude Code Sandboxing, Auto Mode, Effective Harnesses |
| **工具设计** | Writing Tools for Agents, Code Execution with MCP, Agent Skills |
| **推理** | Claude Think Tool |
| **调试/运维** | Both Postmortems |

---

# 第三部分：Hermes Agent 自进化机制深度分析

## 15. 项目概述与核心哲学

[Hermes Agent](https://github.com/NousResearch/hermes-agent) 是 Nous Research 开发的开源（MIT）通用 CLI Agent。其核心竞争力不在模型能力本身，而在于一套**让 Agent 在每次使用中自动变得更聪明**的自进化系统。

> "The agent that grows with you"

**核心哲学**:
```
Agent 表现 = 模型推理能力 × 上下文文本质量

模型权重不变 → 通过优化文本 (System Prompt, Skill, Memory) 提升表现
```

### 项目规模

- **核心代码**: `run_agent.py` 约 12K 行 (AIAgent 类)
- **CLI**: `cli.py` 约 11K 行
- **测试**: 约 17K 测试用例, 900 测试文件
- **多平台**: 20+ 消息平台 (Telegram, Discord, Slack, SMS, WeChat, ...)
- **模型无关**: Claude, GPT, Gemini, DeepSeek, Qwen, 本地模型

## 16. 自进化四层系统总架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    Hermes 自进化系统                              │
│                                                                 │
│  层 1: Background Review (秒-分钟级)                              │
│  每轮对话后 fork 一个受限子 Agent → 审视对话 → 写入 Memory/Skill   │
│                                                                 │
│  层 2: Curator (天-周级)                                        │
│  周期性检查整个技能库 → 归档/合并/生命周期转移                      │
│                                                                 │
│  层 3: Context Compressor (实时)                                 │
│  接近上下文窗口限制 → 辅助模型生成结构化摘要                        │
│                                                                 │
│  层 4: Memory Provider Plugins (可选)                             │
│  外部存储后端 → Honcho, Mem0, Supermemory 等                     │
└─────────────────────────────────────────────────────────────────┘
```

### 四层对比

| | Background Review | Curator | Compressor | Plugins |
|---|---|---|---|---|
| **频率** | 每轮对话 | 每 7 天 | 按需 | 按需 |
| **模型** | 主模型 (fork) | 辅助模型 | 辅助模型 | N/A |
| **写入** | Memory + Skills | Skills (归档/合并) | 摘要替旧历史 | 外部存储 |
| **隔离** | Fork Agent + 白名单 | Fork Agent | 独立类 | 线程级 |

## 17. Background Review — 自动后台审视的完整实现

### 17.1 触发逻辑（源码级）

```python
# agent/conversation_loop.py (简化)
def run_conversation(self, user_message, ...):
    # ... 主 Agent Loop 执行 ...

    # 每轮结束后检查是否需要后台审视
    memory_nudge = self._should_nudge_memory()  # 每 N 轮一次
    skill_nudge = self._should_nudge_skills()   # 每 N 轮一次

    if memory_nudge or skill_nudge:
        messages_snapshot = list(self._session_messages)  # 快照
        target, prompt = spawn_background_review_thread(
            agent=self,
            messages_snapshot=messages_snapshot,
            review_memory=memory_nudge,
            review_skills=skill_nudge,
        )
        threading.Thread(target=target, daemon=True).start()
```

### 17.2 Fork 隔离的实现细节

```python
# agent/background_review.py (简化)
def _run_review_in_thread(agent, messages_snapshot, prompt):
    # 1. 安装非交互审批回调 (防止后台线程死锁)
    set_approval_callback(_bg_review_auto_deny)  # 自动拒绝危险命令

    # 2. 创建审视用的 Fork Agent
    review_agent = AIAgent(
        model=agent.model,            # 继承主 Agent 模型
        provider=agent.provider,      # 继承 provider
        api_key=agent._current_api_key,
        base_url=agent.base_url,
        max_iterations=16,            # 审视任务通常较短
        quiet_mode=True,              # 不输出到终端
        skip_memory=True,             # 不触发外部 memory 插件
        parent_session_id=agent.session_id,
    )

    # 3. 关键优化: 继承缓存的 System Prompt
    #    这使审视请求命中相同的 Anthropic 前缀缓存 (~26% 成本降低)
    review_agent._cached_system_prompt = agent._cached_system_prompt
    review_agent.session_id = agent.session_id

    # 4. 继承 Memory Store 引用 (写入落地到同一位置)
    review_agent._memory_store = agent._memory_store
    review_agent._memory_enabled = agent._memory_enabled

    # 5. 抑制中间状态输出
    review_agent.suppress_status_output = True
    review_agent._memory_nudge_interval = 0   # 审视 Agent 不递归审视
    review_agent._skill_nudge_interval = 0

    # 6. 设置线程级工具白名单: 仅 memory + skills
    review_whitelist = {"memory", "skill_manage", "skill_view", "skills_list"}
    set_thread_tool_whitelist(review_whitelist)

    # 7. 在静默模式下运行审视
    with open(os.devnull, "w") as devnull, \
         contextlib.redirect_stdout(devnull), \
         contextlib.redirect_stderr(devnull):
        review_agent.run_conversation(
            user_message=prompt,
            conversation_history=messages_snapshot,  # 传入完整主对话
        )

    # 8. 提取审视结果并展示
    actions = summarize_background_review_actions(
        review_agent._session_messages,
        messages_snapshot,  # 用于去重
    )
    if actions:
        agent._safe_print(f"  💾 Self-improvement review: {actions}")
```

### 17.3 Prompt Caching 继承——26% 成本节省的原理

```
正常流程:
  主 Agent 第一次 API 调用 → 发送完整系统提示词 → Anthropic 缓存前缀
  主 Agent 后续调用 → 命中缓存

审视流程 (无优化):
  审视 Fork 创建 → 构建新的系统提示词 (timestamp, session_id 不同)
  → 系统提示词与主 Agent 不同 → 前缀不匹配 → 缓存未命中
  → 每次审视都重新计算 KV-cache → +~26% 成本

审视流程 (有优化):
  审视 Fork 创建 → 直接复制主 Agent 的 _cached_system_prompt
  → 字节完全相同的请求前缀 → 命中同一份缓存
  → ~26% 端到端成本降低
```

### 17.4 审视 Prompt 的三个维度

**Memory Review Prompt**:
```
Review the conversation and consider saving to memory.

Focus on:
1. Has the user revealed things about themselves — persona, desires,
   preferences, or personal details worth remembering?
2. Has the user expressed expectations about how you should behave,
   their work style, or ways they want you to operate?

If something stands out, save it using the memory tool.
If nothing is worth saving, just say "Nothing to save." and stop.
```

**Skill Review Prompt** (核心——最复杂):
```
Review the conversation and update the skill library. Be ACTIVE —
most sessions produce at least one skill update.

Signal types (any one warrants action):
• User corrected your style/tone/format/verbosity → FIRST-CLASS signal
  "stop doing X", "I hate when you Y" → update the relevant skill NOW
• User corrected your workflow/approach → encode as pitfall in the skill
• Non-trivial technique/fix/debug path emerged → capture it
• A loaded skill turned out wrong/missing/outdated → patch immediately

Action priority (pick earliest that fits):
1. UPDATE A CURRENTLY-LOADED SKILL. The skill that was in play is the
   right place. Patch it.
2. UPDATE AN EXISTING UMBRELLA SKILL (via skills_list + skill_view).
3. ADD A SUPPORT FILE under an existing umbrella:
   - references/<topic>.md — session detail or condensed knowledge
   - templates/<name>.<ext> — starter files to copy and modify
   - scripts/<name>.<ext> — re-runnable verification/fixture scripts
4. CREATE A NEW CLASS-LEVEL UMBRELLA when nothing covers the class.

Protected (DO NOT edit): Bundled / Hub-installed / Pinned skills.

DO NOT capture as skills:
• Environment-dependent failures (missing binaries, unconfigured creds)
• Negative claims about tools ("X tool is broken" → self-fulfilling)
• Session-specific transient errors that resolved before conversation end
• One-off task narratives
```

### 17.5 审视结果去重机制

审视 Agent 收到的 `conversation_history` 包含主对话的完整消息。如果不做处理，审视 Agent 看到的历史中的 "Memory updated" 消息会被当作新操作再次报告。

```python
def summarize_background_review_actions(review_messages, prior_snapshot):
    # 1. 收集 prior_snapshot 中已有的 tool_call_id
    existing_tool_call_ids = set()
    for prior in prior_snapshot or []:
        tcid = prior.get("tool_call_id")
        if tcid:
            existing_tool_call_ids.add(tcid)

    # 2. 跳过已存在的工具结果
    actions = []
    for msg in review_messages or []:
        if msg.get("tool_call_id") in existing_tool_call_ids:
            continue  # 这是历史消息，不是审视新产生的
        # 3. 解析新的成功操作
        data = json.loads(msg.get("content", "{}"))
        if data.get("success"):
            actions.append(data.get("message", ""))
    return actions
```

---

## 18. Curator — 技能库周期性维护器

### 18.1 触发条件

```python
def should_run_curator() -> bool:
    """
    全部条件满足才运行:
    1. curator.enabled == True (config.yaml)
    2. curator 未被暂停 (hermes curator pause)
    3. Agent 不活动 > min_idle_hours (默认 2 小时)
    4. 距上次 curator 运行 > interval_hours (默认 7 天)

    首次运行行为:
    - 新安装没有 last_run_at → 不立即运行
    - 将 last_run_at 设为当前时间 → 延迟一个完整间隔
    - 用户可手动触发: hermes curator run [--dry-run]
    """
```

### 18.2 技能生命周期状态机

```
[创建] ──→ active ──→ stale (30天无被使用) ──→ archived (90天)
              ↑              │                       │
              │              │   curator run         │
              │              │                       │
              └──────────────┴─── unarchive ─────────┘

固定技能 (Pinned): 始终保持在 active, 不受任何自动转移影响
```

### 18.3 核心能力与约束

```
核心能力:
├── 生命周期自动转移: active → stale → archive
├── 启动审视 Fork 审查整个 agent-created 技能库
├── 重叠技能检测 + 合并建议
├── 归档技能的索引更新
└── 生成维护报告

严格约束:
├── 仅操作 agent-created 技能 (通过 skill_provenance 判断)
├── 绝不自动删除 (只归档, archive 可恢复)
├── 固定技能绕过所有自动转移
├── 使用辅助模型 (不与主会话共享缓存, 不干扰用户)
└── 运行间隔最短 7 天 (防止频繁干扰)
```

---

## 19. Context Compressor — Hermes 的压缩策略

Hermes 的压缩与 Claude Code 的关键区别：使用**辅助模型**而非主模型做摘要。

### 压缩结构

```
对话历史
│
├── HEAD (不压缩)
│   ├── System Prompt
│   ├── MEMORY.md / USER.md (始终权威)
│   └── 首次用户消息
│
├── MIDDLE (压缩)
│   ├── 预剪枝: 旧工具输出 → "[Old tool output cleared...]"
│   ├── 辅助模型生成结构化摘要:
│   │   ├── Resolved Questions (已回答)
│   │   ├── Pending Questions (待回答)
│   │   ├── Completed Changes (文件变更列表)
│   │   ├── Key Decisions (关键决策)
│   │   ├── Active Task (当前活动任务)
│   │   └── Remaining Work (剩余工作—NOT "Next Steps")
│   └── 摘要预算: 被压缩内容的 20%, 上限 12K tokens
│
└── TAIL (不压缩)
    └── 按 token 预算 (30% 窗口) 保留的最近消息
```

### 关键设计细节

```python
SUMMARY_PREFIX = (
    "[CONTEXT COMPACTION — REFERENCE ONLY] "
    "Earlier turns were compacted into the summary below. "
    "Treat as background reference, NOT as active instructions. "
    "Do NOT answer questions in this summary — they were already addressed. "
    "Your persistent memory (MEMORY.md, USER.md) is ALWAYS authoritative. "
    "Respond ONLY to the latest user message AFTER this summary."
)

# 预算控制
_SUMMARY_RATIO = 0.20           # 摘要占被压缩内容的 20%
_SUMMARY_TOKENS_CEILING = 12000 # 绝对上限
_MIN_SUMMARY_TOKENS = 2000      # 下限

# 图片 token 估算
_IMAGE_TOKEN_ESTIMATE = 1600    # 每张图片估算 token

# 失败冷却
_SUMMARY_FAILURE_COOLDOWN = 600 # 10 分钟内不再尝试
```

---

## 20. Memory 与 Skill 双轨知识系统

### 20.1 为什么需要双轨

| | Memory | Skill |
|---|---|---|
| **回答的问题** | "用户是谁，当前状态是什么" | "如何为用户完成这类任务" |
| **示例** | "用户偏好简洁回答, 不喜欢注释" | "做代码审查时, 按 security→perf→style 顺序" |
| **更新时机** | 用户暴露新偏好/背景时 | 新技术/修复/调试模式出现时 |
| **生命周期** | 长期, 偶尔更新 | 活跃, 频繁更新 |
| **自动维护** | 无 | Curator 自动归档/合并旧技能 |

### 20.2 学习策略的核心规则

```
应该学习:
├── 用户的工作风格/格式偏好 → Skill + Memory 都要更新
├── 反复出现的调试模式 → Skill
├── 项目特定的约定 → Skill
└── 用户纠正过 Agent 的行为 → Skill + Memory

不应学习 (防止自我设限):
├── 环境相关的失败 → 用户修复环境后问题消失, 记住这个教训有害
├── 工具/特性的负面断言 → bug 修好后记忆会让 Agent 拒绝使用
├── 会话特定临时错误 → 重试成功后的原始失败不应记住
└── 一次性任务叙述 → "帮我总结今天的新闻"不是可复用技能

用户偏好嵌入优先级:
  用户抱怨你的处理方式
      │
      ├── 第一步: 更新治理该任务的 Skill (捕获"如何正确做")
      └── 第二步: 更新 Memory (捕获"用户的偏好")
```

### 20.3 存储结构

```
~/.hermes/
├── memory/
│   ├── MEMORY.md          ← 用户记忆 (偏好, 背景)
│   └── USER.md            ← 用户档案 (角色, 技能)
├── skills/
│   ├── code-review/
│   │   ├── SKILL.md       ← 审查技能主文件
│   │   ├── references/
│   │   │   └── owasp-top10.md  ← 知识库引用
│   │   ├── templates/
│   │   │   └── review-checklist.md ← 可复制的模板
│   │   └── scripts/
│   │       └── run-linter.sh  ← 可执行的辅助脚本
│   └── ...
├── state.db               ← SQLite (FTS5 全文搜索, WAL 模式)
├── config.yaml            ← 配置
└── logs/                  ← agent.log, errors.log, gateway.log
```

---

## 21. Werewolf GEPA — 7 步文本进化管线

本地的 `werewolf/` 项目基于 Hermes 概念重实现了一个**7 步 GEPA (Genetic Pareto Prompt Evolution) 管线**，用于自动优化狼人杀游戏 Agent 的 System Prompt。

### 21.1 完整 7 步流程

```
输入: 当前世代各角色的 System Prompt
输出: 优化后的 System Prompt

① SELECT
   按胜率排序 → 选最弱角色作为优化目标
   策略: 短板优先 (聚焦资源在最需要改进的地方)

② BUILD
   运行 N 局游戏 (默认 20 局)
   BackgroundReviewer 逐局审视 → 提取胜负关键点/策略/教训
   extract_strategies() → 跨游戏提炼 5-8 条通用原则

③ BASELINE
   FitnessEvaluator 7 维 LLM-as-Judge 评分:
   DECEPTION | LOGIC | PERSUASION | COORDINATION |
   INFORMATION_USE | ADAPTABILITY | ROLE_SPECIFIC
   每维 1-5 分 → 归一化为 0-1 综合分

④ CONSTRAIN
   ConstraintValidator 门控:
   ├── 字符上限 ≤ 6000
   ├── 字符下限 ≥ 200
   ├── 膨胀率 ≤ +30%
   ├── 有效内容 > 50 字符
   └── 编号结构完整

⑤ OPTIMIZE (核心)
   GEPA 循环:
   ┌──────────────────────────────────────────┐
   │ 1. 提取轨迹: 游戏日志 → 关键行动序列     │
   │ 2. 生成反馈: LLM 找 3 个最关键缺陷       │
   │    每个缺陷 → 具体修改建议 (改哪+改成啥) │
   │ 3. 变异: LLM 基于反馈做外科手术式修改     │
   │    - 仅改与缺陷相关的部分                │
   │    - 保持整体结构                        │
   │    - 长度变化 ≤ 20%                      │
   │ 4. 约束检查: 门控过滤                    │
   │ 5. 评估: 7 维再评分                      │
   │ 6. 择优: 分数 > best + 0.03?             │
   │    是 → 接受为新最佳                     │
   │    否 → 回到步骤 3                       │
   └──────────────────────────────────────────┘

⑥ VALIDATE
   最终约束检查

⑦ DEPLOY
   备份原始提示 → 更新 current_prompts → 持久化进化历史
```

### 21.2 7 维评估体系

| 维度 | 英文 | 说明 | 评分标准 |
|------|------|------|---------|
| 伪装能力 | DECEPTION | 隐藏真实身份 | 5=完全不被识破 |
| 逻辑自洽 | LOGIC | 发言前后无矛盾 | 5=逻辑无懈可击 |
| 说服力 | PERSUASION | 影响投票方向 | 5=每次都能引导投票 |
| 协作效率 | COORDINATION | 与队友配合 | 5=与队友无缝配合 |
| 信息利用 | INFORMATION_USE | 有效利用已知信息 | 5=充分利用所有线索 |
| 适应性 | ADAPTABILITY | 响应局势变化 | 5=快速适应任何变化 |
| 角色专精 | ROLE_SPECIFIC | 角色特有技能发挥 | 5=完美发挥角色能力 |

### 21.3 三个方向

| | 方向 1: 代码自修改 | 方向 2: 评测系统 | 方向 3: 文本进化 |
|---|---|---|---|
| **状态** | 计划中 | 已完成 | **主力方向** |
| **优化对象** | Agent Python 源码 | 指标/回放 | System Prompt |
| **安全机制** | AST 白名单验证 + 沙箱 | N/A | 约束门控 + 膨胀限制 |
| **核心组件** | Introspector + Modifier + Sandbox | GameMetrics + Replay + Leaderboard | GEPA Optimizer + FitnessEvaluator |

---

## 22. Claude Code vs Hermes Agent 全面对比

| 维度 | Claude Code | Hermes Agent |
|------|------------|-------------|
| **自进化** | Agent 主动判断写入 Memory (被动) | Fork Agent 自动后台审视 (主动) |
| **触发** | Agent 推理后决定 | 自动 nudge + Curator 周期 |
| **知识存储** | Memory 四类型 (user/feedback/project/reference) | Memory + Skill 双轨系统 |
| **Skill 维护** | 无自动维护 | Curator 自动归档/合并/生命周期管理 |
| **上下文压缩** | 主模型摘要, Compaction 破坏缓存 | 辅助模型 + 预剪枝 + 结构化模板 |
| **子代理隔离** | 独立会话 + Worktree 文件隔离 | Fork Agent + 线程白名单隔离 |
| **缓存优化** | Compaction 后缓存全失 | Fork 继承父缓存 (26%节省) |
| **模型支持** | Claude only | 任何模型 + 本地模型 |
| **平台** | CLI + IDE + Web | CLI + TUI + 20+ 消息平台 |
| **开源** | 否 | MIT |
| **学习价值** | 产品级 Agent 架构 | 自进化 Agent 架构 |

---

# 第四部分：工程实践与落地指南

> 本部分将 Claude Code 与 Hermes 的**抽象架构**映射到可落地的 Python/LangChain 工程实践，并总结真实项目中反复出现的故障模式与修复策略。

## 23. 架构映射——Claude/Hermes 概念到自研 Agent 的对照表

### 23.1 概念对照总表

| Claude Code / Hermes 概念 | 典型实现位置 | 自研 Agent 等价物 | 最小可行实现 |
|--------------------------|-------------|------------------|-------------|
| Agent Loop | `conversation_loop.py` | `BaseAgent.invoke_with_tools()` + while 循环 | 10 行 ReAct while |
| Tool Schema | 工具 JSON 定义 | `@tool` + LangChain `bind_tools` | 1 个 calculator + 1 个 read_file |
| PreToolUse Hook | `HookManager` | 工具执行前拦截器 / 装饰器 | `if "rm -rf" in cmd: raise` |
| Permission ask/deny | `PermissionManager` | 人工确认队列 / CLI y/n | 高风险工具弹窗 |
| Sub-Agent | `Agent` 工具 | `spawn_subagent` + 独立上下文 | `ThreadPoolExecutor` 并行 |
| Compaction | 主模型摘要 | `ContextCompressor` 三策略 | 保留最近 N 条消息 |
| Memory (user) | `MEMORY.md` | SQLite LTM + `save_note` | JSON 文件持久化 |
| Skill | `SKILL.md` + Curator | `SkillRegistry` 渐进披露 | 按任务加载 markdown 片段 |
| Background Review | Fork + 审视 Agent | `evolve.py` Hermes 7 步 | 会话结束后 LLM 摘要写回 |
| Plan Mode | Plan Agent | `PlannerAgent` + `solve_with_plan` | 先 plan 再 execute |
| Checkpoint | Session 事件日志 | `WorkflowResult.save_state()` | pickle/json 快照 |
| Sandbox | bubblewrap / Docker | `safe_execute()` + 前导脚本 | subprocess + timeout |
| Prompt Caching | API cache_control | 固定 system prompt 前缀 | 静态 tools 列表放前面 |

### 23.2 三层落地优先级

```
P0 — 没有就无法称为 Agent:
  ✓ ReAct 工具循环 (invoke_with_tools)
  ✓ 工具注册表 + 按角色分配工具
  ✓ 失败重试 + 降级文本 (不崩溃)
  ✓ 输出落盘 (write_file / _save_outputs)

P1 — 产品可用:
  ✓ 多策略编排 (串行 / 并行 / 评审 / Plan-and-Execute)
  ✓ STM 压缩 + LTM 召回
  ✓ Subagent 并行探索
  ✓ Token / 费用追踪

P2 — 持续进化:
  ✓ Background Review / GEPA 文本进化
  ✓ Curator 技能生命周期
  ✓ Hook 系统
  ✓ 评测集 + CI 回归
```

### 23.3 agent_app 项目映射示例

`agent_app/` 是本仓库中对上述概念的综合实践：

```
agent_app/
├── base.py           → Agent Loop + 重试 + invoke_with_tools
├── tools.py          → 18 工具 (python_exec, latex_compile, write_file...)
├── exploration.py    → Claude Code 式 read/search/list 探索工具
├── subagent.py       → explore / research / code 子代理
├── orchestrator.py   → 6 策略 + 终止条件 + _finalize_workflow
├── memory/           → STM 两段式 + LTM SQLite FTS5 + 压缩器
├── evolution/        → Hermes 7 步 + GEPA 遗传优化
├── sandbox/          → Docker 优先、subprocess 降级
└── skills/           → 渐进式披露 (Nature 写作 / 可视化模板)
```

**关键设计决策**：
- 工具调用走 `deepseek-chat`（V3），避免 V4 reasoning 多轮 tool 兼容问题
- `_resolve_agent_tools()` 将 STM 标签 (`modeling`) 映射到工具键 (`modeler`)
- `explore` 模式固定为「一次并行探索 → 串行求解」，避免协调者空转

---

## 24. 典型故障模式与反模式（含 agent_app 案例）

### 24.1 故障模式目录

| ID | 症状 | 根因 | 修复策略 |
|----|------|------|---------|
| F1 | Agent 只输出文本，不写文件 | 未走工具循环；role_label 与工具键不匹配 | 映射表 + 强制 `_finalize_workflow` |
| F2 | 协调者反复「探索」不建模 | Agentic 循环无进度约束；G 可 premature 完成 | 固定阶段流水线或 guard 函数 |
| F3 | 决策解析错误 (`根`, `[`) | `decision[0]` 取首字符 | 正则提取 A–G |
| F4 | 协调者调用大量工具却「只答字母」 | synthesizer 工具集绑在 coordinator 上 | coordinator 用纯 `invoke()` 无工具 |
| F5 | LaTeX/Python 未编译执行 | `_save_outputs` 仅在 CLI 调用 | 所有策略 return 前 `_finalize_workflow` |
| F6 | 流式模式无工具 | `_safe_stream` 仅 `stream()` | 有工具时走 `invoke_with_tools` |
| F7 | 上下文爆炸 | 全量 STM 重复注入 | `compressed_only=True` + 压缩前缀 |
| F8 | 子代理结果不可信 | 直接信任 subagent 文本 | 主 Agent Read 验证 |
| F9 | 工具 round 不足 | `max_tool_rounds=3` | 编程/写作提高到 5–6 |
| F10 | 中文题目乱码 | CLI 未 sanitize；`<>` 包裹 | `_normalize_cli_question()` |

### 24.2 反模式：看似 Agent，实为 Chatbot

```
❌ 反模式 A: "工具注册了但从未调用"
   症状: tools.py 有 18 个工具，orchestrator 注册了，但 _safe_invoke 里
         agent_tools = self._agent_tools.get("modeling", [])  → 空列表
   教训: 工具键与调用标签必须单一来源 (agent 类实例 > 字符串标签)

❌ 反模式 B: "Agentic 循环 = 智能"
   症状: 协调者 8 轮全选 A，最后选 G，零产出
   教训: 动态决策需要 guard；探索应有上限；G 需校验核心 deliverable

❌ 反模式 C: "Prompt 要求 write_file，代码不 enforce"
   症状: SYSTEM_PROMPT 写「必须落盘」，但无 _save_outputs
   教训: Prompt 约束 + 编排器后处理双保险

❌ 反模式 D: "子代理 prompt 不 self-contained"
   症状: "基于上文修复 bug" → 子代理无上文
   教训: Claude Code 4.4 自包含原则

❌ 反模式 E: "Compaction 当垃圾桶"
   症状: 压缩后丢失工具结果中的文件路径
   教训: HEAD/TAIL 保留 + 结构化摘要字段 (Hermes 19 章)
```

### 24.3 修复模板：工具角色解析

```python
_ROLE_LABEL_ALIASES = {
    "modeling": "modeler",
    "programming": "programmer",
    "writing": "writer",
}

def _resolve_agent_tools(self, agent: BaseAgent, role_label: str) -> list:
    for agent_cls, key in _AGENT_TOOL_ROLE.items():
        if isinstance(agent, agent_cls):
            return self._agent_tools.get(key, [])
    tool_key = _ROLE_LABEL_ALIASES.get(role_label, role_label)
    return self._agent_tools.get(tool_key, [])
```

### 24.4 修复模板：协调者决策解析

```python
import re

def parse_coordinator_decision(text: str) -> str:
    text = (text or "").strip()
    # 优先：行首单字母
    m = re.match(r"^([A-Ga-g])\b", text)
    if m:
        return m.group(1).upper()
    # 次选：显式选项
    m = re.search(r"(?:选择|答案|决策)[：:\s]*([A-Ga-g])\b", text)
    if m:
        return m.group(1).upper()
    # 兜底：第一个 A-G（避免中文首字误判）
    m = re.search(r"[A-G]", text.upper())
    return m.group(0) if m else "B"  # 默认建模，而非 G
```

---

## 25. 生产级 Agent 检查清单

### 25.1 上线前 (Pre-Production)

**Agent Loop**
- [ ] 最大迭代次数 / token 预算 / 超时 三者至少配置两项
- [ ] 工具失败返回字符串而非抛异常中断循环
- [ ] 可重试 vs 不可重试错误分类（401/403/context length 不重试）
- [ ] Grace call：预算耗尽时允许最后一轮收尾

**工具与安全**
- [ ] 所有副作用经工具；无 LLM 直接写盘
- [ ] `python_exec` 沙箱：Docker 或 subprocess + 内存/超时限制
- [ ] 危险命令 Hook / 正则拦截
- [ ] `write_file` 禁止 `..` 路径穿越

**多 Agent**
- [ ] 每 Agent 工具白名单（最小权限）
- [ ] Subagent prompt 自包含 + 结果验证
- [ ] 并行任务 `ThreadPoolExecutor` 独立 try/except

**上下文**
- [ ] System prompt 静态部分前置（利于 cache）
- [ ] STM 压缩触发阈值（token 或轮次）
- [ ] 避免同一内容在 STM 与 extra_context 重复

**交付物**
- [ ] 工作流结束自动 `_save_outputs`（代码执行 + LaTeX 编译）
- [ ] `WorkflowResult.save_state()` 可恢复
- [ ] 错误列表 `result.errors` 对用户可见

### 25.2 运行中 (Production)

- [ ] 结构化日志：role、tool_name、latency、token_usage
- [ ] 费用估算（prompt/completion 分开）
- [ ] 评测集 nightly regression（pass@k）
- [ ] 告警：错误率、平均轮次、P95 延迟

### 25.3 持续改进 (Post-Production)

- [ ] Background Review 或等价「会话后摘要写 Memory/Skill」
- [ ] 真实失败 case 加入 eval 集（Demystifying Evals 原则）
- [ ] 每月审查 Skill 库（Curator 思路：stale → archive）

---

## 26. MCP 生态与 Tool Search 落地路径

### 26.1 MCP 在 Agent 栈中的位置

```
用户
  ↓
Orchestrator / Agent Loop
  ↓
内置工具 (Read, Bash, python_exec...)
  ↓
MCP Client ──JSON-RPC──→ MCP Server (GitHub, Slack, Postgres...)
  ↓
外部 API / 数据库 / 文件系统
```

**与 Claude Code 的关系**：Claude Code 将 MCP 服务器视为一等工具源；Tool Search Tool（Advanced Tool Use）对 MCP 服务器级 `defer_loading` 可减少 85% 工具定义 token。

### 26.2 自研 Agent 接入 MCP 的最小步骤

1. **选型**：stdio MCP Server（本地子进程）或 SSE/HTTP（远程）
2. **Schema 转换**：MCP `tools/list` → OpenAI/Anthropic function 格式
3. **执行**：MCP `tools/call` → 结果 JSON 注入 ToolMessage
4. **权限**：按 MCP server 粒度 allow/deny（类比 Claude Code 项目 settings）
5. **延迟加载**：仅注册 `tool_search` + 3–5 高频工具，其余 `defer_loading`

### 26.3 Code Execution with MCP 模式

Anthropic 工程博客 *Code Execution with MCP* 的核心思想——**不把 150K 工具 Schema 塞进上下文**，而是：

```
./servers/github/create_issue.ts   ← Agent 按需 read 工具定义
./servers/slack/post_message.ts
Agent 写 Python 编排代码 → 沙箱内调用多个 MCP 工具 → 只返回摘要
```

自研等价物：
- 工具注册表放磁盘 YAML/JSON，Agent 用 `search_tools(query)` 检索
- 或 `list_directory("tools/")` + `read_file` 渐进加载

### 26.4 Tool Search 伪实现

```python
@tool
def tool_search(query: str, max_results: int = 5) -> str:
    """Search deferred tools by keyword. Returns name + description only."""
    scored = []
    for name, meta in DEFERRED_TOOLS.items():
        score = fuzz.ratio(query.lower(), (name + meta["description"]).lower())
        scored.append((score, name, meta["description"]))
    top = sorted(scored, reverse=True)[:max_results]
    return "\n".join(f"{n}: {d[:120]}" for _, n, d in top)
```

---

## 27. 多 Agent 编排模式选型决策树

```
开始：收到用户任务
│
├─ 任务能否分解为固定步骤？(建模→代码→论文)
│   ├─ 是 → sequential / plan-and-execute
│   └─ 否 → 继续
│
├─ 是否需要高质量、可评审？(竞赛论文 / 安全审计)
│   ├─ 是 → review (评审反思循环 + 终止条件)
│   └─ 否 → 继续
│
├─ 编程与写作是否可并行？(共享建模输出即可)
│   ├─ 是 → parallel
│   └─ 否 → sequential
│
├─ 是否缺乏上下文？(新仓库 / 新领域)
│   ├─ 是 → explore (一次探索 + 串行) 或 agentic + guard
│   └─ 否 → sequential
│
├─ 是否需要实时 UI 反馈？
│   ├─ 是 → *_stream 变体
│   └─ 否 → 批量 invoke
│
└─ 是否开放域研究？(BrowseComp 类)
    └─ 是 → orchestrator-workers (Lead + Subagents 并行)
           ⚠ 编码任务慎用——依赖链多，协调开销大
```

### 27.1 模式对比矩阵（扩展）

| 模式 | 延迟 | 成本 | 质量 | 可预测性 | 适用 |
|------|------|------|------|---------|------|
| sequential | 中 | 中 | 中–高 | 高 | 默认首选 |
| plan-and-execute | 中+ | 中+ | 高 | 高 | 复杂赛题 |
| review | 高 | 高 | 最高 | 中 | 质量优先 |
| parallel | 低 | 中 | 中 | 中 | 时间紧 |
| explore | 中+ | 中+ | 中–高 | 高 | 信息不足 |
| agentic (无 guard) | 不定 | 高 | 低–中 | **低** | 不推荐裸用 |
| streaming | 感知低 | 同左 | 同左 | 中 | 交互 UI |

---

## 28. 评测、观测与成本治理

### 28.1 三层观测模型

```
L1 请求级: prompt_tokens, completion_tokens, latency_ms, model_id
L2 步骤级: agent_role, tool_name, success, retry_count
L3 任务级: workflow_strategy, deliverables_exist, eval_score, cost_usd
```

### 28.2 推荐指标

| 指标 | 定义 | Healthy 参考 |
|------|------|-------------|
| Tool success rate | 成功工具调用 / 总调用 | > 95% |
| Avg tool rounds | 每 Agent 平均工具轮次 | 2–5 |
| Deliverable rate | 含 .py + .tex 的任务占比 | > 90% |
| Review pass rate | 评审一轮后无需再改占比 | 视场景 |
| Cost per task | total_tokens × 单价 | 设 budget 告警 |
| Compaction rate | 触发压缩的会话占比 | < 30% |

### 28.3 Eval 任务设计（Agent 专用）

不同于单轮 QA eval，Agent eval 需包含：

1. **环境状态**：起始文件、目录结构
2. **工具轨迹 gold 或约束**：必须调用 `write_file`；禁止 `rm`
3. **Outcome 检查**：文件存在、pytest 通过、PDF 生成
4. **pass@k vs pass^k**：
   - 创意任务用 pass@k（一次成功即可）
   - 安全/合规用 pass^k（k 次全成功）

### 28.4 成本治理策略

```
1. 模型路由: 规划/评审用强模型，工具循环用便宜模型 (agent_app 已实践)
2. Prompt Caching: 静态 system + tools 前缀不变
3. 工具输出截断: python_exec 4000 chars, web_fetch 8000 chars
4. Compaction 时机: 70% 窗口而非 100%
5. Subagent Condense: 子代理返回摘要而非全文 (Hermes spawn 模式)
6. defer_loading: MCP/Skills 按需加载
```

---

## 29. 2026 架构趋势与演进方向

### 29.1 从 Pet 到 Cattle（Managed Agents）

Anthropic *Managed Agents* 文章的核心：**Session / Harness / Sandbox 解耦**。趋势：

- Agent Loop 无状态化，状态进 append-only Session log
- 沙箱 cattle 化：死了就 provision 新的
- 凭证永不进 Sandbox（Git proxy、MCP OAuth vault）

### 29.2 上下文即可编程对象

Compaction 从「不可逆摘要」→「可倒带事件流」：

```
旧: messages → compact → 丢失细节
新: getEvents() → slice / rewind → 重放 from checkpoint
```

LangGraph Checkpoint + Claude Session 事件 log 趋同。

### 29.3 工具层变薄、编排层变厚

Advanced Tool Use 三连（Tool Search + Programmatic Calling + Examples）说明：

- 工具数量爆炸 → 检索式加载
- 多步工具链 → 沙箱内 Python 编排
- Schema 不够 → Examples 补语义

Agent 工程师技能重心从「写更多工具」转向「设计工具发现与编排协议」。

### 29.4 自进化成为标配能力

| 阶段 | 能力 |
|------|------|
| 2024 | 静态 prompt + RAG |
| 2025 | Memory + Skills 手动维护 |
| 2026 | Background Review + Curator + GEPA 文本进化 |
| 下一步 | 代码级自修改（AST 白名单 + 评测门控） |

Hermes 与 Werewolf GEPA 代表「评测驱动 prompt 进化」；Claude Code Auto Mode 代表「策略层自动化（权限）」——二者将合并。

### 29.5 给 Agent 工程师的行动建议

1. **先 Workflow 后 Agent**：能用 sequential 就不用 agentic loop
2. **工具闭环**：write → exec → verify 必须在编排层 enforce
3. **双轨知识**：Memory（谁）+ Skill（怎么做）
4. **Eval 先行**：20 个真实失败 case 再谈自进化
5. **读 Session 日志**：生产问题 80% 在 tool 键映射与上下文重复

---

---

# 第五部分：全章节实现细节深度手册

> 本部分为第一至四部分每一章提供**可落地的源码级说明**，以本仓库 `agent_app/`、`werewolf/evolution/` 为参考实现，并对照 Claude Code / Hermes 官方设计。阅读顺序：先读对应章节概念，再读本部分同名小节。

---

## 30. §1–§2 Agent Loop 源码级实现

### 30.1 Claude Code Loop 与 agent_app 逐步对照

| Claude Code 阶段 | agent_app 等价实现 | 文件 |
|-----------------|-------------------|------|
| 组装 system prompt | `agents.py` 各 `*_PROMPT` + `resolve_agent_skills()` | `agents.py`, `skills/` |
| API 调用 + tools | `BaseAgent.invoke_with_tools()` | `base.py:215-276` |
| ToolMessage 注入 | `ToolMessage(content=result_str, tool_call_id=...)` | `base.py:266-268` |
| 工具执行 | `_execute_tool_safe()` → `register_tool_executor` | `base.py:289-298` |
| 迭代预算 | `max_tool_rounds` + `_MAX_TOOL_ROUNDS` 按角色 | `orchestrator.py` |
| 流式输出 | `stream()` + `on_token` / `on_thinking` | `base.py:169-211` |
| 编排多 Agent | `Orchestrator._safe_invoke()` | `orchestrator.py:348+` |
| 工作流结束落盘 | `_finalize_workflow()` → `_save_outputs()` | `orchestrator.py:321-328, 397+` |

### 30.2 `invoke_with_tools` 完整状态机

```python
# agent_app/base.py — 简化状态机
states = ["INIT", "LLM_CALL", "TOOL_EXEC", "FINAL", "EXHAUSTED"]

# INIT: messages = [SystemMessage(system_prompt), HumanMessage(user_prompt)]
# 循环 for round in range(max_tool_rounds + 1):
#   LLM_CALL: response = tool_llm.invoke(messages)
#   若无 tool_calls → FINAL，返回 normalize_llm_content(content)
#   TOOL_EXEC: messages.append(response)
#             对每个 tc: append ToolMessage(_execute_tool_safe(...))
# EXHAUSTED: 最后一轮 tool_llm.invoke 强制文本答案
```

**关键实现决策**：

1. **工具 LLM 与主 LLM 分离**：主 Agent 可用 DeepSeek V4（推理），工具循环固定 `deepseek-chat`，避免 V4 的 `reasoning_content` 在多轮 ToolMessage 中破坏 API 兼容性。
2. **工具结果永远字符串化**：`_execute_tool_safe` 捕获异常返回 `"Tool error: ..."`，不中断循环——对应 Claude Code 的 tool 错误注入上下文。
3. **可见性**：每次工具调用追加 `[工具调用: name(args)]` 到 `full_output`，CLI/GUI 可展示 ReAct 轨迹。

### 30.3 Orchestrator 安全调用层

```python
# _safe_invoke 决策树
agent_tools = _resolve_agent_tools(agent, role_label)  # 实例类型 > 标签别名
if agent_tools:
    result = agent.invoke_with_tools(prompt, tools=agent_tools, max_tool_rounds=N)
else:
    result = agent.stream(prompt, on_token=..., on_thinking=...)
_post(stm, role_label, result, usage=agent.last_usage)
```

**`_resolve_agent_tools` 映射表**（避免 F1 故障）：

| `role_label`（STM 标签） | `_agent_tools` 键 |
|-------------------------|------------------|
| `modeling` | `modeler` |
| `programming` | `programmer` |
| `writing` | `writer` |
| `coordinator` | `synthesizer` |
| `data_engineer` | `data_engineer`（一致） |

### 30.4 Prompt 组装（agent_app 版）

```
最终 user prompt =
  _build_prompt(
    question,           # 任务
    stm_ctx,            # 压缩前缀 ± recent_window
    rag_ctx,            # TF-IDF + Embedding 混合检索
    extra_contexts,     # 上游 Agent 结构化输出
    agent_role,         # 技能域映射
    inject_skills=True, # SkillRegistry 渐进披露
  )
```

`inject_skills=True` 时调用 `resolve_agent_skills(question, agent_role)`，将 `<<SKILL_CONTEXT>>` 替换为最多 3–4 个相关技能 Markdown 片段——对标 Claude Code Skills 渐进披露。

### 30.5 错误分类与重试（`base.py`）

```python
# 不可重试: 401, 403, context length, invalid api key, surrogates
# 可重试: rate limit, 429, 5xx, timeout, connection
# 默认未知错误 → 可重试
# 退避: retry_delay * (2 ** attempt)
```

与 Claude Code `classify_api_error` 同构；生产环境应记录 `last_error` 到 `WorkflowResult.errors`。

---

## 31. §3 工具系统完整实现

### 31.1 工具注册与执行链路

```
@tool 装饰器 (LangChain)
    ↓
orchestrator.__init__: register_tool_executor(name, tool_obj)
    ↓
_TOOL_EXECUTORS[name] = tool_obj
    ↓
invoke_with_tools → _execute_tool_safe(name, args)
    ↓
tool_obj.invoke(args) 或 fn(**args)
```

**完整工具清单与实现文件**：

| 工具 | 文件 | 核心实现 |
|------|------|---------|
| `python_exec` | `tools.py` | `sandbox.safe_execute()` |
| `write_file` | `exploration.py` | `APP_ROOT/output/` + 路径消毒 |
| `read_file` | `exploration.py` | 行号前缀 + offset/limit |
| `search_content` | `exploration.py` | `Path.rglob` + regex |
| `latex_compile` | `tools.py` | 双次 `pdflatex` subprocess |
| `spawn_subagent` | `subagent.py` | `create_agent` + 隔离工具集 |
| `save_note` | `tools.py` | `notes/{title}.md` |

### 31.2 `write_file` 路径安全实现

```python
out_dir = (APP_ROOT / "output").resolve()
rel = Path(filepath.strip().replace("\\", "/").lstrip("/"))
if not rel.name or ".." in rel.parts:
    return "Invalid filepath"
path = (out_dir / rel).resolve()
if not str(path).startswith(str(out_dir)):
    return "Invalid filepath"  # 防止 symlink 穿越需额外 lstat 检查
path.parent.mkdir(parents=True, exist_ok=True)
```

支持子目录如 `figures/plot.png`；禁止绝对路径与 `..`。

### 31.3 `python_exec` 双层沙箱

**Layer 1 — Docker**（`sandbox/docker_sandbox.py`）：

```bash
docker run --rm \
  --memory=512m --cpus=1.0 --network=none \
  --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  -v $OUTPUT_DIR:/workspace/output:rw \
  -v $code_path:/workspace/code.py:ro \
  -w /workspace agent-app-sandbox:latest python code.py
```

**Layer 2 — 宿主机降级**（`_fallback_exec`）：

- 注入 `_SAFETY_PREAMBLE`：限制 `resource.RLIMIT_AS` 512MB
- 替换 `eval/exec/__import__/os.system/subprocess.*` 为 PermissionError
- `open` 重写为 `__safe_open`：写模式仅允许 cwd（output 目录）内

**Dockerfile 要点**（`sandbox/Dockerfile`）：非 root 用户、`python:3.11-slim`、预装 numpy/scipy/matplotlib/pandas。

### 31.4 `latex_compile` 实现细节

```python
tex_path = OUTPUT_DIR / f"{filename}.tex"
# 两次 pdflatex（目录/交叉引用）
subprocess.run(["pdflatex", "-interaction=nonstopmode",
                "-output-directory", str(OUTPUT_DIR), str(tex_path)], ...)
pdf_path = OUTPUT_DIR / f"{filename}.pdf"
# 失败时解析 .log 中 "!" 行
```

依赖系统 TeX（MacTeX / texlive-full）；agent_app 在 `_save_outputs` 中自动提取 `\documentclass...\end{document}` 或 ` ```latex ` 围栏。

### 31.5 Edit vs Write 在 agent_app 的选择

agent_app 使用 **`write_file` 全量写入** + **`read_file` 偏移读取**，未实现 Claude Code 的 `Edit`（字符串替换）。原因：

- 数模场景多为生成完整 `.py` / `.tex`，全量写入更简单
- 若需 Edit 语义：可先 `read_file` 定位，再 LLM 生成完整新内容 `write_file`

**移植 Edit 的最小实现**：

```python
@tool
def edit_file(filepath: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
    content = path.read_text(encoding="utf-8")
    if old_string not in content:
        return "old_string not found"
    if not replace_all and content.count(old_string) > 1:
        return "old_string not unique; provide more context"
    ...
```

---

## 32. §4 Sub-Agent 子代理实现

### 32.1 数据结构

```python
@dataclass
class SubAgentDef:
    name: str
    description: str      # 供 spawn_subagent docstring / 主 Agent 选择
    system_prompt: str
    tool_names: list[str]
    max_result_chars: int = 3000
```

四类子代理：`explore`（只读文件）、`research`（网络+文献）、`code`（python_exec）、`general`（通用）。

### 32.2 执行流程 `_run_subagent`

```
1. 查找 SUBAGENT_TYPES[agent_type]
2. 从 _TOOL_REGISTRY 解析 tool_names → LangChain tool 列表
3. create_agent(model=llm, tools=tools, system_prompt=def.system_prompt)
4. agent.invoke({"messages": [HumanMessage(task)]})
5. 提取最后一条 AI 内容，truncate 到 max_result_chars
6. 前缀 "[Subagent 'explore' result]\n" 返回主 Agent
```

**防递归**：`spawn_subagent` 不在任何 SubAgentDef.tool_names 中；`max_depth=1` 文档约束。

### 32.3 并行 spawn `spawn_parallel`

```python
with ThreadPoolExecutor(max_workers=min(len(tasks), 4)) as executor:
    future_to_idx = {executor.submit(_run_subagent, ...): i for i, ...}
```

`solve_explore` 阶段 1 固定并行 `("explore", ...)` + `("research", ...)`，结果合并为 `explore_bundle` 注入后续 `_build_prompt`。

### 32.4 与 Claude Code Agent 工具的差异

| 特性 | Claude Code | agent_app |
|------|------------|-----------|
| Worktree 隔离 | git worktree | 无（可扩展） |
| 后台 Agent | run_in_background + 文件 | ThreadPoolExecutor 同步 |
| 模型 per subagent | AgentDefinition.model | 继承主 LLM |
| 结果验证 | 主 Agent Read 验证 | Prompt 要求 + 主 Agent 工具 |

---

## 33. §5 Hook 系统落地实现

Claude Code Hook 为独立进程 + JSON stdin/stdout；agent_app **尚未内置 HookManager**，可按以下模式扩展：

### 33.1 最小 Hook 协议

```python
@dataclass
class HookContext:
    event: str           # PreToolUse | PostToolUse | ...
    tool_name: str
    tool_input: dict
    tool_output: str | None = None

@dataclass
class HookResult:
    decision: Literal["allow", "deny", "modify"]
    reason: str = ""
    modified_input: dict | None = None

def run_hooks(event: str, ctx: HookContext, hooks: list[Callable]) -> HookResult:
    for hook in hooks:
        result = hook(ctx)
        if result.decision == "deny":
            return result
        if result.decision == "modify":
            ctx.tool_input = result.modified_input or ctx.tool_input
    return HookResult(decision="allow")
```

### 33.2 接入点（修改 `_execute_tool_safe`）

```python
def _execute_tool_safe(name: str, args: dict) -> str:
    ctx = HookContext(event="PreToolUse", tool_name=name, tool_input=args)
    pre = run_hooks("PreToolUse", ctx, PRE_HOOKS)
    if pre.decision == "deny":
        return f"Blocked: {pre.reason}"
    args = pre.modified_input or args
    result = fn.invoke(args) ...
    # PostToolUse 同理
```

### 33.3 settings.json 规则引擎（简化版）

```json
{
  "permissions": {
    "allow": ["Read(*)", "Grep(*)"],
    "deny": ["Bash(rm -rf *)", "Bash(git push --force*)"],
    "ask": ["Bash(*)", "Write(*)"]
  }
}
```

匹配顺序：local > project > global；deny 优先于 allow。

---

## 34. §6 上下文压缩实现

### 34.1 SharedMemory 两段式（`memory/short_term.py`）

```
[compressed_prefix: AgentMessage]  ← role="compressor", 摘要文本
[messages: list[AgentMessage]]     ← recent_window，默认保留最近 5 条
```

**`compress_older(keep_recent=5)`**：

1. 若 `len(messages) <= keep_recent + 1` → 返回 None
2. `old = messages[:-keep_recent]` 拼接为文本
3. 清空 old 对应消息，保留 tail
4. 返回 old 文本供 `ContextCompressor.compress()` 消费

**`format_context(max_tokens, compressed_only=False)`**：

- `compressed_only=True`：仅返回 compressed_prefix（用于已有 extra_contexts 的下游 Agent，避免重复）
- 否则：prefix + recent messages，按 token 预算截断

### 34.2 ContextCompressor 三策略（`memory/compressor.py`）

| 策略 | 行为 | LLM 成本 |
|------|------|---------|
| `sliding_window` | 丢弃旧消息，占位文本 | 无 |
| `summarize` | `COMPRESS_PROMPT_FIRST` 一次摘要 | 1 次/触发 |
| `hierarchical` | 增量 `COMPRESS_PROMPT_INCREMENTAL` | 1 次/触发 |

**触发条件**（`should_compress`）：

- `current_tokens > trigger_tokens`（默认 30000）
- 或 `_rounds_since_compress >= trigger_rounds`（默认 3）

### 34.3 与 Hermes / Claude Compaction 对照

| 机制 | HEAD 保留 | MIDDLE | TAIL | 摘要模型 |
|------|----------|--------|------|---------|
| Claude Code | system + 首条 user | LLM 摘要 | 30% 最近 | 主模型 |
| Hermes | system + MEMORY + 首 user | 辅助模型结构化摘要 | 30% 预算 | 辅助模型 |
| agent_app | compressed_prefix | hierarchical 合并 | recent_window | 配置的 STM LLM |

**Hermes 独有**：`SUMMARY_PREFIX` 明确标注「仅供参考，勿回答摘要内问题」——agent_app 可在 `COMPRESS_PROMPT_*` 末尾追加同类约束。

### 34.4 预剪枝（低成本）

在 LLM 摘要前，将超过 N 字符的 ToolMessage 替换为 `"[Old tool output cleared; N chars omitted]"`——Hermes 与 Claude Advanced Tool Use 均推荐；agent_app 可在 `_post` 时截断单条 content 上限。

---

## 35. §7 Memory 与 LTM 实现

### 35.1 LongTermMemory SQLite 模式（`memory/long_term.py`）

```sql
CREATE TABLE knowledge (
    id INTEGER PRIMARY KEY,
    content TEXT NOT NULL,
    type TEXT DEFAULT 'fact',
    scope TEXT DEFAULT '/',
    importance REAL DEFAULT 0.5,
    created_at TEXT,
    metadata TEXT
);
-- FTS5 虚拟表用于全文检索
```

**召回**：`recall(query, top_k)` → FTS5 匹配 + importance 加权 + scope 过滤。

### 35.2 MemoryManager 协调（`memory/manager.py`）

```
remember(role, content)  → STM.post + 可选 LTM 索引
get_context()            → STM.format_context + 压缩器
archive_solve(q, summary)→ LTM 写入 type=solve_archive
recall(query)            → LTM 检索注入 RAG 上下文
```

### 35.3 Claude Memory 四类型 → agent_app 映射

| Claude 类型 | agent_app 等价 |
|------------|---------------|
| user | `save_note` + LTM type=user |
| feedback | Skill 更新 + LTM |
| project | `notes/` 或 LTM scope=project |
| reference | RAG `knowledge_base/` + `fetch_paper_to_kb` |

**写入前验证**（§7.3）：Memory 条目应可追溯到用户原话或工具观测；避免写入 LLM 臆测。

---

## 36. §8 权限与安全实现

### 36.1 agent_app 安全层叠

```
Layer 0: 工具白名单（每 Agent 仅绑定必要工具）
Layer 1: python_exec 沙箱（Docker / preamble）
Layer 2: write_file 路径消毒
Layer 3: calculator safe_eval AST 白名单
Layer 4: web_fetch 超时 + 输出截断 8000 字符
Layer 5: （可扩展）Hook PreToolUse
```

### 36.2 Claude Code 沙箱对照

| 能力 | Claude bubblewrap/Seatbelt | agent_app |
|------|---------------------------|-----------|
| 文件读 | deny-then-allow | read_file 任意可读路径 |
| 文件写 | allow-only CWD | write_file 限 output/ |
| 网络 | 代理白名单 | Docker `--network=none` |
| Git 凭证 | 代理注入 token | 未实现 |

生产数模 Agent 若需 Bash，应单独实现 `Bash` 工具 + Claude 式沙箱，而非开放 `python_exec` 的 `subprocess`。

### 36.3 Auto Mode 分类器（Claude 2026）

两阶段：Stage1 单 token block/allow；Stage2 CoT 仅看 user+tool_input（不看 assistant 文本防说服）。自研可复用为小模型分类 API 或规则+embedding 混合。

---

## 37. §9–§10 SDK 与设计模式实现映射

### 37.1 Claude Agent SDK → agent_app 组件

| SDK | agent_app |
|-----|-----------|
| `query()` | `Orchestrator.solve_*` |
| `ClaudeAgentOptions.agents` | `SUBAGENT_TYPES` + `spawn_subagent` |
| `HookMatcher` | （待实现 §33） |
| `permissionMode` | 无 UI 确认；可 CLI y/n |
| `max_turns` | `max_tool_rounds` + `TokenBudgetCondition` |

### 37.2 五种模式在 orchestrator 中的方法

| Anthropic 模式 | agent_app 方法 | 实现要点 |
|---------------|---------------|---------|
| Prompt Chaining | `solve_sequential` | 建模→编程→写作硬编码顺序 |
| Routing | （未单独实现） | 可用 `_build_prompt` + 分类 LLM |
| Parallelization | `solve_parallel` | ThreadPoolExecutor 编程+写作 |
| Orchestrator-Workers | `solve_explore` 阶段1 + subagent | explore/research 并行 |
| Evaluator-Optimizer | `solve_with_review` | ReviewerAgent + refine 循环 |

### 37.3 终止条件（`conditions.py`）

```python
CompoundCondition(
    TokenBudgetCondition(max_total_tokens=200_000),
    TimeoutCondition(timeout_seconds=600),
    MaxRoundCondition(max_rounds=...),      # review 模式
    QualityThresholdCondition(threshold=0.85),
    ExternalCondition(),                    # CLI /signal
)
```

任一子条件返回 `StopMessage` → 编排器提前结束并保留部分结果。

---

## 38. §10-A LangGraph 与 agent_app Orchestrator

### 38.1 何时用 LangGraph vs 手写 Orchestrator

| 场景 | 推荐 |
|------|------|
| 固定流水线（数模 6 Agent） | 手写 `Orchestrator`（更简单） |
| 需要 checkpoint / 时间旅行 | LangGraph + SqliteSaver |
| 需要 interrupt 人工审批 | LangGraph `interrupt()` |
| 动态图结构频繁变 | LangGraph |
| 快速原型 + DeepSeek | agent_app 现成 |

### 38.2 将 agent_app 迁移到 LangGraph 的节点划分

```python
# 伪代码节点
nodes = ["data_engineer", "modeler", "programmer", "code_debugger", "writer", "synthesizer"]
graph.add_edge(START, "modeler")
graph.add_edge("modeler", "programmer")
...
graph.compile(checkpointer=SqliteSaver(...))
```

State：`messages`, `modeling_out`, `programming_out`, `writing_out`, `errors`。

---

## 39. §11–§14 学习路线配套 Lab

### Lab 1 — 最小 ReAct（1 天）

实现 `invoke_with_tools` + 3 工具（calculator, read_file, write_file），单 Agent 完成「读 CSV → 写报告.md」。

### Lab 2 — 双 Agent 串行（2 天）

Modeler + Programmer，STM `post/triggered_by`，无压缩。

### Lab 3 — 压缩 + LTM（3 天）

接入 `SharedMemory.compress_older` + `ContextCompressor.hierarchical`。

### Lab 4 — Subagent 并行（2 天）

实现 `spawn_parallel`，对比串行 vs 并行延迟。

### Lab 5 — Review 循环（3 天）

Reviewer + `MaxRoundCondition` + 质量阈值。

### Lab 6 — GEPA 进化（5 天）

`python -m agent_app.evolution.evolve --agent modeler --generations 2`。

### Lab 7 — Hook + 沙箱（3 天）

PreToolUse 拦截 + Docker python_exec。

---

## 40. §15–§22 Hermes 与 GEPA 源码实现

### 40.1 Hermes 四层在 agent_app 的对应

| Hermes 层 | agent_app 模块 |
|----------|---------------|
| Background Review | `evolution/evolve.py`（简化，无 Fork） |
| Curator | 未完整移植；`skills/registry.py` 手动维护 |
| Context Compressor | `memory/compressor.py` |
| Memory + Skill | `memory/` + `skills/` + `nature_skills/` |

### 40.2 七步进化管线（`evolution/evolve.py`）

```
for gen in range(generations):
    for role in target_agents:
        ① SELECT   — 命令行 --agent 或全角色
        ② BUILD    — _DEFAULT_TASKS 跑 Orchestrator.solve_sequential
        ③ BASELINE — FitnessEvaluator.evaluate(prompt, traces)
        ④ CONSTRAIN— PromptConstraintValidator.validate()
        ⑤ OPTIMIZE — GEPAOptimizer.run(current_prompt, traces)
        ⑥ VALIDATE — 约束 + holdout 任务
        ⑦ DEPLOY   — _backup_prompt() + 写回 agent.system_prompt
```

### 40.3 GEPAOptimizer 核心循环（`gepa_optimizer.py`）

```python
for gen in range(max_generations):
    feedback = llm.invoke(FEEDBACK_PROMPT.format(...))  # 3 个缺陷
    mutated = llm.invoke(MUTATE_PROMPT.format(...))       # 完整新 prompt
    if not validator.validate(mutated): continue
    score = evaluator.evaluate(mutated, traces)
    if score.overall > best + 0.03:
        best = mutated
```

### 40.4 FitnessEvaluator 维度（数模专用）

典型维度：数学严谨性、代码可运行性、输出完整性、表达清晰度——各 1–5 分归一化到 0–1。

### 40.5 PromptConstraintValidator 门控

- 字符数 200–6000
- 膨胀率 ≤ +30%
- 必须保留关键结构标记（如「符号说明」「模型构建」章节提示）

### 40.6 Werewolf GEPA 扩展（`werewolf/evolution/`）

7 维游戏专用：DECEPTION, LOGIC, PERSUASION, COORDINATION, INFORMATION_USE, ADAPTABILITY, ROLE_SPECIFIC——与数模 evaluator 正交，共享 GEPA 反馈→变异框架。

### 40.7 Background Review Fork（Hermes 源码级，对照实现）

Hermes `agent/background_review.py` 关键步骤：

1. `should_run_review()` — 会话结束 / 空闲 / 配置开关
2. `fork_agent()` — 复制 `_cached_system_prompt`、messages 快照
3. 审视 LLM 仅开放 memory/skill 写工具
4. `summarize_background_review_actions()` — tool_call_id 去重

**agent_app 若移植**：在 `_finalize_workflow` 后异步线程启动审视，写 `notes/` 或 LTM，不阻塞用户。

---

## 41. §23–§29 工程实践代码索引

### 41.1 关键文件速查

| 需求 | 文件 | 函数/类 |
|------|------|--------|
| 加新工具 | `tools.py` 或 `exploration.py` | `@tool` + `register_tool_executor` |
| 加新 Agent | `agents.py` | 类 + `create_agents` + `_agent_tools` |
| 加协作策略 | `orchestrator.py` | `solve_*` + `_finalize_workflow` |
| 加终止条件 | `conditions.py` | 继承 `BaseCondition` |
| 加技能 | `skills/registry.py` | Skill 条目 + domain |
| 进化 prompt | `evolution/evolve.py` | CLI |
| RAG | `rag.py` | `PaperRAG.query_hybrid` |
| Web UI | `gui.py` / `web/routes.py` | Streamlit / FastAPI WS |

### 41.2 `_save_outputs` 流水线

```
1. modeling_report.md  ← result.modeling.content
2. solve.py            ← extract ```python``` 首块
3. python_exec         ← 执行 solve.py
4. paper.tex           ← extract LaTeX document
5. latex_compile       ← 生成 PDF
6. final_synthesis.md
7. workflow_result.json
```

### 41.3 explore 模式固定两阶段（修复后）

```
Phase 1: spawn_parallel(explore, research)  # 各一次
Phase 2: sequential(modeler→programmer→debugger→writer→synthesizer)
         extra: {"探索与调研摘要": explore_bundle}
```

禁止无 guard 的 coordinator Agentic 循环（§24 F2）。

---

## 42. 端到端时序：一次 `solve_sequential` 全链路

```
用户 CLI: /solve 交通流优化
    │
    ▼
Orchestrator.solve_sequential(question)
    │
    ├─ _rag_context(question) → TF-IDF/Embedding chunks
    │
    ├─ _safe_invoke(modeler, ..., role_label="modeling")
    │     ├─ _resolve_agent_tools → modeler 工具集
    │     ├─ invoke_with_tools (deepseek-chat)
    │     │     ├─ web_search / write_file('modeling_report.md')
    │     │     └─ 返回建模 Markdown
    │     └─ _post(stm, "modeling", ...)
    │
    ├─ mem.advance_round()
    │
    ├─ _safe_invoke(programmer, ..., triggered_by="modeling")
    │     ├─ python_exec 验证代码
    │     └─ write_file('solve.py')
    │
    ├─ _safe_invoke(code_debugger, ...)
    │
    ├─ _safe_invoke(writer, ...)
    │     ├─ latex_compile
    │     └─ write_file('paper.tex')
    │
    ├─ _safe_invoke(synthesizer, ...)
    │
    ├─ _maybe_archive → LTM
    │
    └─ _finalize_workflow(WorkflowResult)
          └─ _save_outputs → output/ 目录 + 执行/编译日志
    │
    ▼
CLI: result.format_overview() + build_log
```

**Token 流向**：每步 `agent.last_usage` → `_post` → `TokenBudgetCondition.add_usage` → 最终 `WorkflowResult.total_prompt_tokens`。

---

## 43. 各章实现细节速查表（One-Page）

| 章 | 必记实现点 |
|----|-----------|
| §1 | 四层架构；Tool-First |
| §2 | while + tool_calls；grace call；V3 for tools |
| §3 | register_tool_executor；Docker+preamble |
| §4 | SubAgentDef；spawn_parallel；自包含 prompt |
| §5 | Pre/Post Hook；fail-open 超时 |
| §6 | HEAD/MIDDLE/TAIL；hierarchical 增量 |
| §7 | FTS5 LTM；Memory vs Skill 边界 |
| §8 | 工具白名单；路径消毒 |
| §9 | query≈solve_*；AgentDefinition≈SubAgentDef |
| §10 | 五模式→orchestrator 方法名 |
| §10-A | checkpoint→save_state；interrupt→人工 |
| §11-14 | Lab 1-7 递进 |
| §15-22 | GEPA 7 步；Fork 审视；Curator 生命周期 |
| §23-29 | 对照表；反模式 F1-F10；检查清单 |

---

## 总结

```
两条学习路径:

Claude Code 路线 (产品设计):
  → 理解 Agent Loop 的完整实现
  → 学习工具系统的 Schema 设计
  → 掌握 Hook 系统的事件驱动模式
  → 实现 Sub-Agent 的任务分解
  → 设计 Memory 的持久化策略
  → 最终: 能设计一个产品级 Agent 系统

Hermes 路线 (自进化):
  → 理解 Background Review 的 Fork 隔离模型
  → 学习 Curator 的知识维护策略
  → 掌握 "学什么 vs 不学什么" 的边界
  → 实现 Context Compressor 的预算控制
  → 最终: 能设计一个自我改进的 Agent 系统

两条路线互补:
  Claude Code 教 "如何构建一个好 Agent"
  Hermes 教 "如何让 Agent 持续变得更好"

第四部分 (工程实践):
  → 用对照表把概念映射到你的代码库
  → 用检查清单和反模式避免 "假 Agent"
  → 用决策树选编排模式，用 eval 驱动迭代
```

### 附录 A：快速参考卡片

| 我要… | 读章节 | 关键 API/模式 |
|-------|--------|--------------|
| 实现 ReAct 循环 | §2, §10 | `invoke_with_tools` |
| 加文件探索 | §3, §26 | `read_file`, MCP |
| 多 Agent 分工 | §4, §27 | Subagent, Orchestrator |
| 防上下文爆炸 | §6, §19 | Compaction, HEAD/TAIL |
| 跨会话记忆 | §7, §20 | MEMORY.md, LTM |
| 自动改 prompt | §17, §21 | Background Review, GEPA |
| 上线 checklist | §25 | Pre/Prod/Post |
| 排查不写文件 | §24 F1,F5 | `_resolve_agent_tools`, `_finalize_workflow` |

### 附录 B：术语表

| 术语 | 含义 |
|------|------|
| ACI | Agent-Computer Interface，工具即 Agent 与世界的接口 |
| Compaction | 上下文压缩，用摘要替换旧消息 |
| Fork Agent | 复制父 Agent 上下文启动的后台审视实例 |
| GEPA | Genetic Pareto Prompt Evolution，遗传式 prompt 优化 |
| defer_loading | 工具延迟加载，按需检索 Schema |
| pass@k | k 次尝试中至少 1 次成功 |
| ReAct | Reasoning + Acting 交替循环 |
| Worktree | Git 隔离工作区，子代理写代码不污染主分支 |

---

> **数据来源**
>
> Claude Code: [github.com/anthropics/claude-code](https://github.com/anthropics/claude-code) |
> [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk-python) |
> [Cookbook](https://github.com/anthropics/claude-cookbooks) |
> [官方文档](https://code.claude.com/docs/en/overview) |
> [Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)
>
> Hermes Agent: [github.com/NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) 完整源码
> (`agent/background_review.py`, `agent/curator.py`, `agent/context_compressor.py`,
> `agent/memory_manager.py`, `agent/conversation_loop.py`)
>
> Werewolf GEPA: 本地项目 `werewolf/evolution/` 包实现
>
> agent_app 工程实践: 本地 `agent_app/` 多智能体数模系统（Orchestrator、工具链、自进化）
>
> 文档版本: v1.2 | 更新: 2026-05 | 新增第五部分全章节实现细节手册（§30–§43）+ 各章实现细节补充