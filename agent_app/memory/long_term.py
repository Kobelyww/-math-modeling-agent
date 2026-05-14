"""长期记忆：跨会话持久化知识库（SQLite + FTS5 全文搜索）。

存储三类知识：
1. problem — 解过的题（题目、方案摘要、关键模型）
2. pattern  — 成功的建模模式（可跨题复用）
3. mistake — 犯过的错误和修正（防重复踩坑）
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

from ..config import APP_ROOT

DB_PATH = APP_ROOT / "data" / "memory.db"
EntryType = Literal["problem", "pattern", "mistake"]


@dataclass
class KnowledgeEntry:
    id: int | None
    type: EntryType
    title: str
    content: str
    tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    access_count: int = 0
    relevance_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.id, "type": self.type, "title": self.title,
            "content": self.content, "tags": self.tags,
            "created_at": self.created_at, "access_count": self.access_count,
        }


class LongTermMemory:
    """SQLite + FTS5 长期记忆存储。"""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db_path = Path(db_path) if db_path else DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS knowledge (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL CHECK(type IN ('problem','pattern','mistake')),
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags TEXT DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    access_count INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
                    title, content, tags, content='knowledge', content_rowid='id'
                )
            """)
            # 触发器保持 FTS 索引同步
            conn.executescript("""
                CREATE TRIGGER IF NOT EXISTS knowledge_ai AFTER INSERT ON knowledge BEGIN
                    INSERT INTO knowledge_fts(rowid, title, content, tags)
                    VALUES (new.id, new.title, new.content, new.tags);
                END;
                CREATE TRIGGER IF NOT EXISTS knowledge_ad AFTER DELETE ON knowledge BEGIN
                    INSERT INTO knowledge_fts(knowledge_fts, rowid, title, content, tags)
                    VALUES ('delete', old.id, old.title, old.content, old.tags);
                END;
                CREATE TRIGGER IF NOT EXISTS knowledge_au AFTER UPDATE ON knowledge BEGIN
                    INSERT INTO knowledge_fts(knowledge_fts, rowid, title, content, tags)
                    VALUES ('delete', old.id, old.title, old.content, old.tags);
                    INSERT INTO knowledge_fts(rowid, title, content, tags)
                    VALUES (new.id, new.title, new.content, new.tags);
                END;
            """)

    def add(self, type: EntryType, title: str, content: str, tags: list[str] | None = None) -> int:
        """添加一条知识。"""
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO knowledge (type, title, content, tags, created_at) VALUES (?, ?, ?, ?, ?)",
                (type, title, content, json.dumps(tags or []), datetime.now().isoformat(timespec="seconds")),
            )
            return cursor.lastrowid

    @staticmethod
    def _sanitize_fts5(query: str) -> str:
        """FTS5 查询净化：去除特殊字符，添加 * 前缀匹配。"""
        import re
        # 去掉 FTS5 特殊字符，保留字母数字和中文
        cleaned = re.sub(r'[-\"\(\)\[\]\{\}\~\!\@\#\$\%\^\&\=\.\,\;\:\?\<\>]', ' ', query)
        tokens = cleaned.split()
        # 最后 2 个词加 * 做前缀匹配
        safe = []
        for i, t in enumerate(tokens):
            if i >= len(tokens) - 2 and len(t) > 1:
                safe.append(t + '*')
            else:
                safe.append(t)
        return ' OR '.join(safe) if safe else query

    def search(self, query: str, top_k: int = 5, entry_type: EntryType | None = None) -> list[KnowledgeEntry]:
        """FTS5 全文搜索。"""
        safe_query = self._sanitize_fts5(query)
        with self._connect() as conn:
            where = ""
            params: list = []
            if entry_type:
                where = "AND k.type = ?"
                params.append(entry_type)

            # FTS5 搜索 + 从主表 join 元数据
            rows = conn.execute(f"""
                SELECT k.id, k.type, k.title, k.content, k.tags, k.created_at, k.access_count,
                       rank
                FROM knowledge_fts f
                JOIN knowledge k ON f.rowid = k.id
                WHERE knowledge_fts MATCH ? {where}
                ORDER BY rank
                LIMIT ?
            """, [safe_query] + params + [top_k]).fetchall()

            results = []
            for row in rows:
                results.append(KnowledgeEntry(
                    id=row["id"], type=row["type"], title=row["title"],
                    content=row["content"], tags=json.loads(row["tags"]),
                    created_at=row["created_at"], access_count=row["access_count"],
                ))

            # 更新访问计数
            if results:
                ids = [r.id for r in results if r.id]
                conn.executemany(
                    "UPDATE knowledge SET access_count = access_count + 1 WHERE id = ?",
                    [(i,) for i in ids],
                )

            return results

    def recall(self, query: str, top_k: int = 5) -> str:
        """搜索并格式化为可注入 Agent prompt 的文本。"""
        entries = self.search(query, top_k=top_k)
        if not entries:
            return ""

        lines = ["## 长期记忆（历史相关知识）"]
        for e in entries:
            type_label = {"problem": "历史题目", "pattern": "成功模式", "mistake": "踩坑记录"}.get(e.type, e.type)
            lines.append(f"\n### [{type_label}] {e.title}")
            lines.append(e.content[:500])
        return "\n".join(lines)

    def list_recent(self, entry_type: EntryType | None = None, limit: int = 10) -> list[KnowledgeEntry]:
        """列出最近添加的知识。"""
        with self._connect() as conn:
            where = f"WHERE type = '{entry_type}'" if entry_type else ""
            rows = conn.execute(
                f"SELECT * FROM knowledge {where} ORDER BY created_at DESC LIMIT ?", [limit]
            ).fetchall()

        return [
            KnowledgeEntry(
                id=r["id"], type=r["type"], title=r["title"],
                content=r["content"], tags=json.loads(r["tags"]),
                created_at=r["created_at"], access_count=r["access_count"],
            )
            for r in rows
        ]

    def stats(self) -> dict:
        """记忆库统计信息。"""
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM knowledge").fetchone()[0]
            by_type = {}
            for row in conn.execute("SELECT type, COUNT(*) as cnt FROM knowledge GROUP BY type"):
                by_type[row["type"]] = row["cnt"]
        return {"total": total, "by_type": by_type}

    def delete(self, entry_id: int) -> bool:
        with self._connect() as conn:
            conn.execute("DELETE FROM knowledge WHERE id = ?", [entry_id])
            return conn.total_changes > 0
