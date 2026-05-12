"""策略优化器：分析弱点 → 生成改进的 System Prompt。"""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel

OPTIMIZE_PROMPT = """你是狼人杀 AI 策略优化师。请分析以下角色的表现数据，找出弱点并生成改进后的 System Prompt。

## 当前 Prompt
{current_prompt}

## 表现数据
- 角色：{role}
- 胜率：{win_rate:.0%}
- 投票准确率：{vote_accuracy:.0%}
- 存活率：{survival_rate:.0%}
- 语音质量均分：{speech_quality:.1f}/5

## 关键问题（从多局对局中提取）
{weaknesses}

## 优化要求
1. 保持原有结构完整性
2. 针对性修复上述弱点
3. 增加 1-2 条具体的新策略指南
4. 不要超过原有字数 30%

请直接输出优化后的完整 System Prompt。"""


class StrategyOptimizer:
    def __init__(self, llm: BaseChatModel) -> None:
        self.llm = llm

    def optimize(
        self,
        role: str,
        current_prompt: str,
        metrics: dict,
        weaknesses: str,
    ) -> str:
        """基于表现数据优化角色的 System Prompt。"""
        prompt = OPTIMIZE_PROMPT.format(
            current_prompt=current_prompt,
            role=role,
            win_rate=metrics.get("win_rate", 0.5),
            vote_accuracy=metrics.get("vote_accuracy", 0.5),
            survival_rate=metrics.get("survival_rate", 0.5),
            speech_quality=metrics.get("speech_quality", 3.0),
            weaknesses=weaknesses,
        )
        result = self.llm.invoke(prompt)
        content = result.content if hasattr(result, "content") else str(result)
        if isinstance(content, list):
            content = "".join(
                str(item.get("text", item)) if isinstance(item, dict) else str(item)
                for item in content
            )
        return content

    def analyze_weaknesses(
        self,
        role: str,
        game_logs: list[dict],
    ) -> str:
        """分析多局对局中的共同弱点。"""
        events_summary = []
        for log in game_logs:
            role_events = [
                e for e in log.get("events", [])
                if e.get("role") == role
            ]
            events_summary.append(
                f"对局（{len(role_events)}个行动）：" +
                ", ".join(f"{e['action']}" for e in role_events[:10])
            )

        analyze_prompt = (
            f"分析 {role} 在多局狼人杀对局中的表现问题。\n\n"
            + "\n".join(events_summary[:5])
            + "\n\n请列出 3-5 个具体的弱点和改进建议。"
        )

        result = self.llm.invoke(analyze_prompt)
        content = result.content if hasattr(result, "content") else str(result)
        if isinstance(content, list):
            content = "".join(
                str(item.get("text", item)) if isinstance(item, dict) else str(item)
                for item in content
            )
        return content
