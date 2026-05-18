

# 数模多智能体协作系统 — 面试问答详解

> 最后更新：2026-05-18，基于最新架构（token 追踪、终止条件、LLM 记忆索引、流式全策略、PDF 表格/图片提取）

---

## 一、架构设计类

### Q1: 为什么选择多 Agent 协作而不是单个大 Agent 完成所有任务？

**核心论点：分工带来质量提升，而不是简单的任务拆分。**

**1. 上下文窗口压力**

数学建模竞赛是一个信息密度极高的工作流。一个典型的赛题涉及：问题背景（数页文字 + 数据表）、建模假设与变量定义（数十个符号）、数学模型推导（多目标优化、微分方程、概率模型等）、算法实现（Python 代码数百行）、论文写作（通常 20-30 页）。如果全部塞给单一 Agent，即使 DeepSeek-v4-pro 有 128K 上下文，多个子任务的内容混杂在一起，模型容易产生"中段遗忘"——对 prompt 前部的约束注意力衰减，导致输出后半部分质量急剧下降。拆分为多个 Agent，每个只承受自己职责范围内的上下文压力。

**2. 角色混淆问题**

单一 Agent 需要在"严谨的数学推导者"和"流畅的论文写作者"之间反复切换人格。这会导致：
- 建模时语言过于口语化，缺少数学严谨性
- 写作时过度关注公式细节，忽略论文的整体叙事逻辑
- 评审自身输出时缺乏客观性（自己很难发现自己的盲点）

多 Agent 架构中，`ModelerAgent` 的 System Prompt 专注于"变量、约束、优化目标"；`WriterAgent` 则专注"论文结构、摘要撰写、图表设计"。每个角色不会被其他角色的思维模式污染。

**3. 自我纠错能力**

这是多 Agent 设计最关键的价值。`ReviewerAgent` 独立审视建模/编程/写作的输出，它持有完全不同视角的 System Prompt（"发现漏洞和不足"），能够发现单一 Agent 无论如何自我检查都会遗漏的问题。`solve_with_review` 策略中，每阶段"输出→评审→修改"的循环形成质量控制闭环，这是单 Agent 无法做到的。

**4. 可扩展性与可维护性**

如果需要新增"数据预处理 Agent"，只需新增一个 Agent 类并编排进 pipeline。如果是单 Agent 方案，所有职责耦合在一个巨大 prompt 里，修改任何部分都可能产生不可预知的连锁反应。

**代码印证**：`orchestrator.py:78-91` 中 Orchestrator 持有五个独立的 Agent 实例，每个都可以通过 `settings.get_agent_config()` 获取个性化配置（如 temperature），单 Agent 无法做到这种粒度的控制。

---

### Q2: Orchestrator 的四种策略是怎么设计的？各自解决了什么问题？

**策略一：串行流水线 (`solve_sequential`)**

流程：建模 → 编程 → 写作 → 总控整合

每一阶段的输出作为下一阶段的输入上下文。编程需要建模的变量定义和求解思路，写作需要建模方案 + 代码实现的数值结果，总控需要所有前三者的输出来整合方案。这是有向无环图（DAG）中最简单、最可靠的拓扑排序。

适用场景：绝大多数标准赛题，对质量要求与时间要求均衡。

**策略二：深度反思 (`solve_with_review`)**

流程：建模 → 评审 → 修改（循环 max_review_rounds 轮）→ 编程 → 评审 → 修改 → 写作 → 评审 → 修改 → 总控

每个阶段都有质量门控。退出条件是 `"无问题" in review and rnd > 0`——首轮即使评审说"无问题"也会再确认一轮，防止评审 Agent 因"偷懒"给出敷衍的正面评价。后续轮次一旦出现"无问题"就提前终止，避免无效循环浪费 Token。

适用场景：国赛 A 题级别的难题，或方案需要提交给导师审查。

**策略三：快速并行 (`solve_parallel`)**

流程：建模先行 → 编程 + 写作（ThreadPoolExecutor 并行）→ 总控

为什么建模必须先行？因为编程和写作都依赖建模输出（变量定义、模型结构），这是硬依赖。编程和写作之间没有直接依赖——写作可以在建模方案基础上先搭建论文框架，编程同时在跑数值实验，两者互不阻塞。

适用场景：时间紧迫的限时赛，如美赛 4 天 4 夜的最后冲刺阶段。

**策略四：流式输出 (`solve_stream`)**

这不是一种独立的拓扑策略，而是串行模式的传输方式变体。用户通过 `on_modeling_token` 等回调实时看到每个 Agent 生成过程，体验上像看 AI"思考"。对于需要中途干预的场景（比如发现建模方向偏离赛题意图），用户可以在看到建模输出第一段时立即叫停，而不是等全部跑完才发现。

**代码印证**：`orchestrator.py:252-305` 并行策略中，编程和写作通过 `ThreadPoolExecutor(max_workers=2)` 并发执行，建模始终是先行的阻塞步骤。

---

### Q3: SharedMemory 的"两段式"架构是什么？为什么要区分 compressed_prefix 和 recent_window？

**核心设计：压缩前缀 + 最近窗口**

```
[compressed_prefix] ← LLM 增量摘要旧消息（层次合并，不过期）
[recent_window]     ← 最近 5 条原始消息（完整细节，被淘汰旧消息）
```

**设计动机：**

1. **信息不丢失**：普通截断式记忆丢弃旧消息，而两段式将旧消息压缩为摘要永久保留，保留了历史脉络
2. **细节不稀释**：最近窗口始终保留 5 条完整消息，后续 Agent 可以获取关键的最新上下文
3. **增量合并**：再次触发压缩时，已有摘要 + 新积累的旧消息 → LLM 合并为新摘要（`compress_incremental`），不是简单覆盖
4. **Token 预算可控**：`format_context()` 自动控制输出长度，先放压缩前缀，剩余预算给最近消息

**压缩策略选择：**

| 策略 | 方式 | 适用 |
|------|------|------|
| `sliding_window` | 纯粹保留最近 N 条 | 零 LLM 成本 |
| `summarize` | LLM 一次性摘要全部 | 标准场景 |
| `hierarchical` | 增量合并：旧摘要 + 新消息 → 新摘要 | 长对话（默认） |

**代码印证**：`memory/short_term.py:95-120`（`compress_older` + `set_compressed_prefix`）、`memory/compressor.py:90-100`（`_compress_incremental`）。

---

### Q4: 如果要扩展到 20 个 Agent，当前架构有什么问题？你会怎么改？

**当前架构的问题：**

1. **硬编码的线性依赖**：`Orchestrator` 中每种策略的方法都硬编码了 Agent 调用顺序和依赖关系。每新增一个 Agent，需要修改 Orchestrator 的所有策略方法。
2. **一对一的 prompt 拼接**：每个阶段的输入是手动拼接的前序输出，Agent 数量增多时拼接逻辑会爆炸。
3. **单层 Reviewer**：当前只有一个 Reviewer 审查所有阶段，如果扩展到 20 个 Agent 涉及多个专业领域（如数值分析、统计检验、可视化设计），一个 Reviewer 的知识面不足。
4. **缺乏动态调度**：无法根据中间结果（如建模失败）动态调整后续策略。

**改进方案：**

1. **引入 Agent 注册与 DAG 编排**：每个 Agent 声明自己的输入依赖（如 `requires=["modeling"]`）和输出产物（如 `produces=["code"]`），Orchestrator 自动构建执行拓扑图。类似 Airflow 的 DAG 调度。
2. **消息路由层**：不在 Orchestrator 中手动拼接 prompt，而是由 SharedMemory 根据声明式的依赖关系自动组装上下文。Agent 只需要声明 `input_sources=["latest:modeling", "all:reviewer(feedback)"]`。
3. **分领域 Reviewer**：引入多个专业 Reviewer（模型 Reviewer、算法 Reviewer、写作 Reviewer），各自审查对应领域。
4. **条件分支**：加入"Gate Agent"，根据中间结果质量决定下一步是继续、重试还是切换方案。例如建模输出中若缺少关键假设，则回到建模阶段而非继续编程。

---

## 二、LLM / Prompt 工程类

### Q5: 每个 Agent 的 System Prompt 都强制了 6 个输出维度，为什么这样设计？有什么代价？

**设计动机：**

1. **输出可预测**：数学建模竞赛有明确的评审标准（假设合理性、模型创新性、求解正确性、结果分析深度、论文写作质量）。6 维度结构确保每个 Agent 的输出不漏掉任何评分点。
2. **便于下游 Agent 消费**：`ProgrammerAgent` 知道自己需要从 `ModelerAgent` 输出中找"模型求解思路与算法选择"这一节；`WriterAgent` 知道从"建模方案"和"编程方案"中提取数值结果来撰写论文。结构化输出降低了 Agent 间信息提取的歧义。
3. **便于人工审查**：用户（或竞赛指导老师）可以快速定位到特定维度查看，而不需要通读全文。
4. **防止 LLM 敷衍**：如果没有强制结构，LLM 倾向于产出一个笼统的、看似合理但信息密度低的回答。强制分点迫使模型在每个维度都给出实质内容。

**代价：**

1. **Token 消耗大**：6 个维度即使部分内容质量不高，也占用了上下文。一轮完整协作的 Token 消耗通常在 8000-15000 token。
2. **输出可能僵化**：某些赛题可能不需要完整的 6 维度输出（如极简的优化问题可能不需要"风险分析"），但模型仍会生成。
3. **维度间可能重复**：如"模型构建"和"求解思路"在一个简单的线性规划问题中边界模糊，容易产生重复阐述。
4. **限制模型的自由发挥**：LLM 有时能发现 prompt 设计者没考虑到的输出角度，强制结构可能扼杀这种洞察。

**改进方向**：可以根据赛题复杂度动态选择输出维度。简单题用 3 维度（问题→模型→求解），复杂题用完整 6 维度。

**代码印证**：`agents.py:9-54` 中每个 Agent 的 System Prompt 都明确列出了 6 个编号输出项。

---

### Q6: ReviewerAgent 的评审 prompt 是怎么设计的？为什么要求"具体、建设性"而不是泛泛而谈？

**Prompt 设计分析：**

```
你是数学建模评审专家，擅长发现建模方案中的漏洞和不足。
请针对以下内容进行评审，输出：
1) 整体评价（优点）
2) 关键问题与漏洞（按严重程度排序）
3) 具体改进建议（可操作、可量化）
4) 是否有遗漏的假设或边界条件
5) 建议补充的分析或实验

评审要具体、建设性，不要泛泛而谈。
```

**每个维度的设计意图：**

1. **整体评价（优点）**：先肯定优点，降低修改的抵触感（即使是 AI Agent，在 prompt 中建立正向语境也能提高后续修改的质量）。同时帮助 Orchestrator 判断是否需要进入下一轮评审。
2. **关键问题与漏洞（按严重程度排序）**：强制排序阻止了"灌水式评审"（列一堆不痛不痒的小问题凑数）。评审必须做出价值判断——哪些问题阻塞了方案可行性，哪些是锦上添花。
3. **具体改进建议（可操作、可量化）**：这是最关键的约束。"可操作"意味着不能只说"模型需要改进"，必须说明怎么改；"可量化"意味建议要带指标（如"将误差阈值从 5% 收紧到 1%"或"补充 3 组对照实验"）。
4. **是否有遗漏的假设或边界条件**：针对数学建模的领域特性。遗漏假设是数模竞赛中最致命的问题之一（如假设"忽略摩擦力"但没有说明适用场景）。
5. **建议补充的分析或实验**：向前看的角度，不只是纠错，还要给出增强建议。

**为什么要"具体、建设性"：**

如果不在 prompt 中明确约束，LLM 的评审输出极容易退化为：

> "整体方案较为合理，模型选择适当，求解思路清晰。建议在某些细节上进一步优化。"

这种评审对 `solve_with_review` 的下游修改环节毫无价值——修改 Agent（实际就是原来的 Modeler/Programmer/Writer 重新 invoke）缺少具体的修改方向，改出来的结果和原版差异不大，形成"评审-修改-评审-修改"的死循环（每次改一点措辞但没有实质提升）。

**代码印证**：`agents.py:73-83`，`ReviewerAgent.review()` 方法构造 prompt 时把原始任务 `question`、`target_role` 和 `target_output` 一起注入，确保评审有完整的上下文。

---

### Q7: 不同 Agent 使用不同 temperature，背后的考虑是什么？

**核心原理：temperature 控制输出的随机性/确定性程度。**

| Agent | Temperature | 理由 |
|-------|------------|------|
| Modeler | 0.2（可配置） | 建模需要**创造性**来发现新颖的建模角度，但仍需要一定的数学严谨性。0.2 在创新与严谨间取平衡 |
| Programmer | 0.3（默认） | 代码实现需要精确，但算法选择有一定的弹性空间。默认值适合大多数场景 |
| Writer | 0.5（可配置） | 写作需要**表达多样性**——不同的句式、论证角度、强调重点。过低的 temperature 会让论文读起来像模板填空 |
| Reviewer | 0.1（可配置） | 评审需要**高度一致性**。同一份建模方案给不同的评审，结论应基本一致。0.1 确保评审稳定可复现 |
| Synthesizer | 0.3（默认） | 整合方案需要平衡一致性和灵活性 |

**为什么 Reviewer 的 temperature 最低？**

评审的核心价值是**可靠性**。如果同一个建模方案两次评审得出截然相反的结论，`solve_with_review` 中的修改循环就失去了锚点。低 temperature 保证了评审 Agent 对相同输入产生基本一致的输出，使评审反馈成为一个稳定的质量指标。

**为什么要可配置？**

不同赛题类型可能需要不同的创造性水平。比如探索性的开放问题（如"设计一种新的交通流模型"）可能希望建模 Agent 的 temperature 更高以激发创新思路；而答案明确的验证类问题（如"验证某模型的收敛性"）则需要更低的 temperature。

**代码印证**：`config.py:53-56`，通过环境变量 `DEEPSEEK_{ROLE}_TEMPERATURE` 按 Agent 覆盖温度，`Orchestrator.__init__` 中 `reviewer_llm` 使用独立温度创建独立的 LLM 实例。

---

### Q8: RAG 检索的 chunk 是怎么注入 prompt 的？如果 chunk 太多怎么处理？

**注入方式：**

在 `orchestrator.py:94-98`，`_rag_context()` 方法调用 `rag.query(question, top_k=6)` 获取 top_k 个 chunk，格式化为：

```
[来源: paper.pdf | 片段: 3] 论文相关内容...

[来源: survey.md | 片段: 1] 另一篇论文内容...
```

然后拼接到每个 Agent 的 prompt 开头（如 `f"任务：{question}\n\nRAG参考：\n{rag_ctx}"`）。

**当前机制的局限：**

1. **无相关性过滤**：所有 top_k 个 chunk 都会注入，即使有些 chunk 的相似度得分很低。代码中 `rag.py:120` 的过滤条件是 `scores[i] > 0`，这个阈值太低——余弦相似度 > 0 只是"有共同词"而非"语义相关"。
2. **无去重**：如果两个 chunk 来自同一篇论文的相邻段落，内容高度重叠，会浪费上下文空间。
3. **chunk 过多时的处理**：`top_k` 默认 6，在 GUI 侧边栏可调至 12。如果用户调到 20（当前限制），总 chunk 文本可能超过 15000 字符，严重挤压 Agent prompt 中的任务描述空间。

**改进方向：**

1. **相似度阈值**：设置 `scores[i] > 0.1` 或动态阈值（基于分数分布），低于阈值的 chunk 不注入。
2. **MMR（最大边际相关性）重排序**：在保证相关性的同时，惩罚与已选 chunk 相似的结果，增加多样性。
3. **动态 top_k**：根据检索结果的质量（最高分、平均分、分数衰减）自动调整注入数量。
4. **chunk 摘要**：对于超长 chunk，先用轻量模型生成一句话摘要，Agent 根据摘要决定是否需要深入阅读该 chunk 全文。
5. **分阶段注入**：不在每个 Agent 的 prompt 中都注入全部 RAG 上下文。建模阶段注入建模相关的论文，编程阶段注入算法相关的论文。

---

## 三、RAG / 检索增强类

### Q9: 为什么选 TF-IDF 而不是向量 Embedding 做检索？各自的优劣是什么？

**选择 TF-IDF 的理由：**

1. **零额外成本**：TF-IDF 纯本地计算，不需要调用 Embedding API（如 DeepSeek Embedding 或 text-embedding-3），零费用、零延迟。对于学生竞赛场景，成本敏感。
2. **无需额外配置**：不需要申请 Embedding 模型、不需要管理 API Key 的额外权限。开箱即用。
3. **关键词匹配在数学领域有优势**：数学建模文献中充满专有术语（如"变分不等式""NSGA-II""层次分析法一致性检验"），这些术语的语义很难被通用 Embedding 模型准确捕捉，但 TF-IDF 的精确词匹配能直接命中。
4. **可解释**：用户知道为什么某个 chunk 被检索出来（共享了哪些关键词），便于调试和优化。

**TF-IDF 的局限：**

1. **语义盲区**："交通流优化"和"车流密度调控"在语义上高度相关，但 TF-IDF 因为没有共享关键词，可能完全检索不到后者。
2. **词汇鸿沟**：用户用口语问"怎么把论文写得更像国奖水平"，而知识库中相关论文的表述是"数学建模竞赛论文写作策略的文献计量分析"——几乎没有共享词。
3. **多语言问题**：中英文混合检索时，TF-IDF 无法跨越语言边界。

**如果切换到 Embedding：**

- **优势**：语义理解强，跨语言好，对同义词和改写鲁棒
- **代价**：需要 Embedding 模型（额外费用或本地模型资源），索引构建慢（向量化比 TF-IDF 慢很多），检索延迟高（需要做向量相似搜索）

**代码印证**：`rag.py:85-89`，使用 `TfidfVectorizer(tokenizer=_jieba_tokenizer, max_features=7000, ngram_range=(1, 2))`，配置了 unigram + bigram 特征。

---

### Q10: jieba 分词在这个场景下有什么局限性？数学公式、英文术语混排怎么处理？

**jieba 的局限：**

1. **数学符号切分混乱**：`x_i^(k+1) = α * ∇f(x_i^k)` 会被 jieba 切分为 `['x', '_', 'i', '(', 'k', '+1', ')', '=', 'α', '*', '∇', 'f', '(', 'x', '_', 'i', '^', 'k', ')']`，原本有意义的数学符号被拆成碎片，TF-IDF 无法捕捉"梯度下降迭代公式"这个完整概念。
2. **中英文混排切分不准**："采用 NSGA-II 算法求解 Pareto 前沿" 中，"NSGA-II" 被拆成 `['NSGA', '-', 'II']`，"Pareto" 可能被当成未登录词处理。
3. **专业术语不在默认词典**："变分不等式""拟牛顿法""混合整数非线性规划"等术语可能被错误切分。

**改进方向：**

1. **自定义词典**：将数模领域常见术语加入 jieba 词典：

```python
jieba.add_word("层次分析法")
jieba.add_word("混合整数非线性规划")
jieba.add_word("NSGA-II")
jieba.add_word("Pareto前沿")
```

2. **数学公式预处理**：在分词前，用正则表达式将 LaTeX 公式提取为特殊 token 单独处理，保护其不被分词器切割。

3. **混合 tokenizer**：对中文部分用 jieba，对英文/数字/符号部分用空格 + 正则分词，两者结果合并。

4. **升级到 Embedding 模型**：向量化天然不会破坏公式结构（虽然公式的语义表达仍是挑战）。

**代码印证**：`rag.py:13-14`，`_jieba_tokenizer` 只是一个 4 行包装函数，没有任何自定义词典或预处理逻辑。

---

### Q11: chunk_size=900、overlap=120 这个参数是怎么确定的？

**参数选择的推断（代码中没有说明，以下为合理的技术解释）：**

**chunk_size = 900 字符：**
- 对于中文，约 450 个中文字（一个中文字约占 2 个字符位宽，但实际上 Python 中一个中文字 = 1 个字符）。实际约 450-900 字不等。
- 一个数学建模论文的段落通常在 200-800 字，900 字符能容纳一个完整的论据段落。
- 对于 TF-IDF，chunk 太小会导致关键词稀疏（一个 chunk 只包含少量术语，向量稀疏难匹配）；chunk 太大则会稀释关键词密度，检索精度下降。

**overlap = 120 字符：**
- 约 60-120 个中文字，相当于 2-3 句话的缓冲。
- 确保关键论点不被 chunk 边界切断。例如一个公式推导有 3 步，前两步骤落在 chunk A 末尾，第三步骤落在 chunk B 开头。如果没有 overlap，检索时无论命中 chunk A 还是 B，都只能看到不完整的推导。

**调参实验建议：**

可以设计消融实验：固定 overlap，测试 chunk_size ∈ {300, 600, 900, 1200, 1500} 对检索召回率的影响。评估方式：准备一组人工标注的问题-chunk 对，测试不同参数下的 Hit@k 和 MRR。

**代码印证**：`rag.py:33`，`_chunk_text(chunk_size=900, overlap=120)`，同时 `cleaned = " ".join(text.split())` 将原文的多余空白规范化。

---

### Q12: RAG 索引构建是离线的，如果知识库持续新增论文，怎么做增量索引？

**当前实现的问题：**

`build_index()` 是**全量重建**：重新遍历所有文件、重新分块、重新拟合 TfidfVectorizer、重新计算矩阵。原因是 TfidfVectorizer 的 `fit_transform` 需要看全量语料来计算 IDF（逆文档频率）——新增文档会改变所有已知词的 IDF 值。

**增量索引方案：**

**方案一：局部 ID 更新 + 定期全量重建（推荐）**

- 新增论文时：用已训练的 `vectorizer`（不重新 fit）对新增 chunk 做 `transform`（只用已学到的词汇表），拼接到现有矩阵。
- 代价：IDF 值基于旧语料，不反映新词的分布。新论文中新出现的词被忽略（不在旧词汇表中）。
- 补偿：每新增 20-30 篇论文或每周，后台自动触发一次 `build_index()` 全量重建，更新 IDF 和词汇表。
- 这相当于"最终一致性"——平时用近似索引，定期对齐到精确索引。

**方案二：替换存储后端**

- 将 TF-IDF + pickle 替换为 ChromaDB / FAISS + Embedding：
  - 新增文档时，对新 chunk 做 Embedding，直接插入向量数据库。
  - 不需要全局重新计算（Embedding 是文档独立的，不像 IDF 需要全量统计）。
- 代价：引入外部依赖，且 Embedding 费用/资源增加。

**方案三：分片索引**

- 将知识库按论文来源或主题分成多个子索引。
- 新增论文只重建受影响的分片索引，不再重建整个索引。

**代码印证**：`rag.py:70-99`，`build_index()` 中的 `fit_transform` 是全量操作，且索引通过 `pickle.dump` 整个覆盖写入。

---

## 四、工程实践类

### Q13: BaseAgent 的指数退避重试机制是怎么实现的？什么情况下重试也没用？

**实现原理：**

```python
# base.py:40-50
for attempt in range(self.max_retries):
    try:
        response = self.llm.invoke(messages)
        return self._normalize_content(response.content)
    except Exception as exc:
        last_error = exc
        if attempt < self.max_retries - 1:
            time.sleep(self.retry_delay * (2 ** attempt))
```

重试间隔：第 1 次重试等待 1s，第 2 次等待 2s，第 3 次等待 4s（`1.0 × 2^0 = 1s`, `1.0 × 2^1 = 2s`, `1.0 × 2^2 = 4s`）。

**为什么是指数退避而不是固定间隔：**

1. **应对 API 限流（Rate Limit）**：如果 API 返回 429 错误，固定间隔下所有重试请求仍然密集到达，可能再次触发限流。指数退避让请求密度指数衰减，给 API 服务器恢复时间。
2. **应对瞬时网络故障**：短暂断连通常在 1-3 秒内恢复，指数退避的首个间隔（1 秒）刚好匹配。
3. **避免资源浪费**：如果是持续故障（如 API Key 无效），固定间隔会快速耗尽重试次数；指数退避自动拉开了尝试间隔。

**什么情况下重试也没用：**

1. **认证错误（401）**：API Key 过期或无效，重试永远失败。应当检查异常类型，区分"可重试"（网络错误、429 限流、5xx 服务端错误）和"不可重试"（401、403、400 参数错误）。
2. **Token 超限**：如果 prompt 超过了模型的最大上下文，截断或压缩后再试，而不是原样重试。
3. **模型不存在**：请求了一个错误的模型名，重试无意义。
4. **流式模式的特殊问题**：`base.py:52-80` 中 stream 方法的重试逻辑有一个细节——重试前 `parts.clear()` 清空了已收集的 token，但如果失败发生在生成 3000 token 之后，清空后重新生成会多出一倍 Token 消耗。

**改进方向**：在异常捕获中做错误分类，对不可重试的错误直接抛出，对可重试的错误做退避。

**代码印证**：`base.py:40-49`（invoke 重试）、`base.py:63-77`（stream 重试）。

---

### Q14: `python_exec` 在子进程中执行代码，安全风险怎么控制的？还有什么不足？

**当前的安全措施：**

1. **子进程隔离**：代码在 `subprocess.run` 的独立进程中运行，有独立的内存空间，崩溃不影响主进程。
2. **30 秒超时**：`timeout=PYTHON_TIMEOUT`（30 秒）防止死循环耗尽 CPU。
3. **输出截断**：`out[:4000]` 防止输出爆炸撑爆上下文。

**不足——当前无法防止的攻击：**

1. **文件系统访问**：子进程可以读写文件系统。恶意代码可以执行：
   ```python
   import os; os.system("rm -rf ~/")  # 删除用户文件
   open("/etc/passwd").read()         # 读取系统文件
   ```
2. **网络访问**：子进程有完整的网络权限，可以作为跳板攻击内网其他服务。
3. **资源耗尽**：虽然有时间限制，但代码可以 `import numpy; numpy.random.rand(50000, 50000)` 瞬间耗尽内存。
4. **依赖滥用**：通过 `pip_install` 安装恶意包，然后 `python_exec` 执行。

**改进方向：**

1. **Docker/容器沙箱**：在 Docker 容器中执行代码，带 `--memory=512m --network=none --read-only` 等限制。这是最彻底的方案，但需要用户安装 Docker。
2. **RestrictedPython**：在 Python 层面做 AST 级别的权限控制，禁用 `__import__`、`open`、`os` 等危险操作。代价是可能误伤合法代码（如科学计算中的 `open` 读数据文件）。
3. **网络防火墙**：在子进程层面用 `unshare`（Linux）或 `sandbox-exec`（macOS）限制网络访问。
4. **资源限制**：用 `resource` 模块设置内存上限（仅 Linux/macOS）。

**当前设计的使用场景假设**：用户在本地使用，自己输入代码自己运行，攻击风险较低。但如果上线为多用户 SaaS，安全措施必须大幅加强。

**代码印证**：`tools.py:101-128`，只有超时、输出截断和独立的子进程，没有资源限制或系统调用过滤。

---

### Q15: `calculator` 用 AST 而不是 `eval()`，为什么？

**安全性对比：**

`eval("__import__('os').system('rm -rf /')")` —— 这行代码如果用 `eval()` 执行，会删除整个文件系统。

`calculator` 使用 AST（抽象语法树）做白名单安全求值：

```python
# tools.py:31-40
def _safe_eval(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
        return _OPERATORS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPERATORS:
        return _OPERATORS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("Only basic numeric expressions are supported.")
```

**工作原理：**

1. `ast.parse(expression, mode="eval")` 将字符串解析为 AST 树
2. 递归遍历 AST 节点，只处理白名单中的节点类型：`Constant`（数字）、`BinOp`（二元运算）、`UnaryOp`（一元运算）、`Expression`（包裹节点）
3. 遇到任何不在白名单中的节点（如 `Call` 函数调用、`Attribute` 属性访问、`Name` 变量引用），直接抛出 `ValueError`
4. 即使是合法的运算节点，其操作符也必须在 `_OPERATORS` 字典中

**支持的操作符**（`tools.py:19-28`）：`+`, `-`, `*`, `/`, `//`, `%`, `**`, 一元取反 `-`

**不支持的操作**：函数调用（`sqrt(4)`）、列表/字典、比较运算（`>`, `==`）、布尔运算（`and`, `or`）、三元表达式

**为什么这个设计是合理的：**

`calculator` 的定位是"帮用户快速算个数"，不是"做符号数学"。如果用户需要复杂计算，应该用 `python_exec`（在子进程沙箱中）。`calculator` 为高频小需求提供了零延迟零风险的路径。

---

### Q16: 流式输出是怎么实现的？如果中途断连怎么处理？

**实现原理：**

```python
# base.py:52-78
def stream(self, user_prompt, on_token=None):
    for attempt in range(self.max_retries):
        try:
            for chunk in self.llm.stream(messages):  # LangChain 的 stream 方法
                token = self._normalize_content(chunk.content)
                if not token:
                    continue
                parts.append(token)
                if on_token:
                    on_token(token)           # 实时回调
            return "".join(parts)             # 全部完成后返回完整文本
        except Exception as exc:
            parts.clear()                     # 清空已收集的 token
            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay * (2 ** attempt))
```

**流程：**

1. `self.llm.stream(messages)` 返回一个迭代器，每次 `next()` 产生一个 token chunk
2. 每个 token 被归一化后追加到 `parts` 列表，同时通过 `on_token` 回调立即推送给调用方
3. 在 GUI 模式（`gui.py:96-103`）中，`_stream_to_placeholder` 回调函数将累积的 token 实时更新到 Streamlit 的 `st.empty()` placeholder 上，用户看到文本逐字"生长"

**断连处理：**

- 当异常发生时，`parts.clear()` 清空已缓存内容，然后进入指数退避重试，从头开始重新生成
- 问题：如果断连发生在生成 3000 token 后，重试意味着那 3000 token 的 API 费用白费了，且用户会看到输出"跳回开头"
- 更好的方案是记录已生成的 token 数，重试时通过 Chat History 告诉 LLM 从断点继续，但 LangChain 的 `stream` 不原生支持断点续传

**代码印证**：`base.py:63-77`、`gui.py:96-103`、`cli.py:79-93`（`_print_streaming` 构造回调）。

---

## 五、业务逻辑 / 数模领域类

### Q17: 为什么建模 Agent 的输出要先给编程 Agent，而不是直接给写作 Agent？

**依赖关系分析：**

```
Modeler → Programmer → Writer → Synthesizer
   ↓         ↓           ↓          ↑
   └─────────┴───────────┴──────────┘
         (全部汇集到 Synthesizer)
```

**1. 编程 Agent 对建模 Agent 的依赖（硬依赖）：**

`ProgrammerAgent` 的 prompt 中包含 `f"建模专家输出：\n{model_out}"`。编程需要知道：
- 变量定义（符号、维度、含义）→ 决定数据结构设计
- 目标函数和约束条件 → 决定算法选择（线性规划选单纯形法，非线性选梯度下降或遗传算法）
- 假设条件 → 决定代码中哪些边界情况需要处理

没有建模输出，编程只能给出一个泛泛的算法框架，无法落地到具体代码。

**2. 写作 Agent 对编程 Agent 的依赖（数据依赖）：**

`WriterAgent` 的 prompt 中同时包含建模输出和编程输出。论文的核心章节"模型求解与结果分析"需要的要素：
- 求解算法描述（来自编程 Agent 的算法设计部分）
- 数值实验结果（来自编程 Agent 的数值实验设计）
- 收敛性分析（来自编程 Agent 的复杂度分析）
- 参数敏感性（来自编程 Agent 的调参建议）

如果写作 Agent 只拿到建模方案没有编程输出，论文中"结果分析"章节只能是空洞的定性描述，缺少图表和数据支撑。

**3. 为什么不反过来，写作先行？**

论文是对建模和求解的**描述**，不是对它们的**规划**。在不知道模型具体是什么之前，写出来的论文框架是"模板填空"，价值有限。建模→编程→写作的顺序遵循"方案→实现→文档"的自然流程。

**代码印证**：`orchestrator.py:124-132`，写作阶段的 prompt 包含 `建模专家输出：\n{model_out}\n\n编程专家输出：\n{prog_out}`。

---

### Q18: 评审反思模式中，为什么对建模、编程、写作都做评审，而不评审总控 Agent？

**设计逻辑：**

1. **评审的对象是"创造性产出"，而非"整合性产出"**

建模、编程、写作都是**从零产出**的创造性工作——你需要做出判断、选择、方案。这些判断和选择可能有错误、遗漏或不合理之处，需要外部评审。

总控 Agent（Synthesizer）的职责是**整合已有信息**："建模和编程和写作已经给出了高质量的输出，现在总控要做的是调度、排期、风险识别、TODO 列表"。总控的输出质量完全取决于**输入的质量**——如果前三个阶段（经过评审反思）的输出已经足够好，总控的输出自然也是好的。

2. **评审总控会造成无限递归**

如果评审总控 → 总控修改 → 再评审总控 → 总控再修改，这个循环什么时候终止？总控没有"客观标准"来判断输出质量（不像建模可以用数学逻辑验证，编程可以用测试验证）。

3. **如果要评审总控：**

可以让 Reviewer 检查总控输出中的：
- TODO 条目的优先级排序是否合理
- 风险识别是否覆盖了关键风险
- 时间计划是否实际可行
- 是否有遗漏的交付物

但这是在**执行层面**审查，而非在**方案层面**审查。可以作为一个可选的低成本检查步骤，而非核心质量门控。

**代码印证**：`orchestrator.py:233-241`，总控整合阶段没有评审循环，直接 `self.synthesizer.invoke(synth_in)` 生成最终方案。

---

### Q19: 如果有一个数模问题需要先做数据处理，当前 Agent 设计够用吗？

**当前设计的缺口：**

数学建模竞赛中，数据处理是常见且关键的前置步骤：
- 缺失值插补（线性插值、多重插补、KNN 插补）
- 异常值检测与处理（3σ 原则、箱线图、孤立森林）
- 特征工程（归一化、标准化、One-Hot 编码、特征交叉）
- 降维（PCA、t-SNE）
- 数据可视化（分布图、相关性热力图、时序图）

当前五个 Agent 中，`ProgrammerAgent` 在"算法实现"维度可以部分覆盖数据处理，但它的主要职责是"将数学模型转化为代码"，数据处理只是其输出的一小部分，容易被边缘化。

**改进方案：**

**方案一：新增 DataEngineerAgent**

```
你是数据预处理专家，负责赛题数据的清洗、探索与特征工程。
请按以下结构输出：
1) 数据概况（维度、缺失率、分布特征）
2) 数据清洗方案（缺失值处理策略、异常值检测方法）
3) 特征工程（构造、选择、变换）
4) 数据可视化方案（图表类型与解读）
5) 预处理后的数据格式说明（供建模 Agent 直接使用）
```

在 pipeline 中：`DataEngineer → Modeler → Programmer → Writer → Synthesizer`

**方案二：扩展 ProgrammerAgent 的职责**

在 ProgrammerAgent 的 System Prompt 中增加一个输出维度："0) 数据预处理与探索性分析"，将数据处理作为编程的前置输出。

**方案三：工具链补充**

通过 `python_exec` 和 `read_csv_info` 工具，让 Agent 直接操作数据文件。但这需要 Agent 具备 ReAct 能力（推理-行动循环），当前 Agent 是单纯的问答模式。

---

### Q20: 实际效果怎么样？有没有评估过输出质量？

**坦诚回答（面试官看重诚实）：**

当前项目处于**功能完备**阶段，有完整的架构和代码实现。但缺乏**系统性量化评估**。以下是可讨论的评估维度：

**定性评估指标：**

1. **结构完整性**：Agent 输出是否覆盖了 System Prompt 要求的所有维度
2. **逻辑自洽性**：建模假设是否内部一致、结论是否由推导自然得出
3. **可执行性**：编程 Agent 给出的代码是否能正常运行并输出合理结果
4. **论文规范性**：写作 Agent 的论文结构是否符合竞赛评审标准

**定量评估方案（如果要做实验）：**

1. **与获奖论文对比**：选取 3-5 道历年数模国赛 A/B/C 题，让系统产出完整方案，与获奖论文做对比。评估指标：
   - 模型创新度（专家 1-5 评分）
   - 求解完成度（是否有数值结果、结果是否合理）
   - 论文完整度（章节覆盖率）

2. **消融实验**：逐组件评估贡献
   - Baseline：单 Agent 做全部任务
   - + 多 Agent 分工
   - + RAG 检索
   - + 评审反思
   - 对比四组输出的专家评分

3. **A/B 测试**：同一道题，分别用 `sequential` 和 `review` 策略，将两份方案匿名交给 3 位有数模竞赛经验的评委打分。

4. **Token 效率**：不同策略下的 Token 消耗与输出质量的性价比。

---

## 六、扩展性 / 场景题

### Q21: 如果用户想要让 Agent 之间互相辩论，怎么实现？

**辩论模式的设计：**

核心思想是让多个 Agent 形成"对抗性协作"——不是单方面评审，而是双向质疑与回应。

**实现方案：辩论轮次协议**

```
Round 1: Modeler → 产出方案 v1
Round 2: Reviewer → 质疑方案 v1 的 3 个核心问题
Round 3: Modeler → 逐一回应质疑，修改方案 → 产出 v2
Round 4: Reviewer → 对修改后的 v2 再次质疑（新的问题或追问旧问题是否真正解决）
Round 5: Modeler → 最终方案 v3
...
终止条件：Reviewer 连续两次无新问题 OR 达到最大轮次（如 5 轮）
```

**关键设计点：**

1. **质疑必须具体**：Reviewer 不能只说"模型不够好"，必须指向具体假设、推导步骤或参数选择。可以强制 Reviewer 输出格式："问题 X：[具体位置] + [理由] + [反例/边界条件]"
2. **回应必须有修改**：Modeler 不能只解释不修改。协议要求每次回应必须附带具体的方案修改（标注修改前后对比）。
3. **防止无限循环**：设置 5 轮硬上限，且每轮有新问题才继续（"我已经没有实质性质疑了" = 达成共识）。
4. **多角色辩论扩展**：可以让 Programmer 也参与质疑建模（"这个模型在时间 O(n³) 内无法求解，建议用近似算法"），形成跨专业辩论。

**代码层面的改动：**

需要将 `solve_with_review` 的单向评审改为双向辩论循环，本质上是对话式的多轮 invoke（而非当前"生成→评审→重生成"的文档级往返）。核心差异是：辩论中 Agent 看到的是**对方的具体质疑**并针对性质疑做**定向修改**，而非看到一份完整的评审报告后全量重写。

---

### Q22: 怎么加上"从上次中断处继续"的功能？

**方案设计：checkpoint 机制**

**第一步：序列化状态**

将以下状态持久化到磁盘（如 `checkpoint.pkl`）：

```python
@dataclass
class Checkpoint:
    question: str
    strategy: str                    # sequential / review / parallel
    current_stage: str               # modeling / programming / writing / synthesis
    current_round: int               # 评审反思中的当前轮次
    stage_outputs: dict[str, str]    # 已完成阶段的输出
    memory: SharedMemory             # 完整消息历史
    rag_top_k: int
```

**第二步：在每个阶段完成后自动保存 checkpoint**

在 `Orchestrator` 的每个策略方法中，每完成一个阶段就调用 `_save_checkpoint()`。

**第三步：恢复执行**

```python
def resume_from_checkpoint() -> WorkflowResult:
    cp = load_checkpoint()
    orch = Orchestrator(settings, rag=rag)
    # 根据 current_stage 和 strategy 跳转到对应位置继续执行
    if cp.current_stage == "programming":
        # 跳过建模阶段，直接从编程继续
        prog_out = orch.programmer.invoke(...)
        # ...
```

**难点：**

1. **评审反思模式的恢复**：需要记录当前评审轮次和上一轮的评审反馈，恢复时精确跳转到当前轮次的当前位置。
2. **并行模式的恢复**：如果编程完成了但写作中断了，恢复时只需重跑写作。
3. **流式模式的恢复**：流式输出不应该做 checkpoint（因为用户正在实时观看），仅在非流式模式下启用。
4. **版本兼容**：如果 Agent 的 System Prompt 在两次会话间改变了，恢复后的输出风格可能不一致。

**代码层面**：当前 `SharedMemory` 已经是一个结构良好的可序列化对象（dataclass + 基本类型），天然支持 pickle。

---

### Q23: 如果 DeepSeek API 挂了，怎么让系统不崩溃？怎么无缝切到另一个模型？

**方案一：LLM 工厂 + Fallback 链**

```python
# llm.py 改造
from langchain_core.language_models import BaseChatModel

def create_llm_with_fallback(settings: Settings) -> BaseChatModel:
    primary = create_llm(settings)  # DeepSeek

    # fallback 模型（如 OpenAI 兼容接口的其他模型）
    fallback_configs = settings.fallback_models  # 从 .env 读取
    fallbacks = [_create_fallback_llm(cfg) for cfg in fallback_configs]

    # LangChain 的 with_fallbacks 自动处理异常切换
    return primary.with_fallbacks(fallbacks)
```

**方案二：抽象 LLM 接口层**

```python
from abc import ABC, abstractmethod

class LLMProvider(ABC):
    @abstractmethod
    def invoke(self, messages) -> str: ...
    @abstractmethod
    def stream(self, messages): ...

class DeepSeekProvider(LLMProvider):
    # 封装 langchain-deepseek

class OpenAIProvider(LLMProvider):
    # 封装 langchain-openai
```

在 `Settings` 中配置 provider 优先级列表，`LLMFactory.create()` 按顺序尝试。

**方案三：熔断器模式**

```python
class CircuitBreaker:
    def __init__(self, failure_threshold=3, timeout=60):
        self.failures = 0
        self.threshold = failure_threshold
        self.timeout = timeout
        self.last_failure_time = None

    def call(self, fn):
        if self.failures >= self.threshold:
            if time.time() - self.last_failure_time < self.timeout:
                raise Exception("Circuit breaker OPEN")
            self.failures = 0  # timeout已过，尝试半开
        try:
            result = fn()
            self.failures = 0  # 成功，重置
            return result
        except Exception:
            self.failures += 1
            self.last_failure_time = time.time()
            raise
```

熔断器在短期内多次失败后直接拒绝调用（不浪费重试等待时间），等冷却期过后再尝试。

**代码印证**：`llm.py` 当前是单一 provider 的工厂函数，改造需要引入 fallback 链或熔断器逻辑。

---

### Q24: 这个项目如果要上线做成 SaaS，最大的挑战是什么？

**1. 成本控制**

- 单次完整协作消耗 8000-15000 token（五个 Agent 各产出一段长文），按 DeepSeek 当前价格估算每次约 0.01-0.03 美元
- 评审反思模式消耗翻倍（每轮评审 + 修改 = 额外 token）
- 如果日活 1000 用户，每天 100 次协作请求，月度 API 费用可达数百到上千美元
- **对策**：按用户等级限流（免费用户限 sequential 模式 + top_k=3，付费用户解锁 review + top_k=20）、输出缓存（相似问题的方案复用）

**2. 延迟**

- 串行模式：五个 Agent 串行调用，每个调用 5-30 秒，总延迟 30-150 秒
- 用户不可能等 2 分钟看一个结果
- **对策**：流式输出缓解感知延迟（用户看到第一个 token 后就能开始阅读）、预生成常见赛题的方案模板做缓存、异步任务队列（后台运行，完成通知）

**3. API QPS 限制**

- DeepSeek API 有并发限制，多用户同时请求时会排队
- **对策**：请求队列 + 优先级调度（付费用户优先）、多 API Key 负载均衡、自建模型（如本地部署的开源模型）

**4. 多租户隔离**

- RAG 知识库：用户 A 上传的论文不应被用户 B 检索到
- SharedMemory：协作历史需要按用户隔离
- **对策**：每个用户独立的知识库目录和索引文件，SharedMemory 绑定用户 ID

**5. 输出质量不一致**

- 同一个赛题，两次运行的输出可能差异较大（temperature > 0 的必然结果）
- 如何保证付费用户体验？
- **对策**：增加输出质量评分机制（用另一个 LLM 对输出打分）、低质量输出自动触发重新生成、提供"不满意可重试"按钮

**6. 安全性**

- `python_exec` 在服务端执行任意代码，这是**极高风险**
- **对策**：必须上 Docker 沙箱，限制内存、CPU、网络、文件系统、系统调用。绝不能在宿主机直接运行用户代码

**7. 流式输出的 WebSocket 管理**

- 流式模式下需要维持长连接，1000 并发 WebSocket 连接的管理是工程挑战
- **对策**：异步框架（FastAPI + asyncio）、连接池管理、心跳检测、断线自动重连

---

## 七、加分题

### Q25: 你有没有考虑过让 Agent 自己决定调用顺序，而不是固定 pipeline？

**固定 pipeline vs 自主调度的权衡：**

| 维度 | 固定 Pipeline（当前） | 自主调度（Agent-driven） |
|------|----------------------|--------------------------|
| 可靠性 | 高，流程可预测 | 低，可能走偏或死循环 |
| 效率 | 可能有冗余步骤 | 按需调用，减少浪费 |
| 可控性 | 高，人工可审查每个阶段 | 低，黑盒决策 |
| Token 消耗 | 固定 | 可能更少（跳步骤）或更多（循环） |

**实现自主调度的技术路线：**

**路线一：ReAct 模式**

给 Orchestrator 本身配一个 LLM，在循环中做"思考-行动-观察"：

```
Thought: 用户的问题是优化问题，我需要建模→求解→写作
Action: invoke(ModelerAgent, "建立交通流优化模型")
Observation: [建模输出]
Thought: 建模方案中使用了整数规划，我需要用分支定界法求解
Action: invoke(ProgrammerAgent, "用分支定界法实现上述模型")
Observation: [代码方案]
Thought: 建模和编程都完成了，可以开始论文写作
Action: invoke(WriterAgent, "基于以上方案撰写论文")
...
Thought: 所有阶段完成
Final Answer: [整合方案]
```

**路线二：Plan-and-Execute 模式**

先让一个 Planner Agent 分析赛题类型和复杂度，生成执行计划（计划中包含哪些 Agent、什么顺序、几轮评审），然后 Executor 按计划执行。

```python
plan = planner.plan(question)
# plan = {
#     "stages": [
#         {"agent": "data_engineer", "required": True},
#         {"agent": "modeler", "required": True},
#         {"agent": "programmer", "required": True},
#         {"agent": "writer", "required": True},
#         {"agent": "reviewer", "rounds": 1, "targets": ["modeler"]},
#     ],
#     "estimated_tokens": 12000,
# }
```

**为什么当前项目选择了固定 pipeline：**

数模竞赛的流程是高度结构化的（建模→求解→写作），Agent 的调用顺序有明确的领域逻辑，自动发现调用顺序带来的收益不大，但引入的不确定性很高。对于一个面向竞赛场景的工具，**可靠性 > 灵活性**。

---

### Q26: 如果要评估这个系统的效果，你会设计怎样的实验？

**实验一：组件消融实验**

| 实验组 | 配置 | 预期 |
|--------|------|------|
| A（Baseline） | 单 Agent + 无 RAG | 基础质量 |
| B | 多 Agent（sequential） + 无 RAG | 分工带来的提升 |
| C | 多 Agent + RAG | 知识检索的增益 |
| D | 多 Agent + RAG + 评审反思 | 质量控制的增益 |

每组在 5 道历年赛题上运行，每道题运行 3 次取平均。

**实验二：与人类方案的对比**

选取 3 道公开的历年数模国赛题（A/B/C 题各一道），收集当年获奖论文（国一、国二各 2 篇）。将系统产出方案与获奖论文混合在一起，匿名交给 3 位有数模竞赛评审经验的评委，按竞赛评分标准打分。

评估维度：
- 模型假设合理性（/10）
- 模型创新性（/10）
- 求解正确性与完整性（/10）
- 结果分析深度（/10）
- 论文写作质量（/10）

**实验三：RAG 检索质量评估**

构造测试集：人工标注 50 个问题与相关论文 chunk 的对应关系。

指标：
- **Hit@k**：前 k 个检索结果中至少有一个是相关 chunk 的问题比例
- **MRR**（Mean Reciprocal Rank）：第一个相关结果排名的倒数平均值
- **NDCG@k**：考虑排序位置的归一化折损累积增益

**实验四：Temperature 参数灵敏度**

固定其他配置，对每个 Agent 的 temperature 在 {0.0, 0.1, 0.2, 0.3, 0.5, 0.7} 做网格搜索，评估输出质量的均值和方差。目标：找到每个 Agent 的最优 temperature 区间。

**实验五：Token 效率分析**

对比不同策略（sequential / review / parallel）在相同赛题上的 Token 消耗和输出质量比值（Quality per 1K tokens），为用户推荐性价比最优的策略。

---

> 以上回答基于项目源码分析和对数学建模竞赛、LLM 应用工程的理解编写，面试时建议结合自己的理解做口语化表达。

---

## 八、最新架构升级（2026-05）

### Q27: 项目的上下文压缩是怎么设计的？为什么选择"增量合并"而不是"全文摘要"？

**两段式 STM 架构（`compressed_prefix + recent_window`）：**

```
触发前: [msg1, msg2, msg3, msg4, msg5, msg6, msg7, msg8, msg9, msg10]  ← 10条消息，token 超限
       ↓ 触发 compress_older(keep_recent=5)
触发后: [compressed_prefix: "摘要: msg1-5的核心..."]
       [recent_window: msg6, msg7, msg8, msg9, msg10]             ← 5条完整保留

再次触发:
       [compressed_prefix: "摘要: msg1-10的核心..."]  ← LLM 合并旧摘要+msg6-7
       [recent_window: msg8, msg9, msg10, msg11, msg12]
```

**为什么增量合并（hierarchical）优于全文摘要（summarize）：**
1. **信息保真度**：全文摘要每次重新摘要全部消息，中间的细节在二次摘要中再次衰减。增量合并保留已有摘要的脉络，新消息作为"增量"追加合并
2. **Token 节省**：增量合并只需处理 `旧摘要(500字) + 新消息(2000字)`，全文摘要需要处理 `全部消息(8000字)`
3. **历史连贯性**：已有摘要中的关键决策不会被遗忘（全文摘要可能因 LLM 注意力偏移而遗漏旧段落中的要点）

**触发条件（双阈值）：**
- Token 阈值：STM 估算 token > 30000（可配置）
- 轮次阈值：距上次压缩超过 3 轮（防止 token 小但轮次多的场景）

**代码印证**：`memory/short_term.py:95-112`（`compress_older`）、`memory/compressor.py:90-100`（`_compress_incremental`）、`memory/manager.py:80-95`（`_run_compression`）。

---

### Q28: 为什么设计了 6 种终止条件？和简单的 `max_review_rounds` 有什么本质区别？

**设计动机（受 AutoGen `conditions` 模块启发）：**

`max_review_rounds` 只能按轮次终止，但实际协作中有多种"该停了"的信号：
- 时间紧迫（`TimeoutCondition`：600 秒超时）
- Token 预算耗尽（`TokenBudgetCondition`：累计消耗 > 200K tokens）
- 质量已达标（`QualityThresholdCondition`：评审得分 > 0.85）
- 用户手动中断（`ExternalCondition`：WebSocket 断开时 `set()`）

**组合模式（`CompoundCondition` = OR 逻辑）：**

```python
active_conditions = [
    MaxRoundCondition(3),
    TokenBudgetCondition(200000),
    TimeoutCondition(600.0),
    external_condition,  # WebSocket 断开时 set()
]
# 任一条件触发 → StopMessage → 退出循环
```

**本质区别**：单一 `max_review_rounds` 是**静态上限**，而多条件是**动态门控**——评审循环可以在"轮次未满但已无必要继续"时提前退出，也可以在"轮次已满但质量严重不足"时给用户反馈而非默默接受低质量输出。

**代码印证**：`conditions.py:90-115`（`TokenBudgetCondition`）、`conditions.py:120-150`（`TimeoutCondition`）、`orchestrator.py:410-430`（评审循环中的每轮检查）。

---

### Q29: 实际 LLM token 消耗是怎么追踪的？估算和真实的差距怎么处理？

**三层 token 计数：**

| 层级 | 来源 | 准确度 |
|------|------|--------|
| `AgentMessage.token_count` | `len(content) // 2`（粗略估算） | 低，用于快速判断 |
| `AgentMessage.prompt_tokens + completion_tokens` | LLM 响应的 `usage_metadata` 或 `response_metadata.token_usage` | 高，真实 API 消耗 |
| `TokenBudgetCondition.accumulated` | 累加每次调用的真实 token | 高，用于终止判断 |

**提取真实 token 的逻辑（`base.py:extract_token_usage`）：**

```python
def extract_token_usage(response):
    # 兼容 LangChain >= 0.3 的 usage_metadata（input_tokens/output_tokens）
    meta = getattr(response, "usage_metadata", None) or {}
    # 兼容 DeepSeek 的 response_metadata.token_usage（prompt_tokens/completion_tokens）
    resp_meta = getattr(response, "response_metadata", None) or {}
    token_usage = resp_meta.get("token_usage", {})
    # 两种来源互补，取非零值
```

**费用估算**（`WorkflowResult.estimated_cost_usd`）：
- DeepSeek V4 定价：$0.27/1M prompt tokens + $1.10/1M completion tokens
- 一次完整 solve 通常在 $0.01-0.05

**面试加分点**：说明了你不仅关心功能正确性，还关心生产环境下的成本可控性。

---

### Q30: LLM 驱动的记忆索引（CrewAI 启发）和传统关键词索引有什么区别？

**传统做法（`archive_solve` 旧版）**：人工标记的 `tags` + 关键词匹配的 `_has_code_issues`。完全依赖预定义的判断规则。

**新做法（LLM Analyze → Archive）**：

```
solve 完成 → LLM 分析输出
  ├─ scope: "/optimization/linear-programming"（层级领域路径）
  ├─ importance: 0.82（可复用价值评分）
  └─ model_types: ["线性规划", "对偶理论", "灵敏度分析"]
→ LTM.add(..., importance=0.82, scope="/optimization/...")
```

**三种层级 scope 的优势**（`search_by_scope`）：
- `/optimization/` 前缀搜索可召回所有优化相关的历史方案
- 重要性评分 0.8+ 的优先召回
- 低质量的求解（importance < 0.3）自动降权

**复合重排序（`_compute_composite_score`）**：

```
最终得分 = 0.4 × FTS5_rank + 0.25 × 时间衰减 + 0.1 × 访问热度 + 0.25 × 重要性
```

时间衰减半衰期 180 天——半年前的记忆权重降至 50%，防止过时的建模方案排在新方案前面。

**代码印证**：`memory/manager.py:145-170`（`_analyze_for_archive`）、`memory/long_term.py:130-145`（`_compute_composite_score`）、`memory/long_term.py:218-238`（`search_by_scope`）。

---

### Q31: Orchestrator 的容错机制是怎么设计的？如果 Modeler 失败了，后续 Agent 还能运行吗？

**核心设计：`_safe_invoke` / `_safe_stream`**

```python
def _safe_invoke(self, agent, prompt, role_label, stm, errors, ...):
    try:
        result = agent.invoke(prompt)
        self._post(stm, role_label, result)  # 记录到 STM
        return result
    except Exception as exc:
        errors.append(f"[{role_label}] 执行失败: {exc}")  # 追踪错误
        fallback = f"[{role_label} 因错误未能完成: {exc}]"  # 降级文本
        self._post(stm, role_label, fallback)
        return fallback  # 不抛异常，返回降级文本
```

**失败链的处理**：
- Modeler 失败 → `model_out = "[建模智能体 因错误未能完成: ...]"` → Programmer 收到的是降级文本，但依然能基于问题描述给出一个基础方案
- Programmer 失败 → Writer 仍能基于建模输出 + 问题描述写论文框架
- 所有错误汇入 `WorkflowResult.errors`，`format_overview()` 在末尾展示错误摘要

**设计权衡**：选择"容错继续"而非"失败即停"，因为：
1. 数模竞赛中，即使某个阶段不理想，其他阶段的输出仍有价值
2. `WorkflowResult.errors` 让用户知道哪些阶段出了问题，可以针对性重跑
3. 比整个流程崩溃后用户零信息要好

**并行模式特殊处理**（`solve_parallel`）：`ThreadPoolExecutor` 中的编程和写作独立 try/except，一个失败不影响另一个。

**代码印证**：`orchestrator.py:238-260`（`_safe_invoke` / `_safe_stream`）、`orchestrator.py:120-130`（`WorkflowResult.errors` 和 `format_overview` 中的错误展示）。

---

### Q32: Web 端三种策略都支持流式输出，并行模式下的流式是怎么实现的？

**三种策略的流式实现**：

| 策略 | 方法 | 流式方式 |
|------|------|----------|
| 串行 | `solve_stream` | 各 Agent 依次 `stream()`，token 逐个经 WebSocket 推送 |
| 评审 | `solve_with_review_stream` | 主阶段 `stream()`，评审意见走 `invoke()`（内容短），优化后重新 `stream()` |
| 并行 | `solve_parallel_stream` | 建模 `stream()` → 编程+写作在 `ThreadPoolExecutor` 中**各自独立 `stream()`** |

**并行流式的关键设计**：

```python
def solve_parallel_stream(self, question, on_modeling_token=None,
                           on_programming_token=None, on_writing_token=None, ...):
    # 建模流式（阻塞，完成后编程和写作才能开始——这是硬依赖）
    model_out = self._safe_stream(self.modeler, model_in, "modeling", ..., on_token=on_modeling_token)

    # 编程和写作并行执行，各自独立的 token 回调
    def run_programmer_stream():
        return self.programmer.stream(
            prompt, on_token=on_programming_token,  # → WebSocket "programming" channel
        )

    def run_writer_stream():
        return self.writer.stream(
            prompt, on_token=on_writing_token,       # → WebSocket "writing" channel
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        pf = executor.submit(run_programmer_stream)
        wf = executor.submit(run_writer_stream)
        prog_out = pf.result()
        write_out = wf.result()
```

**WebSocket token 推送**：`_sync_send_token` 将 token 追加到全局队列 → `_token_drainer`（50ms 间隔）批量通过 WebSocket 发送。前端 `connectWS()` 中 `msg.type === 'token'` 处理每个 token，实时 DOM 更新。

**代码印证**：`orchestrator.py:940-1000`（`solve_parallel_stream`）、`web/routes.py:139-166`（`_token_drainer`）、`web/static/app.js:75-85`（前端 token 渲染）。

---

### Q33: PDF 上传提取题目的难点是什么？表格和图片怎么处理？

**三个提取维度**：

| 维度 | 方法 | 输出 |
|------|------|------|
| 文字 | `page.get_text()` | 纯文本 |
| 表格 | `page.find_tables()` → `_md_table_from_cells()` | Markdown 表格 |
| 图片 | `page.get_images()` → Qwen-VL 多模态描述 | 中文图片描述 |

**表格提取的挑战**：
- PyMuPDF 的 `find_tables()` 依赖表格边框线，无边框表格无法检测
- `cell.text` 可能包含换行符，需要 `replace("\n", " ")` 清理
- 合并单元格的 `row/col` 计算需要 `row_count/col_count` 修正

**图片处理的取舍**：
- 只对 > 2048 字节的图片进行 VL 描述（跳过小图标/装饰元素）
- 最多 8 张图片（限制 API 调用量）
- VL 描述是可选的——如果没有 `EMBEDDING_API_KEY`，只标注"本页含 N 张嵌入图片"
- 图片描述追加在正文末尾（`── 图片内容描述 ──`），不打断原文结构

**代码印证**：`web/routes.py:211-225`（`_md_table_from_cells`）、`web/routes.py:280-330`（图片提取与 VL 描述）。

---

## 九、补充新增面试题

### Q34: 项目的测试策略是什么？65 个测试覆盖了哪些层面？

**测试分层**：

| 文件 | 测试数 | 覆盖内容 |
|------|--------|----------|
| `test_memory.py` | 12 | STM 消息操作、LTM CRUD、MemoryManager 集成、归档 |
| `test_core.py` | 42 | `normalize_llm_content`、重试分类、分段 STM、压缩策略、终止条件（9个）、AgentMessage 字段、token 提取 |
| `test_evolution.py` | 11 | FitnessScore、ConstraintValidator、PromptConstraintValidator、EvolutionTracker |

**明确不测试的（设计决策）**：
- Agent 的 LLM 调用（需要 mock，且与模型高度耦合，mock 测试价值低）
- Orchestrator 全流程（需要真实 LLM，留待集成测试/端到端测试）
- Web 路由（可以用 FastAPI TestClient 补充，当前未实现）

**如果面试官追问"测试覆盖率够吗"**：坦诚地说——核心数据结构（STM、LTM、条件系统）有良好覆盖，但 Orchestrator 和 Web 层的集成测试不足。在有 CI/CD 和 staging 环境的情况下，应补充 API 级别的端到端测试和 WebSocket mock 测试。

---

### Q35: 从三个开源项目（AutoGen、CrewAI、MetaGPT）借鉴了什么？为什么不直接使用它们？

**借鉴的关键设计**：

| 来源 | 借鉴 | 实现 |
|------|------|------|
| **AutoGen** | `TokenUsageTermination`、`CompoundCondition` | `conditions.py`（6 种条件） |
| **AutoGen** | `Team.save_state()/load_state()` | `WorkflowResult.save_state()/load_state()` |
| **CrewAI** | LLM 分析 → 提取 scope/importance/categories | `MemoryManager._analyze_for_archive()` |
| **CrewAI** | 过采样 + 复合重排序 | `_OVERSEARCH_FACTOR=2` + `_compute_composite_score()` |
| **MetaGPT** | `ContextMixin`（私有 context 覆盖全局） | `Settings.agent_configs` 的层级配置 |
| **MetaGPT** | `Message.cause_by` 因果追溯 | `AgentMessage.triggered_by` |

**为什么不直接用它们？**

1. **过度抽象**：AutoGen 的 Agent Runtime + Topic + Subscription 体系对简单的线性 pipeline 来说太重了。我们的场景是固定的"模型→求解→写作"，不需要通用消息路由。
2. **依赖负担**：CrewAI 强依赖 ChromaDB（向量数据库）+ LiteLLM（多模型统一接口），引入约 30 个传递依赖。我们的场景只需要 SQLite + DeepSeek。
3. **数模领域的专用优化**：MCM/ICM 的评审标准、论文格式、模型选型逻辑是领域特定的，通用框架不会内置这些。我们的 Reviewer Agent 的评审 prompt 是专门对齐数模评审标准的。
4. **控制力**：自己掌控编排逻辑意味着可以自由实现"如果建模失败则重试"的细粒度控制，而不受框架抽象层的限制。

关键原则：**借鉴设计模式，但不盲从框架。知道自己为什么不直接用它们，比直接用更体现工程判断力。**

---

### Q36: Agent 间如果产生矛盾怎么办？比如 Reviewer 提出修改建议，但 Modeler 修改后的方案更差了。

**当前机制**：
1. `_review_needs_revision()` 用 LLM 做语义判断，而非关键词匹配——评审说"无需修改"才退出，否则继续
2. `max_review_rounds` 硬上限防止无限循环

**当前机制的局限**：没有方案退化检测。如果第 2 轮修改后的方案比第 1 轮更差，系统不会回滚。

**改进方案（可以讲给面试官）**：
1. **适应度评分**：每轮评审后用 `FitnessEvaluator` 打分，追踪趋势。得分下降时回滚到上一版本
2. **差异对比**：用 LLM 对比修改前后的方案，判断修改是否真正解决了评审指出的问题
3. **分歧仲裁**：当 Reviewer 和 Agent 对某修改有分歧时，引入第二个 Reviewer 做独立评价

这展示了你知道当前设计的边界，并有改进思路。