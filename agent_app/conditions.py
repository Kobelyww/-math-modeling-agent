"""终止条件系统 — 受 AutoGen conditions 模块启发。

提供多种可组合的终止条件，用于控制 Agent 评审循环和求解流程。
每个条件都是可调用对象，返回 StopMessage 或 None。
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class StopMessage:
    """终止信号，由条件检查返回。"""
    content: str
    source: str


class BaseCondition(ABC):
    """终止条件基类。"""

    @abstractmethod
    def __call__(self, messages: list, current_round: int, elapsed: float) -> StopMessage | None:
        """检查是否应终止。返回 StopMessage 表示终止，None 表示继续。"""
        ...

    @abstractmethod
    def reset(self) -> None:
        """重置条件状态。"""
        ...


class MaxRoundCondition(BaseCondition):
    """达到最大轮次时终止。"""

    def __init__(self, max_rounds: int) -> None:
        self.max_rounds = max_rounds

    def __call__(self, messages: list, current_round: int, elapsed: float) -> StopMessage | None:
        if current_round >= self.max_rounds:
            return StopMessage(
                content=f"已达最大轮次 {self.max_rounds}",
                source="MaxRoundCondition",
            )
        return None

    def reset(self) -> None:
        pass


class TokenBudgetCondition(BaseCondition):
    """总 token 消耗超过预算时终止。

    追踪 prompt_tokens + completion_tokens 的实际 LLM 消耗。
    """

    def __init__(self, max_total_tokens: int = 200000) -> None:
        self.max_total_tokens = max_total_tokens
        self._accumulated = 0

    @property
    def accumulated(self) -> int:
        return self._accumulated

    def add_usage(self, prompt_tokens: int, completion_tokens: int) -> None:
        self._accumulated += prompt_tokens + completion_tokens

    def __call__(self, messages: list, current_round: int, elapsed: float) -> StopMessage | None:
        if self._accumulated >= self.max_total_tokens:
            return StopMessage(
                content=f"Token 预算耗尽：{self._accumulated}/{self.max_total_tokens}",
                source="TokenBudgetCondition",
            )
        return None

    def reset(self) -> None:
        self._accumulated = 0


class TimeoutCondition(BaseCondition):
    """超时自动终止。"""

    def __init__(self, timeout_seconds: float = 300.0) -> None:
        self.timeout_seconds = timeout_seconds
        self._start_time: float | None = None

    @property
    def elapsed(self) -> float:
        if self._start_time is None:
            return 0.0
        return time.monotonic() - self._start_time

    def start(self) -> None:
        self._start_time = time.monotonic()

    def __call__(self, messages: list, current_round: int, elapsed: float) -> StopMessage | None:
        if self.elapsed >= self.timeout_seconds:
            return StopMessage(
                content=f"超时 {self.timeout_seconds}s（已运行 {self.elapsed:.0f}s）",
                source="TimeoutCondition",
            )
        return None

    def reset(self) -> None:
        self._start_time = None


class QualityThresholdCondition(BaseCondition):
    """适应度得分达到阈值时提前退出评审循环。

    需要外部调用 update() 更新当前得分。
    """

    def __init__(self, threshold: float = 0.85) -> None:
        self.threshold = threshold
        self._current_score = 0.0

    def update(self, score: float) -> None:
        self._current_score = score

    def __call__(self, messages: list, current_round: int, elapsed: float) -> StopMessage | None:
        if self._current_score >= self.threshold:
            return StopMessage(
                content=f"质量达标：{self._current_score:.2f} >= {self.threshold}",
                source="QualityThresholdCondition",
            )
        return None

    def reset(self) -> None:
        self._current_score = 0.0


class ExternalCondition(BaseCondition):
    """外部信号终止（用户中断、WebSocket 断开等）。"""

    def __init__(self) -> None:
        self._set_flag = False

    def set(self) -> None:
        self._set_flag = True

    @property
    def is_set(self) -> bool:
        return self._set_flag

    def __call__(self, messages: list, current_round: int, elapsed: float) -> StopMessage | None:
        if self._set_flag:
            return StopMessage(content="外部中断请求", source="ExternalCondition")
        return None

    def reset(self) -> None:
        self._set_flag = False


class CompoundCondition(BaseCondition):
    """组合多个条件，任一触发即终止（OR 逻辑）。"""

    def __init__(self, *conditions: BaseCondition) -> None:
        self.conditions = list(conditions)

    def add(self, condition: BaseCondition) -> None:
        self.conditions.append(condition)

    def __call__(self, messages: list, current_round: int, elapsed: float) -> StopMessage | None:
        for cond in self.conditions:
            result = cond(messages, current_round, elapsed)
            if result is not None:
                return result
        return None

    def reset(self) -> None:
        for cond in self.conditions:
            cond.reset()


def check_conditions(
    conditions: list[BaseCondition],
    messages: list,
    current_round: int,
    elapsed: float,
) -> StopMessage | None:
    """检查多个条件，返回第一个触发的 StopMessage 或 None。"""
    for cond in conditions:
        result = cond(messages, current_round, elapsed)
        if result is not None:
            return result
    return None
