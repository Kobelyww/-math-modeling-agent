"""Academic Research Skills — integrated from github.com/Imbad0202/academic-research-skills.

This module adds deep academic writing, reviewing, and research methodology skills
to the progressive disclosure registry. Content is distilled from the 4-module
ARS plugin: academic-paper, academic-paper-reviewer, deep-research, academic-pipeline.

Key knowledge domains:
  - Writing quality & de-AI-fication (from writing_quality_check.md)
  - Abstract writing (from abstract_writing_guide.md)
  - Paper structure patterns (from paper_structure_patterns.md)
  - Review criteria framework (from review_criteria_framework.md)
  - Writing judgment (from writing_judgment_framework.md)
  - LaTeX standards (from latex_template_reference.md)
  - Statistical visualization (from statistical_visualization_standards.md)
  - RAISE framework (from raise_framework.md)
"""

from __future__ import annotations

# ─── Skill content extracted from ARS repo ──────────────────────────────

WRITING_QUALITY_SKILL = """## Academic Writing Quality Rules (ARS)

### A. AI-Typical Term Warnings
以下词汇在AI生成文本中出现过多。出现时问自己："这是最精确的词吗？"

| 需警惕 | 替换建议 |
|--------|---------|
| delve (深入) | examine, investigate, explore |
| tapestry (交织) | network, interplay, system |
| landscape (领域) | field, domain, context |
| pivotal / crucial | important, central, essential |
| foster (促进) | promote, develop, cultivate |
| showcase (展示) | demonstrate, illustrate, present |
| leverage (利用) | use, employ, apply |
| robust (稳健) | reliable, strong, rigorous |
| holistic (整体) | comprehensive, integrated |
| groundbreaking | novel, innovative, pioneering |

例外：如果该词是目标学科的标准术语（如统计学的"robust estimator"），豁免。

### B. Punctuation Control
- Em dash (—): 全篇 ≤ 3 个，推荐 0-1
- Semicolons: ≤ 2 个/千字
- Colon-list sequences: 避免连续两段都以冒号+列表开头

### C. Throat-Clearing Openers — 直接删除以下开头
| 删除 | 原因 |
|------|------|
| "In the realm of..." | 空洞 |
| "It's important to note that..." | 如果重要自然就重要 |
| "It is worth mentioning that..." | 同上 |
| "In today's rapidly evolving..." | 时间戳陈词 |
| "This serves as a testament to..." | 替换为 "This demonstrates..." |
| "In order to..." | 替换为 "To..." |
| "This section will discuss..." | 直接讨论，不要宣告 |

### D. Meta-Commentary
避免描述论文在做什么的句子，直接做：
- ❌ "The following paragraph examines..."
- ✅ 直接给出分析内容

**来源**: academic-paper/references/writing_quality_check.md
"""

ABSTRACT_WRITING_SKILL = """## Abstract Writing — 5-Component Model (ARS)

### English Abstract (150-250 words)

**Component 1: Background (1-2 sentences)** — 建立背景，识别问题
- "[Topic] has become important because..."
- "Despite growing interest in [topic], little is known about..."
- ❌ 不要以 "This paper..." 开头（太突兀）

**Component 2: Purpose (1 sentence)** — 研究目标
- "This study examines [what] in [context]."
- "The purpose of this research is to [verb] [object]."

**Component 3: Method (1-2 sentences)** — 方法
- "Using [method], this study analyzed [data] from [source]."
- 包含研究设计、数据来源、分析方法

**Component 4: Findings (2-3 sentences)** — 关键结果（务必量化！）
- "The results indicate that [finding 1]. Additionally, [finding 2]."
- ✅ 包含具体数字（百分比、效应量）
- ❌ "Results will be discussed" / "significant results were found"

**Component 5: Implications (1-2 sentences)** — 意义
- "These findings have implications for [practice/policy/theory]."
- "This research contributes to [field] by [contribution]."

### Chinese Abstract (300-500 characters)
同样五部分结构，特别注意：
- 研究背景：用"隨著...已成為...的重要議題"
- 避免直译英文表达
- 关键词与英文一一对应

**来源**: academic-paper/references/abstract_writing_guide.md
"""

PAPER_STRUCTURE_SKILL = """## Paper Structure Patterns — 6 Models (ARS)

### Pattern 1: IMRaD (最常用)
**适用**: 有原始数据的实证研究
**字数分配 (6000字参考):**
| 部分 | 占比 | 字数 |
|------|------|------|
| Introduction | 15% | 900 |
| Literature Review | 25% | 1,500 |
| Methodology | 15% | 900 |
| Results | 20% | 1,200 |
| Discussion | 20% | 1,200 |
| Conclusion | 5% | 300 |

### Pattern 2: Thematic Literature Review
**适用**: 综合已有研究、识别空白
**结构**: 引言 → Theme 1/2/3 → 跨主题综合 → 研究空白 → 结论

### Pattern 3: Case Study
**适用**: 深入分析一个或多个案例
**结构**: 引言 → 文献综述 → 案例背景 → 研究发现 → 跨案例分析 → 讨论 → 结论

### Pattern 4: Theoretical / Conceptual
**适用**: 提出新理论或框架
**结构**: 引言 → 文献综述与理论基础 → 理论建构(核心) → 理论评估与比较 → 结论

### Pattern 5: Policy Brief / White Paper
**适用**: 政策建议或实践指南
**结构**: Executive Summary → 问题定义 → 证据审查 → 政策选项 → 建议 → 实施路线图

### Pattern 6: Conference Paper
**适用**: 会议投稿，精简版
**字数**: 2,000-4,000

**来源**: academic-paper/references/paper_structure_patterns.md
"""

REVIEW_CRITERIA_SKILL = """## Review Criteria — 7 Universal Dimensions (ARS)

### 1. Originality — 权重 15%
| 5 | Proposes entirely new theory/method/evidence |
| 4 | Clear new insights or novel combinations |
| 3 | Incremental contribution, reasonable extension |
| 2 | Overlapping with existing literature |
| 1 | Essentially repeats known content |

### 2. Methodological Rigor — 权重 25%
| 5 | Impeccable design, innovative methods executed flawlessly |
| 4 | Sound design, appropriate methods, minor improvements possible |
| 3 | Basically acceptable, with design/execution limitations |
| 2 | Significant flaws affecting credibility of conclusions |
| 1 | Methods fundamentally unsuitable or contain serious errors |

### 3. Evidence Sufficiency — 权重 20%
| 5 | Rich, diverse, persuasive evidence exceeding expectations |
| 4 | Evidence sufficiently supports all major arguments |
| 3 | Most arguments supported, a few need supplementation |
| 2 | Key arguments lack sufficient evidence |
| 1 | Serious disconnect between arguments and evidence |

### 4. Argument Coherence — 权重 15%
| 5 | Clear arguments, rigorous logic, elegant structure |
| 4 | Smooth argumentation, occasional minor logical leaps |
| 3 | Basically coherent, inter-paragraph connections sometimes unclear |
| 2 | Multiple logical breaks, difficult to follow |
| 1 | Confused argumentation, core claims unidentifiable |

### 5. Writing Quality — 权重 10%
| 5 | Precise and fluent academic English/Chinese, model of scholarly writing |
| 4 | Clear language, minor imperfections |
| 3 | Generally readable, grammar or word choice issues |
| 2 | Frequent language issues affecting understanding |
| 1 | Language quality below reviewable standard |

### 6. Literature Integration — 权重 10%
| 5 | Comprehensive, contemporary, critically integrated, compelling gap argument |
| 4 | Covers major literature, good integration and positioning |
| 3 | Basic coverage, omissions or insufficient integration |
| 2 | Literature outdated, incomplete, or merely enumerated |
| 1 | Seriously insufficient or irrelevant to topic |

### 7. Significance & Impact — 权重 5%
| 5 | Could change policy, practice, or theoretical direction |
| 4 | Clear impact on a specific field or practice |
| 3 | Some academic or practical value |
| 2 | Limited scope of impact |
| 1 | Difficult to see significance |

### 论文类型特定标准（额外维度）
- **实证研究**: 假设可检验性、变量操作定义、内部/外部效度、统计报告完整性
- **理论/概念**: 理论创新性、论证的严密性、命题的可检验性
- **文献综述**: 检索系统性、筛选透明度、综合方法论

**来源**: academic-paper-reviewer/references/review_criteria_framework.md
"""

WRITING_JUDGMENT_SKILL = """## Writing Judgment Heuristics (ARS)

### The Clarity Test
For every paragraph, ask: "If I remove this paragraph, does the paper still make sense?"
- **Yes, nothing lost** → Delete
- **Yes, but context is lost** → Keep, but short
- **No, the argument breaks** → This is load-bearing — invest the most care

### The Reader's Journey
At any point, the reader should be able to answer:
1. **Where am I?** (Section structure, signposting)
2. **Why am I here?** (Connection to research question)
3. **What should I take away?** (Point of this section)
4. **Where am I going next?** (Transition logic)

If ANY is unclear → revise, regardless of content accuracy.

### The "So What" Hierarchy
| Section | Reader's "So What?" | Your Job |
|---------|--------------------|---------|
| Introduction | Why should I care? | Hook with real-world consequence or knowledge gap |
| Literature Review | What's missing? | Build to the gap, don't just summarize |
| Methodology | Can I trust the results? | Show rigor, acknowledge limitations |
| Results | What did you actually find? | Lead with the finding, not the statistical test |
| Discussion | What does this mean? | Connect back to the gap |
| Conclusion | What should I remember? | One sentence capturing the contribution |

### Discipline-Specific Voice
| Discipline | Typical Voice | What Makes It Credible |
|-----------|--------------|----------------------|
| Hard sciences | Impersonal, passive, hedged | Precision of measurement |
| Social sciences | Semi-personal, active, qualified | Transparency about limitations |
| Humanities | Personal, argumentative, interpretive | Depth of source engagement |
| Engineering | Direct, specification-oriented | Reproducibility of results |
| Medicine | Structured, protocol-focused | Adherence to reporting guidelines |

### Revision Decision Matrix
| Reviewer Says | Your Options |
|--------------|-------------|
| "Unclear" | Always rewrite — costs nothing |
| "Missing reference" | Add if genuinely fills gap |
| "Wrong method" | Evaluate, justify with evidence, or change |
| "Not novel enough" | Strengthen framing, don't add unnecessary analyses |
| "Too long" | Apply the Clarity Test paragraph by paragraph |

**来源**: academic-paper/references/writing_judgment_framework.md
"""

LATEX_AR_STANDARD_SKILL = """## LaTeX Article Template — APA 7.0 (ARS)

### Required Packages
```latex
\\documentclass[12pt, a4paper]{article}
\\usepackage[utf8]{inputenc}
\\usepackage[T1]{fontenc}
\\usepackage{times}                    % Times New Roman
\\usepackage[margin=1in]{geometry}     % 1-inch margins
\\usepackage{setspace}                 % Line spacing
\\doublespacing                        % APA requires double spacing
\\usepackage{amsmath}
\\usepackage{graphicx}
\\usepackage{booktabs}                 % Professional tables
\\usepackage{hyperref}
\\usepackage{natbib}
\\bibliographystyle{apalike}
```

### Structure
```
\\maketitle
\\begin{abstract} ... \\end{abstract}
\\section{Introduction}
\\section{Literature Review}
\\section{Methodology}
\\section{Results}
\\section{Discussion}
\\section{Conclusion}
\\subsection*{AI Disclosure}  ← Required: disclosure of AI tool use
\\bibliography{references}
```

### Figure Formatting (APA 7.0)
- Figure label: Bold ("Figure 1")
- Figure title: Italic, sentence case
- Caption below figure
- Axis labels: 8-10pt, with units
- Color palette: Viridis (continuous), Tol's palette (categorical, ≤8 groups)
- Colorblind-safe: use cividis for deuteranopia/protanopia

### Table Formatting
- Use booktabs: `\\toprule`, `\\midrule`, `\\bottomrule`
- No vertical lines in tables
- Table notes above the table

**来源**: academic-paper/references/latex_template_reference.md + statistical_visualization_standards.md
"""

RAISE_FRAMEWORK_SKILL = """## RAISE Framework — Responsible AI Use in Evidence Synthesis (ARS)

### Four Principles (applicable to all academic AI-assisted work)

**Principle 1 — Human Oversight**
AI should be used with meaningful human oversight, not as autonomous replacement.
- ✅ 明确说明人工审查者数量、资质和裁决机制
- ❌ 模糊描述如 "the authors reviewed the AI output"

**Principle 2 — Transparency**
Any AI use that makes or suggests judgments must be fully reported.
- ✅ 列出所有使用的AI工具、在哪一阶段、prompt/参数/版本
- ❌ 工具声明与使用不一致

**Principle 3 — Reproducibility**
AI-assisted research should be reproducible to a stated level.
- ✅ 记录模型版本、seed、prompt、数据访问细节
- ✅ 声明随机性（stochasticity）

**Principle 4 — Fit-for-purpose**
AI tools should be chosen and validated for specific tasks.
- ✅ 说明每个AI工具为什么用于该特定任务
- ✅ 提供至少一个验证引用
- ❌ "We used AI to save time" 不够

### AI Disclosure Template
```
This paper was prepared with the assistance of AI-powered tools:
- Tool: [name/version], Stage: [research/writing/review], Usage: [specific task]
All AI-generated content was reviewed and verified by the authors.
```

**来源**: shared/raise_framework.md
"""


# ─── Skill definitions for registry ───────────────────────────────────

def get_ars_skills() -> list[dict]:
    """Return ARS skills formatted for registration in the skill registry."""
    return [
        {
            "name": "writing/quality-check",
            "description": "Academic writing quality rules: de-AI terms, punctuation, throat-clearing, meta-commentary (ARS)",
            "domain": "writing",
            "content": WRITING_QUALITY_SKILL,
            "keywords": [
                "写作质量", "去AI", "润色", "修改", "proofread", "quality check",
                "delve", "em dash", "AI writing", "机器人", "throat-clearing",
                "学术写作", "academic writing style",
            ],
        },
        {
            "name": "writing/abstract",
            "description": "5-component abstract writing model: Background→Purpose→Method→Findings→Implications (ARS)",
            "domain": "writing",
            "content": ABSTRACT_WRITING_SKILL,
            "keywords": [
                "摘要", "abstract", "关键词", "双语", "bilingual",
                "五部分", "结构", "200字", "英文摘要", "中文摘要",
            ],
        },
        {
            "name": "writing/paper-structure",
            "description": "6 paper structure patterns with word allocation: IMRaD, literature review, case study, etc. (ARS)",
            "domain": "writing",
            "content": PAPER_STRUCTURE_SKILL,
            "keywords": [
                "论文结构", "大纲", "IMRaD", "文献综述", "案例研究",
                "paper structure", "outline", "章节", "字数分配",
                "structure architect", "组织",
            ],
        },
        {
            "name": "modeling/review-criteria",
            "description": "7 universal review dimensions with 5-level rubrics + paper-type-specific criteria (ARS)",
            "domain": "modeling",
            "content": REVIEW_CRITERIA_SKILL,
            "keywords": [
                "评审", "review", "评分", "标准", "原创性", "方法严谨性",
                "证据充分性", "review criteria", "rubric", "打分",
                "peer review", "论文评价", "质量标准",
            ],
        },
        {
            "name": "writing/judgment",
            "description": "Writing judgment heuristics: Clarity Test, Reader's Journey, So-What Hierarchy, Revision Matrix (ARS)",
            "domain": "writing",
            "content": WRITING_JUDGMENT_SKILL,
            "keywords": [
                "写作判断", "清晰度", "修改决策", "读者体验",
                "clarity test", "revision", "段落", "逻辑",
                "discipline voice", "学科风格", "修改矩阵",
            ],
        },
        {
            "name": "writing/latex-apa7",
            "description": "LaTeX article template with APA 7.0 formatting, figure standards, colorblind-safe palettes (ARS)",
            "domain": "writing",
            "content": LATEX_AR_STANDARD_SKILL,
            "keywords": [
                "LaTeX", "APA7", "模板", "排版", "图表", "Times New Roman",
                "doublespacing", "booktabs", "viridis", "colorblind",
                "figure", "table", "citation", "bibliography",
            ],
        },
        {
            "name": "meta/raise-framework",
            "description": "RAISE framework for responsible AI use: human oversight, transparency, reproducibility, fit-for-purpose (ARS)",
            "domain": "writing",
            "content": RAISE_FRAMEWORK_SKILL,
            "keywords": [
                "RAISE", "responsible AI", "AI disclosure", "AI使用声明",
                "透明度", "可复现", "人类监督", "ethics",
                "合规", "compliance", "声明",
            ],
        },
    ]