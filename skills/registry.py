"""Skill Registry — modular prompt fragments loaded on demand.

Architecture inspired by Claude Code's Skills system:
- Skills are defined with metadata (domain, keywords, trigger conditions)
- Registry manages all available skills
- Resolver matches tasks to relevant skills
- Skills are loaded lazily (content not injected until needed)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

SKILLS_DIR = Path(__file__).resolve().parent


# ─── Skill definitions ───────────────────────────────────────────────────


@dataclass
class Skill:
    """A modular, on-demand prompt fragment for progressive disclosure.

    Each skill encodes domain knowledge that an agent may need for specific
    tasks — but is only loaded when the task context triggers it.
    """

    name: str
    """Unique skill identifier, e.g. 'modeling/optimization'."""

    description: str
    """One-line summary used for matching."""

    content: str
    """The prompt fragment injected when this skill is activated."""

    keywords: list[str] = field(default_factory=list)
    """Keywords that trigger this skill during task analysis."""

    domain: str = ""
    """Top-level domain: modeling, coding, writing, data, viz."""

    depends_on: list[str] = field(default_factory=list)
    """Other skill names this skill needs (loaded together)."""

    def render(self) -> str:
        """Render the skill content for injection into an agent prompt."""
        header = f"## {self.name}"
        return f"{header}\n{self.content}"


# ─── Pre-defined skills ─────────────────────────────────────────────────


_SKILLS: dict[str, Skill] = {}


def _register(skill: Skill) -> Skill:
    _SKILLS[skill.name] = skill
    return skill


# ── Modeling skills ───────────────────────────────────────────────────

_register(Skill(
    name="modeling/optimization",
    description="Linear, integer, nonlinear programming and multi-objective optimization",
    domain="modeling",
    keywords=["优化", "规划", "线性规划", "整数规划", "非线性", "多目标", "NSGA-II",
              "optimization", "linear programming", "integer programming", "LP", "ILP",
              "目标函数", "约束条件", "可行域", "单纯形", "分支定界", "拉格朗日"],
    content="""### 优化类模型选型指南

| 问题特征 | 推荐模型 | 求解方法 |
|----------|---------|----------|
| 线性目标+线性约束 | 线性规划(LP) | 单纯形法、内点法 |
| 整数变量+线性约束 | 整数规划(ILP/MILP) | 分支定界、割平面 |
| 多目标冲突 | 多目标优化 | NSGA-II、MOEA/D、加权和 |
| 非线性连续 | 非线性规划(NLP) | 梯度下降、拉格朗日乘子法 |
| 动态决策 | 动态规划(DP) | Bellman递推、值迭代 |
| 组合爆炸 | 元启发式 | GA、PSO、SA、ACO |
| 随机因素 | 随机规划 | 机会约束、情景树 |

**建模步骤：**
1. 确定决策变量（可控制的量）
2. 写出目标函数（最大化/最小化的指标）
3. 列出约束条件（等式/不等式/整数/范围）
4. 选择求解算法（问题规模→复杂度→方法）
5. 灵敏度分析（参数±20%变化对最优解的影响）

**参考框架：** scipy.optimize, pulp, cvxpy, platypus (多目标)"""
))

_register(Skill(
    name="modeling/prediction",
    description="Time series, regression, classification, and forecasting models",
    domain="modeling",
    keywords=["预测", "回归", "分类", "时间序列", "ARIMA", "LSTM", "XGBoost",
              "prediction", "forecast", "regression", "classification", "time series"],
    content="""### 预测类模型选型指南

| 数据特征 | 推荐模型 | 适用场景 |
|----------|---------|----------|
| 趋势+季节性 | ARIMA/SARIMA | 单变量时间序列 |
| 多变量+时序 | VAR/LSTM/GRU | 多元时间序列 |
| 线性关系 | 线性回归/Ridge/Lasso | 可解释性要求高 |
| 非线性关系 | XGBoost/LightGBM | 特征多、关系复杂 |
| 小样本 | GM(1,1)/贝叶斯 | n<30 |
| 概率预测 | GARCH/分位数回归 | 需要置信区间 |
| 序列到序列 | Seq2Seq/Transformer | 复杂依赖关系 |

**关键步骤：**
1. 数据平稳性检验（ADF test）
2. 自相关分析（ACF/PACF）
3. 训练/验证/测试划分（时间序列需按时间顺序）
4. 评估指标：MSE/MAE/MAPE/R²
5. 残差诊断（白噪声检验）"""
))

_register(Skill(
    name="modeling/evaluation",
    description="Multi-criteria evaluation: AHP, TOPSIS, entropy weight, fuzzy",
    domain="modeling",
    keywords=["评价", "评估", "层次分析", "AHP", "TOPSIS", "熵权法", "模糊",
              "evaluation", "assessment", "多指标", "打分", "权重", "排序"],
    content="""### 评价类模型选型指南

| 场景 | 推荐模型 | 核心思想 |
|------|---------|----------|
| 专家可两两比较 | AHP（层次分析法） | 主观权重+一致性检验 |
| 有原始数据 | 熵权法 | 数据驱动客观权重 |
| 多方案排序 | TOPSIS | 距理想解最近 |
| 模糊信息 | 模糊综合评价 | 处理模糊性 |
| 效率评价 | DEA（数据包络） | 多投入多产出 |
| 风险综合 | 贝叶斯网络 | 概率依赖关系 |
| 定性指标多 | 灰色关联分析 | 部分信息已知 |

**AHP步骤：**
1. 构建递阶层次结构（目标→准则→方案）
2. 构造判断矩阵（1-9标度法）
3. 计算权重向量（特征向量法）
4. 一致性检验（CR<0.1通过）
5. 层次总排序

**TOPSIS步骤：**
1. 指标正向化（极小→极大，中间→极大）
2. 标准化（消除量纲）
3. 确定正/负理想解
4. 计算各方案到理想解的欧氏距离
5. 计算相对贴近度并排序"""
))

_register(Skill(
    name="modeling/dynamics",
    description="Differential equations, cellular automata, agent-based models",
    domain="modeling",
    keywords=["微分方程", "ODE", "PDE", "元胞自动机", "智能体", "ABM",
              "动力系统", "传播", "扩散", "differential", "cellular automata",
              "agent-based", "dynamic", "相图", "稳定性", "不动点"],
    content="""### 动力系统类模型选型指南

| 场景 | 推荐模型 | 求解方法 |
|------|---------|----------|
| 连续变化 | ODE（常微分方程） | Euler/RK4/scipy.integrate |
| 时空演化 | PDE（偏微分方程） | 有限差分/有限元/FiPy |
| 离散步骤 | 差分方程 | 递推求解 |
| 局部规则全局涌现 | 元胞自动机(CA) | numpy + 网格迭代 |
| 异质个体交互 | 智能体模型(ABM) | Mesa/自建OOP框架 |
| 混沌系统 | Lorenz/Rössler | 数值仿真+相图分析 |

**ODE建模流程：**
1. 识别状态变量（S, I, R等）
2. 建立变化率方程 dX/dt = f(X, t, params)
3. 稳定性分析（Jacobi矩阵，特征值）
4. 数值求解（scipy.integrate.solve_ivp）
5. 参数敏感性（分岔分析）

**CA建模流程：**
1. 定义网格规模与边界条件
2. 定义状态空间（0/1，S/I/R等）
3. 定义邻域（Moore/von Neumann）
4. 定义转移规则
5. 可视化时空演化（imshow动画）"""
))

_register(Skill(
    name="modeling/network-graph",
    description="Graph theory, network flow, shortest path, community detection",
    domain="modeling",
    keywords=["图论", "网络", "最短路径", "最大流", "社区发现", "graph",
              "network", "Dijkstra", "Ford-Fulkerson", "渗流", "中心性"],
    content="""### 图论与网络模型选型指南

| 问题类型 | 推荐算法 | 库 |
|----------|---------|-----|
| 最短路径 | Dijkstra/A*/Floyd | networkx |
| 最大流/最小割 | Ford-Fulkerson/Edmonds-Karp | networkx |
| 最小生成树 | Prim/Kruskal | networkx |
| 社区发现 | Louvain/Girvan-Newman | networkx, python-louvain |
| 中心性分析 | betweenness/closeness/eigenvector | networkx |
| 级联传播 | SIR/SIS 在网络上 | 自建+networkx |
| 渗流分析 | bond/site percolation | numpy+networkx |

**常用库：** networkx (分析), igraph (大规模), matplotlib (可视化)
**注意：** 先分析复杂网络统计特性（度分布、聚类系数、平均路径长度）"""
))

_register(Skill(
    name="modeling/sensitivity",
    description="Sensitivity analysis, Monte Carlo simulation, uncertainty quantification",
    domain="modeling",
    keywords=["灵敏度", "敏感性", "蒙特卡洛", "参数变化", "不确定性",
              "sensitivity", "Monte Carlo", "±20%", "robustness", "扰动"],
    content="""### 灵敏度分析标准流程

**MCM/ICM竞赛要求**：每个模型必须包含灵敏度分析。

**标准方法：**
1. **参数扰动法**：对每个关键参数 ±10%、±20%、±30%，观察输出变化
2. **全局敏感性**：Sobol指数、Morris方法（SALib库）
3. **蒙特卡洛模拟**：参数分布采样→N次仿真→输出分布统计

**Python实现框架：**
```python
import numpy as np
def sensitivity_analysis(model_func, param_ranges, perturbation_levels=[0.8, 0.9, 1.0, 1.1, 1.2]):
    results = {}
    for param_name, base_value in param_ranges.items():
        param_results = []
        for factor in perturbation_levels:
            perturbed = base_value * factor
            output = model_func(**{param_name: perturbed})
            param_results.append((factor, output))
        results[param_name] = param_results
    return results
```

**可视化：** 龙卷风图(Tornado plot)展示各参数影响力"""
))

# ── Writing skills ─────────────────────────────────────────────────────

_register(Skill(
    name="writing/academic-structure",
    description="MCM/ICM paper structure, abstract writing, de-AI-fication rules",
    domain="writing",
    keywords=["论文", "结构", "摘要", "写作", "LaTeX", "MCM", "ICM", "去AI",
              "paper", "abstract", "structure", "academic writing", "机器人"],
    content="""### MCM/ICM 论文结构标准

**必须按以下顺序组织：**
1. **摘要** (800-1000字)：独立文档，包含问题+方法+关键数值结果+创新点
2. **引言**：问题背景→已有研究局限→本文贡献
3. **模型假设**：逐条列出并论证合理性（缺一不可）
4. **符号说明**：booktabs三线表，变量/含义/单位三列
5. **模型构建与求解**：分问题→子模型→求解→结果分析
6. **灵敏度分析**：参数±20%，展示鲁棒性
7. **模型评价**：优点+缺点+改进方向
8. **参考文献**：按引用顺序排列
9. **附录**：完整代码+数据表格

**去AI化铁律：**
- ❌ "X被用来促进Y的解决" → ✅ "我们用X解决Y"
- ❌ "值得注意的是" → ✅ "需要注意"
- ❌ "在本文中，我们将会..." → ✅ "本文..."
- ❌ "该方法具有显著的优势" → ✅ "该方法将误差降低36%"
- 不编造参考文献、数据、引用或数学定理（零容忍）

**摘要检查清单：**
- [ ] 第一句：问题核心是什么
- [ ] 第二~四句：每个子问题的模型+方法+关键数值结果
- [ ] 倒数第二句：主要创新点
- [ ] 最后一句：结论或推广价值"""
))

_register(Skill(
    name="writing/latex-standards",
    description="LaTeX compilation standards, font sizes, figure requirements",
    domain="writing",
    keywords=["LaTeX", "编译", "字体", "排版", "图表", "pdflatex", "ctexart"],
    content="""### LaTeX 编译标准

**文档类：** ctexart (12pt, a4paper)
**必须加载的包：** amsmath, amssymb, booktabs, graphicx, geometry, hyperref
**字号规范（Nature Skills）：**
- 标题：14pt
- 章节标题：12pt
- 正文：10pt
- 坐标轴标签：12pt
- 刻度标签：10pt
- 字体：Arial无衬线（英文），宋体/黑体（中文）
- 表格：booktabs三线表，禁止竖线

**图表要求：**
- 每个图表必须有 \\caption 和引用
- \\includegraphics 配 \\label
- 图表解读要点写在 caption 中
- 保存到 output/ 目录

**编译命令：**
```bash
pdflatex -interaction=nonstopmode -output-directory=output paper.tex
pdflatex -interaction=nonstopmode -output-directory=output paper.tex  # 跑两遍
```
"""
))

_register(Skill(
    name="writing/math-notation",
    description="Mathematical notation standards, amsmath usage, equation formatting",
    domain="writing",
    keywords=["数学符号", "公式", "amsmath", "equation", "notation",
              "角标", "求和", "积分", "矩阵"],
    content="""### 数学符号规范

**LaTeX公式环境：**
- 行内公式：`$...$`
- 独立公式：`\\begin{equation} ... \\end{equation}`
- 多行对齐：`\\begin{align} ... \\end{align}`
- 分段函数：`\\begin{cases} ... \\end{cases}`
- 矩阵：`\\begin{pmatrix} ... \\end{pmatrix}` 或 `\\begin{bmatrix}`

**符号惯例：**
- 向量：`\\mathbf{x}` 或 `\\boldsymbol{x}`
- 矩阵：`\\mathbf{A}` 大写粗体
- 转置：`\\mathbf{A}^\\top`
- 最优值：`x^*` 或 `\\hat{x}`
- 求和范围：`\\sum_{i=1}^{n}`”
- 导数：`\\frac{\\partial f}{\\partial x}`

**引用格式：**
- 公式引用：`\\label{eq:name}` + `\\eqref{eq:name}`
- 图表引用：`\\label{fig:name}` + `\\ref{fig:name}`
- 文献引用：`\\cite{ref1}` (使用 thebibliography 环境)
"""
))

# ── Coding skills ──────────────────────────────────────────────────────

_register(Skill(
    name="coding/algorithms",
    description="Algorithm design, numerical computing, scipy/numpy best practices",
    domain="coding",
    keywords=["算法", "numpy", "scipy", "数值计算", "向量化", "矩阵运算",
              "algorithm", "optimization", "数值稳定性", "复杂度"],
    content="""### 数值计算最佳实践

**核心原则：**
1. **向量化优先**：用 numpy 数组运算替代 Python 循环
2. **稀疏矩阵**：scipy.sparse 处理大型稀疏问题
3. **数值稳定性**：log-sum-exp 避免下溢，safe division 避免除零
4. **缓存友好**：连续内存访问，numpy 默认 C-order

**常用数值库：**
- `scipy.optimize` — minimize, linprog, curve_fit, root
- `scipy.integrate` — solve_ivp, quad, trapz
- `scipy.stats` — 概率分布、统计检验
- `scipy.sparse.linalg` — 稀疏矩阵求解
- `numpy.linalg` — 矩阵分解、求逆

**复杂度参考：**
- 矩阵乘法：O(n³) naive, O(n².8) Strassen, O(n².37) 理论最优
- 线性规划：O(n³) 内点法实践，指数最坏
- Dijkstra：O(E + V log V) 二叉堆
- PCA/SVD：O(min(mn², m²n)) 经济SVD
"""
))

_register(Skill(
    name="coding/debugging",
    description="Common Python pitfalls, debugging strategies, numerical issues",
    domain="coding",
    keywords=["调试", "bug", "错误", "异常", "数值不稳定", "边界条件",
              "debug", "overflow", "NaN", "inf", "类型错误"],
    content="""### Python 代码常见问题清单

**检查清单（按严重程度排序）：**
1. **数值问题**：
   - 除零保护：`a / (b + 1e-12)`
   - NaN/Inf检查：`np.isnan(x).any()`, `np.isinf(x).any()`
   - 数值溢出：大数乘积/指数运算前先验证范围
   - 精度损失：避免大数加小数、相近数相减

2. **逻辑缺陷**：
   - 边界条件是否处理？（空列表、零值、负值）
   - 循环终止条件是否正确？
   - 递归收敛准则是否可达到？
   - 索引是否正确？（0-index vs 1-index，包含/不包含）

3. **性能问题**：
   - 是否在循环内创建了不必要的 numpy 数组？
   - 是否对 Pandas DataFrame 使用了 iterrows()？
   - 是否重复计算了可以缓存的值？

4. **依赖检查**：
   - 是否缺少 `import`？
   - 包的版本是否兼容？
   - 是否有可选的 C 扩展加速？（numba, cython）

**快速修复模板：**
```python
# 安全除法
def safe_div(a, b, default=0.0):
    return np.divide(a, b, out=np.full_like(a, default, dtype=float), where=b != 0)

# 数值稳定softmax
def stable_softmax(x):
    x_shifted = x - np.max(x, axis=-1, keepdims=True)
    e = np.exp(np.clip(x_shifted, -500, 500))
    return e / e.sum(axis=-1, keepdims=True)
```
"""
))

_register(Skill(
    name="coding/visualization",
    description="Matplotlib best practices, Nature-style plots, chart types",
    domain="coding",
    keywords=["可视化", "绑图", "画图", "matplotlib", "图表", "plot",
              "visualization", "figure", "subplot", "Nature"],
    content="""### 可视化最佳实践

**图表类型选择：**
- 趋势 → 折线图 (plt.plot)
- 分布 → 直方图 (plt.hist)、箱线图 (plt.boxplot)
- 对比 → 柱状图 (plt.bar)、分组柱状图
- 关系 → 散点图 (plt.scatter)、热力图 (plt.imshow)
- 组成 → 饼图 (plt.pie)、堆叠面积图
- 多指标 → 雷达图、平行坐标图

**Nature风格配置：**
```python
plt.rcParams.update({
    'font.size': 10,
    'axes.labelsize': 12,
    'axes.titlesize': 14,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'legend.fontsize': 9,
    'figure.dpi': 150,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
})
```

**规范：**
- 坐标轴必须有标签（含单位）
- 图例置入图内空白处或下方
- 颜色选择优先用 viridis/plasma/tab10
- 避免饼图（看不准比例）和3D饼图（面积扭曲）
- 保存为 PDF（矢量）或 PNG（300dpi）
"""
))

# ── Data skills ────────────────────────────────────────────────────────

_register(Skill(
    name="data/exploration",
    description="Data preprocessing, EDA, missing value handling, feature engineering",
    domain="data",
    keywords=["数据", "EDA", "预处理", "缺失值", "特征工程", "清洗",
              "data", "preprocessing", "missing", "feature engineering",
              "标准化", "归一化", "异常值"],
    content="""### 数据预处理标准流程

**1. 数据质量检查：**
- 形状、各列数据类型
- 缺失率统计（每列 missing%）
- 重复行检测
- 异常值检测（IQR法 / 3σ法）

**2. 缺失值处理策略：**
| 缺失率 | 策略 |
|--------|------|
| <5% | 均值/中位数填充（数值）/众数填充（类别） |
| 5%-20% | KNN插补 / 多重插补 |
| 20%-50% | 用模型预测缺失值 / 创建缺失指示变量 |
| >50% | 删除该特征 |

**3. 特征工程：**
- 数值特征：标准化(StandardScaler) / 归一化(MinMaxScaler)
- 类别特征：One-Hot / Label Encoding
- 时间特征：提取年/月/日/星期/小时/是否周末
- 衍生特征：比率、差值、交互项

**4. 探索性分析报告要素：**
- 各变量分布图（直方图 + 箱线图）
- 两两相关系数矩阵热力图
- 目标变量 vs 各特征散点图
- PCA/tsNE降维可视化（看聚类趋势）
"""
))


# ─── Registry ───────────────────────────────────────────────────────────


class SkillRegistry:
    """Manages the full catalog of loadable skills.

    Like Claude Code's skill system, skills are lazy-loaded: their content
    is only injected into prompts when a task requires them.
    """

    def __init__(self, skills: dict[str, Skill] | None = None) -> None:
        self._skills: dict[str, Skill] = dict(skills or _SKILLS)

    @property
    def list_all(self) -> list[Skill]:
        return list(self._skills.values())

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def by_domain(self, domain: str) -> list[Skill]:
        return [s for s in self._skills.values() if s.domain == domain]

    def search(self, query: str) -> list[Skill]:
        """Simple keyword-based skill search."""
        q = query.lower()
        scored: list[tuple[int, Skill]] = []
        for skill in self._skills.values():
            score = 0
            for kw in skill.keywords:
                if kw.lower() in q:
                    score += 1
            if score > 0:
                scored.append((score, skill))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in scored]

    def list_domains(self) -> list[str]:
        return sorted(set(s.domain for s in self._skills.values() if s.domain))

    def summarize_available(self) -> str:
        """Generate a brief catalog summary for inclusion in agent prompts."""
        by_domain: dict[str, list[str]] = {}
        for s in self._skills.values():
            domain = s.domain or "other"
            by_domain.setdefault(domain, []).append(f"  - {s.name}: {s.description}")
        lines = ["### Available Skills (load on demand)"]
        for domain in sorted(by_domain):
            lines.append(f"**{domain}**:")
            lines.extend(by_domain[domain])
        return "\n".join(lines)


class SkillResolver:
    """Matches tasks to relevant skills and assembles the skill context.

    Like Claude Code's skill loading, this resolves which skills to load
    based on the task description and injects only those that are relevant.
    """

    def __init__(self, registry: SkillRegistry | None = None, max_skills: int = 4) -> None:
        self.registry = registry or SkillRegistry()
        self.max_skills = max_skills

    def resolve(self, task: str, domain_hint: str | None = None) -> list[Skill]:
        """Find skills relevant to a task description.

        Returns at most max_skills skills, ranked by keyword match score.
        """
        if domain_hint:
            candidates = self.registry.by_domain(domain_hint)
        else:
            candidates = self.registry.list_all

        # Score each skill by keyword overlap
        scored: list[tuple[int, Skill]] = []
        task_lower = task.lower()
        for skill in candidates:
            score = sum(1 for kw in skill.keywords if kw.lower() in task_lower)
            if score > 0:
                scored.append((score, skill))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in scored[:self.max_skills]]

    def render_skills(self, skills: list[Skill]) -> str:
        """Render a list of skills into a single prompt fragment."""
        if not skills:
            return ""
        blocks = [s.render() for s in skills]
        return "\n\n---\n\n".join(blocks)

    def resolve_and_render(self, task: str, domain_hint: str | None = None) -> str:
        """Resolve skills for a task and return rendered prompt content."""
        skills = self.resolve(task, domain_hint)
        return self.render_skills(skills)


# ─── Convenience function ───────────────────────────────────────────────

_default_registry = SkillRegistry()
_default_resolver = SkillResolver(registry=_default_registry)


def resolve_skills(task: str, domain_hint: str | None = None, max_skills: int = 4) -> str:
    """Quick access: resolve skills for a task and return rendered content."""
    resolver = SkillResolver(registry=_default_registry, max_skills=max_skills)
    return resolver.resolve_and_render(task, domain_hint)


# ─── Load ARS skills at import time ───────────────────────────────────

def _load_ars_skills() -> None:
    """Import and register skills from the academic-research-skills integration."""
    try:
        from .academic_ars import get_ars_skills  # noqa: PLC0415
        for skill_data in get_ars_skills():
            skill = Skill(
                name=skill_data["name"],
                description=skill_data["description"],
                domain=skill_data["domain"],
                content=skill_data["content"],
                keywords=skill_data["keywords"],
            )
            _register(skill)
    except ImportError:
        pass


_load_ars_skills()