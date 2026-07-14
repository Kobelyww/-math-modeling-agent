from __future__ import annotations

from dataclasses import dataclass

from agent_app.domain.contracts import SubproblemType


@dataclass(frozen=True)
class Classification:
    primary: SubproblemType
    secondary: list[SubproblemType]


KEYWORDS: list[tuple[SubproblemType, tuple[str, ...]]] = [
    (SubproblemType.SAMPLING_TEST, ("抽样", "信度", "置信", "标称值", "次品率", "假设检验")),
    (SubproblemType.OPTIMIZATION, ("最优", "优化", "决策", "利润", "成本", "拆解", "调度", "规划")),
    (SubproblemType.PREDICTION, ("预测", "回归", "时间序列", "趋势", "forecast")),
    (SubproblemType.EVALUATION, ("评价", "排名", "指标", "综合评价", "权重")),
    (SubproblemType.SIMULATION, ("仿真", "模拟", "蒙特卡洛", "排队")),
    (SubproblemType.GRAPH_NETWORK, ("网络", "路径", "流量", "图", "节点")),
    (SubproblemType.STATISTICS, ("不确定", "估计", "区间", "方差", "分布")),
    (SubproblemType.OPERATIONS_RESEARCH, ("工序", "生产", "库存", "运输", "装配")),
    (SubproblemType.DATA_MINING, ("聚类", "分类", "特征", "异常")),
]


def classify_subproblem(text: str) -> Classification:
    normalized = text.lower()
    if ("不确定" in text) or ("重新" in text and "抽样" in text and ("问题2" in text or "问题3" in text)):
        return Classification(primary=SubproblemType.STATISTICS, secondary=[SubproblemType.SAMPLING_TEST])

    scores: list[tuple[int, SubproblemType]] = []
    priority = {problem_type: index for index, (problem_type, _) in enumerate(KEYWORDS)}
    for problem_type, keywords in KEYWORDS:
        score = sum(1 for keyword in keywords if keyword.lower() in normalized)
        if score:
            scores.append((score, problem_type))
    if not scores:
        return Classification(primary=SubproblemType.ANALYSIS, secondary=[])
    scores.sort(key=lambda item: (-item[0], priority[item[1]]))
    primary = scores[0][1]
    secondary = [problem_type for _, problem_type in scores[1:3] if problem_type != primary]
    return Classification(primary=primary, secondary=secondary)
