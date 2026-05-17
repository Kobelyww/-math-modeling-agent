"""长期记忆：跨会话持久化知识库（SQLite + FTS5 全文搜索 + 复合重排序）。

存储三类知识：
1. problem — 解过的题（题目、方案摘要、关键模型）
2. pattern  — 成功的建模模式（可跨题复用）
3. mistake — 犯过的错误和修正（防重复踩坑）

召回策略（受 CrewAI 启发）：
  - 过采样（oversample_factor=2）+ 复合评分重排序
  - 评分维度：FTS5 rank + 时间衰减 + 访问热度 + 重要性
"""

from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

from ..config import APP_ROOT

DB_PATH = APP_ROOT / "data" / "memory.db"
EntryType = Literal["problem", "pattern", "mistake"]

# 重排序过采样因子（CrewAI 启发：取 2x 候选，综合评分后返回 top_k）
_OVERSEARCH_FACTOR = 2

# 时间衰减半衰期（天），180 天后权重降至 50%
_TIME_DECAY_HALF_LIFE = 180.0


@dataclass
class KnowledgeEntry:
    id: int | None
    type: EntryType
    title: str
    content: str
    tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    access_count: int = 0
    importance: float = 0.5
    scope: str = "/"
    relevance_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.id, "type": self.type, "title": self.title,
            "content": self.content, "tags": self.tags,
            "created_at": self.created_at, "access_count": self.access_count,
            "importance": self.importance, "scope": self.scope,
        }


def _time_decay(created_at_str: str) -> float:
    """计算时间衰减权重：越新的记忆权重越高。"""
    try:
        created = datetime.fromisoformat(created_at_str)
        delta_days = (datetime.now() - created).total_seconds() / 86400.0
        return math.exp(-math.log(2) * delta_days / _TIME_DECAY_HALF_LIFE)
    except (ValueError, TypeError):
        return 0.5


class LongTermMemory:
    """SQLite + FTS5 长期记忆存储（含复合重排序）。"""

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
            # 新增字段：importance 和 scope（兼容旧表）
            try:
                conn.execute("ALTER TABLE knowledge ADD COLUMN importance REAL DEFAULT 0.5")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE knowledge ADD COLUMN scope TEXT DEFAULT '/'")
            except sqlite3.OperationalError:
                pass

            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
                    title, content, tags, content='knowledge', content_rowid='id'
                )
            """)
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

    def add(self, type: EntryType, title: str, content: str, tags: list[str] | None = None,
            importance: float = 0.5, scope: str = "/") -> int:
        """添加一条知识。"""
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO knowledge (type, title, content, tags, created_at, importance, scope) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (type, title, content, json.dumps(tags or []),
                 datetime.now().isoformat(timespec="seconds"), importance, scope),
            )
            return cursor.lastrowid

    @staticmethod
    def _sanitize_fts5(query: str) -> str:
        import re
        cleaned = re.sub(r'[-\"\(\)\[\]\{\}\~\!\@\#\$\%\^\&\=\.\,\;\:\?\<\>]', ' ', query)
        tokens = cleaned.split()
        safe = []
        for i, t in enumerate(tokens):
            if i >= len(tokens) - 2 and len(t) > 1:
                safe.append(t + '*')
            else:
                safe.append(t)
        return ' OR '.join(safe) if safe else query

    def _compute_composite_score(self, fts5_rank: float, entry: KnowledgeEntry) -> float:
        """复合评分：FTS5 相关性 + 时间衰减 + 重要性 + 访问热度。

        FTS5 rank 越小越相关（负相关），归一化后组合。
        """
        # FTS5 rank 归一化：rank 越小得分越高
        rank_score = 1.0 / (1.0 + abs(fts5_rank) * 0.1)

        # 时间衰减
        decay = _time_decay(entry.created_at)

        # 访问热度（对数压缩防止热门条目主导）
        access_boost = math.log(1 + entry.access_count) * 0.1

        # 重要性
        imp = entry.importance

        # 加权组合
        return 0.4 * rank_score + 0.25 * decay + 0.1 * access_boost + 0.25 * imp

    def search(self, query: str, top_k: int = 5, entry_type: EntryType | None = None,
               oversample: bool = True) -> list[KnowledgeEntry]:
        """FTS5 全文搜索 + 复合重排序。

        Args:
            query: 搜索查询
            top_k: 返回结果数
            entry_type: 按类型过滤
            oversample: 是否过采样重排序（默认 True）
        """
        fetch_count = top_k * _OVERSEARCH_FACTOR if oversample else top_k
        safe_query = self._sanitize_fts5(query)

        with self._connect() as conn:
            where = ""
            params: list = []
            if entry_type:
                where = "AND k.type = ?"
                params.append(entry_type)

            rows = conn.execute(f"""
                SELECT k.id, k.type, k.title, k.content, k.tags, k.created_at,
                       k.access_count, k.importance, k.scope, rank
                FROM knowledge_fts f
                JOIN knowledge k ON f.rowid = k.id
                WHERE knowledge_fts MATCH ? {where}
                ORDER BY rank
                LIMIT ?
            """, [safe_query] + params + [fetch_count]).fetchall()

            entries = []
            for row in rows:
                entries.append(KnowledgeEntry(
                    id=row["id"], type=row["type"], title=row["title"],
                    content=row["content"], tags=json.loads(row["tags"]),
                    created_at=row["created_at"], access_count=row["access_count"],
                    importance=row["importance"] if "importance" in row.keys() else 0.5,
                    scope=row["scope"] if "scope" in row.keys() else "/",
                ))

            # 复合重排序
            if oversample and len(entries) > top_k:
                for e in entries:
                    e.relevance_score = self._compute_composite_score(
                        float(dict(row).get("rank", 1.0)), e
                    )
                entries.sort(key=lambda e: e.relevance_score, reverse=True)
                entries = entries[:top_k]

            # 更新访问计数
            if entries:
                ids = [r.id for r in entries if r.id]
                conn.executemany(
                    "UPDATE knowledge SET access_count = access_count + 1 WHERE id = ?",
                    [(i,) for i in ids],
                )

            return entries

    def recall(self, query: str, top_k: int = 5) -> str:
        """搜索并格式化为可注入 Agent prompt 的文本。"""
        entries = self.search(query, top_k=top_k)
        if not entries:
            return ""

        lines = ["## 长期记忆（历史相关知识）"]
        for e in entries:
            type_label = {"problem": "历史题目", "pattern": "成功模式", "mistake": "踩坑记录"}.get(e.type, e.type)
            scope_hint = f" [{e.scope}]" if e.scope and e.scope != "/" else ""
            score_hint = f" (相关度:{e.relevance_score:.2f})" if e.relevance_score > 0 else ""
            lines.append(f"\n### [{type_label}]{scope_hint} {e.title}{score_hint}")
            lines.append(e.content[:500])
        return "\n".join(lines)

    def search_by_scope(self, scope: str, top_k: int = 10, entry_type: EntryType | None = None) -> list[KnowledgeEntry]:
        """按层级 scope 路径搜索（支持前缀匹配，如 /optimization/ 匹配所有优化子类）。"""
        with self._connect() as conn:
            where = "WHERE k.scope LIKE ?"
            params: list = [scope + "%"]
            if entry_type:
                where += " AND k.type = ?"
                params.append(entry_type)

            rows = conn.execute(f"""
                SELECT k.* FROM knowledge k
                {where}
                ORDER BY k.importance DESC, k.created_at DESC
                LIMIT ?
            """, params + [top_k]).fetchall()

            return [
                KnowledgeEntry(
                    id=r["id"], type=r["type"], title=r["title"],
                    content=r["content"], tags=json.loads(r["tags"]),
                    created_at=r["created_at"], access_count=r["access_count"],
                    importance=r["importance"] if "importance" in r.keys() else 0.5,
                    scope=r["scope"] if "scope" in r.keys() else "/",
                )
                for r in rows
            ]

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
                importance=r["importance"] if "importance" in r.keys() else 0.5,
                scope=r["scope"] if "scope" in r.keys() else "/",
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
            by_scope = {}
            for row in conn.execute(
                "SELECT scope, COUNT(*) as cnt FROM knowledge WHERE scope != '/' GROUP BY scope"
            ):
                by_scope[row["scope"]] = row["cnt"]
        return {"total": total, "by_type": by_type, "by_scope": by_scope}

    def delete(self, entry_id: int) -> bool:
        with self._connect() as conn:
            conn.execute("DELETE FROM knowledge WHERE id = ?", [entry_id])
            return conn.total_changes > 0
