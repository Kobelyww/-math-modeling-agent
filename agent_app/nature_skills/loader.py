
"""Nature Skills 加载器。读取技能文件并注入到 Agent prompt 中。"""

from __future__ import annotations

from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent


def _strip_frontmatter(text: str) -> str:
    """去除 YAML frontmatter (--- ... ---)。"""
    if text.startswith("---"):
        parts = text.split("---", 2)
        return parts[2].strip() if len(parts) >= 3 else text
    return text.strip()


class SkillLoader:
    def __init__(self, skills_dir: Path | None = None) -> None:
        self._dir = skills_dir or SKILLS_DIR
        self._cache: dict[str, str] = {}

    def load(self, name: str, subdir: str = "Rules") -> str | None:
        cache_key = f"{subdir}/{name}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        candidates = list(self._dir.rglob(f"{name}*"))
        for p in candidates:
            if p.suffix in (".md", ".txt", ".py"):
                content = _strip_frontmatter(p.read_text(encoding="utf-8", errors="ignore"))
                self._cache[cache_key] = content
                return content
        return None

    def load_rule(self, rule_name: str) -> str | None:
        return self.load(rule_name, "Rules")

    def load_viz_template(self, template_name: str) -> str | None:
        return self.load(template_name, "Viz_Templates")

    def load_tool(self, tool_name: str) -> str | None:
        return self.load(tool_name, "Tools")

    def summarize_rules(self, rule_names: list[str]) -> str:
        """加载多个规则文件并拼接为注入用文本块。"""
        parts = []
        for name in rule_names:
            content = self.load_rule(name)
            if content:
                header = name.replace(".md", "").replace("_", " ").title()
                parts.append(f"## {header}\n\n{content}")
        return "\n\n---\n\n".join(parts)


_loader = SkillLoader()


def get_writing_rules() -> str:
    """获取学术写作规范（注入到 WriterAgent）。"""
    return _loader.summarize_rules(["xueshu", "Summary", "font_standard", "output"])


def get_model_reference() -> str:
    """获取模型选型参考（注入到 ModelerAgent + SynthesizerAgent）。"""
    return _loader.summarize_rules(["existing_models", "Summary"])


def get_viz_template(template_name: str) -> str | None:
    """获取 Nature 风格的绑图模板代码。"""
    return _loader.load_viz_template(template_name)


def get_summary_template() -> str:
    """获取论文摘要模板和写作技巧。"""
    return _loader.load_rule("Summary") or ""


def list_available_skills() -> dict[str, list[str]]:
    rules = [p.stem for p in (SKILLS_DIR / "Rules").glob("*.md")]
    viz = [p.stem for p in (SKILLS_DIR / "Viz_Templates").glob("*.py")]
    tools = [p.stem for p in (SKILLS_DIR / "Tools").glob("*.py")]
    return {"rules": rules, "viz_templates": viz, "tools": tools}
