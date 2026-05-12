"""修改器：LLM 分析表现 → 提出代码修改 → 验证安全性。"""

from __future__ import annotations

import ast

from langchain_core.language_models import BaseChatModel

MODIFY_PROMPT = """你是 AI 代码优化师。请分析以下狼人杀 Agent 的表现数据，并修改其策略代码以提升胜率。

## 当前 Agent 源码
```python
{source_code}
```

## 表现数据
- 角色：{role}
- 胜率：{win_rate:.0%}
- 关键问题：{weaknesses}

## 对局关键事件
{key_events}

## 修改要求
1. 只能修改策略逻辑（Prompt 内容、决策逻辑），不能修改引擎代码
2. 保持类的接口不变
3. 修改后的代码必须能通过 Python AST 解析
4. 不允许使用 eval/exec/__import__/subprocess/open 等危险函数

请输出完整的修改后的文件内容。只输出代码，不要解释。"""


class Modifier:
    def __init__(self, llm: BaseChatModel) -> None:
        self.llm = llm

    def propose_changes(
        self,
        source_code: str,
        role: str,
        win_rate: float,
        weaknesses: str,
        key_events: str,
    ) -> str:
        """基于表现数据提出代码修改方案。"""
        prompt = MODIFY_PROMPT.format(
            source_code=source_code,
            role=role,
            win_rate=win_rate,
            weaknesses=weaknesses,
            key_events=key_events,
        )
        result = self.llm.invoke(prompt)
        content = result.content if hasattr(result, "content") else str(result)
        if isinstance(content, list):
            content = "".join(
                str(item.get("text", item)) if isinstance(item, dict) else str(item)
                for item in content
            )
        # 提取代码块
        import re
        match = re.search(r"```(?:python)?\n(.*?)```", content, re.DOTALL)
        return match.group(1).strip() if match else content.strip()

    @staticmethod
    def validate(new_code: str) -> tuple[bool, str]:
        """验证修改后的代码是否安全且可解析。"""
        try:
            tree = ast.parse(new_code)
        except SyntaxError as e:
            return False, f"语法错误: {e}"

        forbidden = {"eval", "exec", "__import__"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in forbidden:
                    return False, f"禁止使用: {node.func.id}"
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in ("os", "subprocess", "sys", "shutil"):
                        return False, f"禁止导入: {alias.name}"

        return True, "验证通过"
