# AI 狼人杀 — 多智能体博弈系统

基于多 Agent 协作框架，构建能够自主完成信息不对称博弈的狼人杀 Agent Team 系统。每个 Agent 根据其扮演角色拥有独立的目标、策略与行动空间，在严格信息隔离的约束下进行推理、发言与决策。

## 功能概览

- **12 人标准局**：4 狼人 + 4 村民 + 预言家 + 女巫 + 猎人 + 白痴
- **6 个专业 Agent**：每个角色拥有独立的 System Prompt、策略指南和输出格式
- **完整对局引擎**：黑夜/白天流转、狼人共识机制、警长竞选、投票放逐、猎人开枪、白痴翻牌
- **信息隔离**：每个 Agent 只接收其角色有权知晓的信息子集
- **结构化日志**：JSON 完整记录 + Markdown 复盘报告
- **三个进阶方向**：

| 方向 | 说明 |
|------|------|
| ② 评测+复盘+Leaderboard | 多维可量化评测体系，对局复盘归因，跨模型跨版本排行榜 |
| ③ 自进化 Agent | 对局→分析弱点→优化 Prompt→再对局的迭代提升循环 |
| ① 自演化 Agent | Agent 读取自身代码→分析→提出修改→沙箱验证→应用 |

## 项目结构

```
werewolf/
├── __init__.py              # 包入口
├── config.py                # 角色枚举、阶段定义、游戏规则
├── state.py                 # 游戏状态管理 + 信息隔离 context 构建
├── engine.py                # 游戏引擎（行动处理、投票、胜负裁决）
├── llm.py                   # LLM 工厂（DeepSeek）
├── orchestrator.py          # 对局协调器（驱动完整回合流转）
├── memory.py                # 共享记忆（仅公开信息）
├── logger.py                # 结构化日志（JSON + Markdown 复盘）
├── cli.py                   # 命令行入口
│
├── agents/                  # Agent 层
│   ├── base.py              # WerewolfAgent 基类（复用 agent_app BaseAgent）
│   ├── werewolf.py          # 狼人 — 与同伴协商击杀、白天伪装
│   ├── villager.py          # 村民 — 倾听分析、投票识别狼人
│   ├── seer.py              # 预言家 — 查验身份、选择时机跳身份
│   ├── witch.py             # 女巫 — 解药救人、毒药灭狼
│   ├── hunter.py            # 猎人 — 被放逐时开枪带走狼人
│   ├── idiot.py             # 白痴 — 被放逐可翻牌免死
│   └── factory.py           # Agent 工厂函数
│
├── evaluation/              # 进阶 ②：评测系统
│   ├── metrics.py           # 多维指标（投票准确率、存活率、角色效率）
│   ├── replay.py            # 对局复盘（时间线重建、转折点识别）
│   └── leaderboard.py       # 排行榜（跨模型/版本对比）
│
├── evolution/               # 进阶 ③：自进化
│   ├── optimizer.py         # LLM 分析弱点 → 生成改进的 System Prompt
│   ├── tournament.py        # 跨代锦标赛（新旧版本同台竞技）
│   └── tracker.py           # 进化历史追踪（胜率趋势可视化）
│
├── self_modify/             # 进阶 ①：自演化 Agent
│   ├── introspector.py      # AST 解析自身代码、提取方法源码
│   ├── modifier.py          # LLM 提出代码修改 + AST 安全验证
│   └── sandbox.py           # 沙箱隔离测试（胜率门控）
│
├── output/                  # 对局日志、复盘报告
└── data/                    # Leaderboard、进化历史
```

## 安装

```bash
# 1. 安装依赖
pip install langchain langchain-core langchain-deepseek python-dotenv

# 2. 配置 API Key（在项目根目录 .env）
echo 'DEEPSEEK_API_KEY=你的key' > ../.env

# 3. 运行
python -m werewolf.cli
```

## 快速开始

### 运行一局 AI 对战

```python
from werewolf import GameConfig
from werewolf.llm import create_llm
from werewolf.orchestrator import GameOrchestrator

llm = create_llm(temperature=0.7)
config = GameConfig()
orch = GameOrchestrator(llm, config=config, verbose=True)

result = orch.run_game()
print(f"胜者: {result.winner.value}")
print(f"总轮数: {result.total_rounds} 天")
```

### 评测一局对局

```python
from werewolf.evaluation import evaluate_game, GameReplay, Leaderboard

# 评测指标
metrics = evaluate_game(game_log, players)

# 复盘分析
replay = GameReplay("werewolf/output/game_20260512.json")
print(replay.generate_narrative())
print("关键转折点:", replay.find_turning_points())

# 更新排行榜
lb = Leaderboard()
lb.record_game("DeepSeek-V4", "v1.0", result.winner.value, result.total_rounds)
lb.record_game("DeepSeek-V4", "v1.1", result.winner.value, result.total_rounds)
print(lb.report())
```

### 运行自进化

```python
from werewolf.evolution import StrategyOptimizer, EvolutionTournament, EvolutionTracker

# 分析弱点
optimizer = StrategyOptimizer(llm)
weaknesses = optimizer.analyze_weaknesses("狼人", game_logs)

# 优化 Prompt
new_prompt = optimizer.optimize("狼人", current_prompt, metrics, weaknesses)

# 跨代锦标赛验证
tournament = EvolutionTournament(llm, games_per_generation=20)
results = tournament.run_generation({"狼人": new_prompt}, generation_id=1)

# 追踪进化
tracker = EvolutionTracker()
tracker.record_generation(metrics)
print(tracker.improvement_summary())
```

### 运行自演化

```python
from werewolf.self_modify import Introspector, Modifier, Sandbox

# 读取自身代码
intro = Introspector("werewolf/agents/werewolf.py")
source = intro.get_class_source()

# LLM 提出修改
modifier = Modifier(llm)
new_code = modifier.propose_changes(source, "狼人", 0.35, weaknesses, key_events)

# 安全验证
ok, msg = Modifier.validate(new_code)
if ok:
    # 沙箱测试
    sandbox = Sandbox(test_games=5)
    result = sandbox.test(source, new_code, "狼人", 0.35, run_game_fn)
    if result.passed:
        print(f"✓ 修改通过！胜率提升 {result.improvement:+.0%}")
```

## 对局流程

```
黑夜阶段：
  1. 狼人睁眼 → 协商击杀目标（需达成共识）
  2. 预言家睁眼 → 查验一名玩家（狼人/好人）
  3. 女巫睁眼 → 得知今晚被刀玩家 → 决定用药

白天阶段：
  4. 死亡公告（平安夜/死亡名单/女巫救人）
  5. 警长竞选（仅首轮）
  6. 存活玩家按顺序发言
  7. 提名 + 投票放逐
  8. 被放逐者遗言 → 猎人开枪/白痴翻牌
  9. 胜负判定
```

## 信息隔离

每个 Agent 只能访问其角色许可的信息：

| 角色 | 夜晚可见信息 | 白天可见信息 |
|------|-------------|-------------|
| 狼人 | 同伴 ID + 存活列表 + 击杀提名 | 公开信息（同下） |
| 预言家 | 查验历史 + 存活列表 | 公开信息 |
| 女巫 | 被刀玩家 + 药水状态 | 公开信息 |
| 猎人/白痴/村民 | 无（闭眼玩家） | 公开信息 |

**公开信息**（所有存活玩家白天都能看到）：
- 死亡公告历史
- 所有玩家的发言记录
- 投票记录
- 警长身份

## 评测指标

| 维度 | 指标 | 计算方式 |
|------|------|----------|
| 发言质量 | 信息密度、逻辑自洽 | LLM 评分 (1-5) |
| 投票准确率 | 投狼人 vs 投好人的比例 | 投票记录统计 |
| 预言家效率 | 查验狼人率 | 查验历史统计 |
| 女巫效率 | 解药利用率、毒狼率 | 用药记录统计 |
| 伪装能力 | 狼人被首次投票的轮次 | 投票时间线分析 |
| 协作能力 | 狼人首夜击杀收敛速度 | 提名轮数统计 |

## 安全机制（自演化方向）

自演化代码修改的安全保障：

1. **AST 安全检查**：禁止 `eval`/`exec`/`__import__`，禁止导入 `os`/`subprocess`/`sys`
2. **沙箱隔离测试**：修改后的代码先跑 5 局验证
3. **胜率门控**：胜率不降超过 5% 才允许应用修改
4. **单角色变更**：每次只允许修改一个角色（避免并发不可控）
5. **修改历史**：保留所有版本，支持回滚

## 依赖

```
langchain >= 0.3
langchain-core
langchain-deepseek
python-dotenv
```

---

*核心挑战不在 LLM 本身，而在信息不对称下的多智能体博弈机制设计——每个 Agent 必须在有限信息下做出最优决策，同时识别和利用其他 Agent 的信息盲区。*
