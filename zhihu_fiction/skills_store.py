"""技能库管理：存储、检索和管理蒸馏后的创作技能卡。

支持：
- 按题材索引检索
- 关键词模糊搜索
- 技能卡增删改查
- 与 RAG 集成的接口
"""

from __future__ import annotations

from pathlib import Path

from .config import APP_ROOT

SKILLS_DIR = APP_ROOT / "data" / "skills"


class SkillsStore:
    """创作技能库管理器"""

    def __init__(self, skills_dir: Path | None = None) -> None:
        self._skills_dir = Path(skills_dir) if skills_dir else SKILLS_DIR
        self._skills_dir.mkdir(parents=True, exist_ok=True)

    def list_genres(self) -> list[str]:
        """列出所有已掌握的题材"""
        if not self._skills_dir.exists():
            return []
        return sorted(
            p.stem for p in self._skills_dir.glob("*.md")
        )

    def get_skill(self, genre: str) -> str | None:
        """获取指定题材的技能卡内容"""
        safe_genre = "".join(c for c in genre if c.isalnum() or c in ("-", "_"))
        filepath = self._skills_dir / f"{safe_genre}.md"
        if not filepath.exists():
            # 模糊匹配
            for p in self._skills_dir.glob("*.md"):
                if genre in p.stem or p.stem in genre:
                    return p.read_text(encoding="utf-8")
            return None
        return filepath.read_text(encoding="utf-8")

    def search(self, keyword: str) -> list[tuple[str, str]]:
        """关键词搜索技能卡，返回 (genre, snippet) 列表"""
        results: list[tuple[str, str]] = []
        for p in self._skills_dir.glob("*.md"):
            content = p.read_text(encoding="utf-8")
            if keyword.lower() in content.lower():
                # 提取匹配行及其上下文
                idx = content.lower().find(keyword.lower())
                start = max(0, idx - 50)
                end = min(len(content), idx + len(keyword) + 100)
                snippet = content[start:end].replace("\n", " ")
                results.append((p.stem, snippet))
        return results

    def save_skill(self, genre: str, content: str) -> Path:
        """保存或更新技能卡"""
        safe_genre = "".join(c for c in genre if c.isalnum() or c in ("-", "_"))
        filepath = self._skills_dir / f"{safe_genre}.md"
        filepath.write_text(content.strip() + "\n", encoding="utf-8")
        return filepath

    def delete_skill(self, genre: str) -> bool:
        """删除技能卡"""
        safe_genre = "".join(c for c in genre if c.isalnum() or c in ("-", "_"))
        filepath = self._skills_dir / f"{safe_genre}.md"
        if filepath.exists():
            filepath.unlink()
            return True
        return False

    def summarize_all(self) -> str:
        """生成所有技能卡的摘要（用于提供给 Agent 作为上下文）"""
        genres = self.list_genres()
        if not genres:
            return ""

        lines = []
        for genre in genres:
            content = self.get_skill(genre)
            if content:
                # 取前 200 字作为摘要
                preview = content[:200].replace("\n", " ").strip()
                lines.append(f"- **{genre}**: {preview}...")
        return "\n".join(lines)

    def get_context_for_agent(self, genre: str | None = None) -> str:
        """生成供 Agent 使用的技能上下文"""
        if genre:
            skill = self.get_skill(genre)
            if skill:
                return f"【{genre}题材创作技能卡】\n\n{skill}"
            return f"未找到 [{genre}] 题材的技能卡，将基于通用知识进行创作。"

        return f"【可用技能库】（{len(self.list_genres())} 个题材）\n\n{self.summarize_all()}"

    @property
    def is_empty(self) -> bool:
        return len(self.list_genres()) == 0
