"""自演化 Agent 系统：读取自身代码 → 分析弱点 → 修改策略 → 沙箱验证。"""

from .introspector import Introspector
from .modifier import Modifier
from .sandbox import Sandbox

__all__ = ["Introspector", "Modifier", "Sandbox"]
