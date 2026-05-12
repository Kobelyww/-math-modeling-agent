"""内省器：Agent 读取自身代码与逻辑。"""

from __future__ import annotations

import ast
from pathlib import Path


class Introspector:
    """让 Agent 读取和理解自己的 Python 源码。"""

    def __init__(self, agent_source_path: str | Path) -> None:
        self.source_path = Path(agent_source_path)
        self.source = self.source_path.read_text(encoding="utf-8")

    def get_method_source(self, method_name: str) -> str | None:
        """提取指定方法的源代码。"""
        tree = ast.parse(self.source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == method_name:
                    return ast.get_source_segment(self.source, node)
        return None

    def get_class_source(self, class_name: str | None = None) -> str:
        """提取类定义的源码。"""
        tree = ast.parse(self.source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if class_name is None or node.name == class_name:
                    return ast.get_source_segment(self.source, node)
        return self.source

    def list_methods(self) -> list[str]:
        """列出文件中所有方法名。"""
        tree = ast.parse(self.source)
        return [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]

    def readable_summary(self) -> str:
        """生成代理代码的人类可读摘要。"""
        lines = [
            f"文件：{self.source_path.name}",
            f"方法列表：{', '.join(self.list_methods())}",
            "",
            "--- 完整源码 ---",
            self.source,
        ]
        return "\n".join(lines)
