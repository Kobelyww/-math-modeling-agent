"""Redis Stack 记忆后端：短期记忆持久化 + 长期记忆（RedisJSON + RediSearch）。

依赖：redis[hiredis] 包 + Redis Stack 服务（可选，未安装时自动回退）。
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime

from .long_term import EntryType, KnowledgeEntry
from .short_term import AgentMessage, SharedMemory

# ─── 延迟导入 redis（可选依赖）─────────────────────────────────────────

_redis_module = None


def _get_redis():
    """延迟导入 redis 包，未安装时抛出 ImportError。"""
    global _redis_module
    if _redis_module is None:
        import redis as _redis
        from redis import Redis
        from redis.commands.search.field import NumericField, TagField, TextField
        from redis.commands.search.indexDefinition import IndexDefinition, IndexType
        from redis.commands.search.query import Query
        from redis.commands.search import reducers as _reducers

        _redis_module = (_redis, Redis, NumericField, TagField, TextField, IndexDefinition, IndexType, Query, _reducers)
    return _redis_module


def _redis_client():
    """获取 Redis 客户端。"""
    import sys

    _redis, Redis, *_ = _get_redis()

    mod = sys.modules.get("env_utils")
    if mod is None:
        from ... import env_utils as _eu
        mod = _eu

    return Redis(
        host=getattr(mod, "REDIS_HOST", "localhost"),
        port=getattr(mod, "REDIS_PORT", 6379),
        password=getattr(mod, "REDIS_PASSWORD", "redis-secure"),
        db=getattr(mod, "REDIS_DB", 0),
        decode_responses=True,
    )


# ─── 短期记忆 Redis 持久化 ────────────────────────────────────────────

class RedisSharedMemory(SharedMemory):
    """带 Redis 持久化的短期记忆。

    消息在内存中操作（速度优先），同时持久化到 Redis（TTL 自动过期）。
    进程重启后，同一 task_id 可恢复上次的消息历史。
    """

    def __init__(
        self,
        max_tokens: int = 50000,
        recent_window_size: int = 5,
        task_id: str | None = None,
        ttl: int = 3600,
        redis_client=None,
    ) -> None:
        super().__init__(max_tokens=max_tokens, recent_window_size=recent_window_size)
        self._task_id = task_id or uuid.uuid4().hex[:12]
        self._ttl = ttl
        self._r = redis_client or _redis_client()
        self._key = f"stm:{self._task_id}"
        self._load()

    @property
    def task_id(self) -> str:
        return self._task_id

    def post(self, role: str, content: str) -> AgentMessage:
        msg = super().post(role, content)
        self._save()
        return msg

    def advance_round(self) -> int:
        r = super().advance_round()
        self._save()
        return r

    def set_compressed_prefix(self, content: str) -> None:
        super().set_compressed_prefix(content)
        self._save()

    def compress_older(self, keep_recent: int | None = None) -> str | None:
        result = super().compress_older(keep_recent)
        if result is not None:
            self._save()
        return result

    def clear(self) -> None:
        super().clear()
        _redis, *_ = _get_redis()
        try:
            self._r.delete(self._key)
        except _redis.RedisError:
            pass

    def _serialize(self) -> dict:
        data = {
            "task_id": self._task_id,
            "round": self._round,
            "total_tokens": self._total_tokens,
            "recent_window_size": self._recent_window_size,
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "round_idx": m.round_idx,
                    "timestamp": m.timestamp,
                    "token_count": m.token_count,
                    "prompt_tokens": m.prompt_tokens,
                    "completion_tokens": m.completion_tokens,
                    "triggered_by": m.triggered_by,
                }
                for m in self._messages
            ],
        }
        if self._compressed_prefix:
            data["compressed_prefix"] = {
                "role": self._compressed_prefix.role,
                "content": self._compressed_prefix.content,
                "round_idx": self._compressed_prefix.round_idx,
                "timestamp": self._compressed_prefix.timestamp,
                "token_count": self._compressed_prefix.token_count,
            }
        return data

    def _save(self) -> None:
        _redis, *_ = _get_redis()
        try:
            self._r.json().set(self._key, "$", self._serialize())
            self._r.expire(self._key, self._ttl)
        except _redis.RedisError:
            pass

    def _load(self) -> None:
        _redis, *_ = _get_redis()
        try:
            data = self._r.json().get(self._key)
        except _redis.RedisError:
            return

        if not data:
            return

        self._round = data.get("round", 0)
        self._total_tokens = data.get("total_tokens", 0)
        self._recent_window_size = data.get("recent_window_size", 5)
        self._messages = [
            AgentMessage(
                role=m["role"],
                content=m["content"],
                round_idx=m.get("round_idx", 0),
                timestamp=m.get("timestamp", ""),
                token_count=m.get("token_count", 0),
                prompt_tokens=m.get("prompt_tokens", 0),
                completion_tokens=m.get("completion_tokens", 0),
                triggered_by=m.get("triggered_by", ""),
            )
            for m in data.get("messages", [])
        ]
        cp = data.get("compressed_prefix")
        if cp:
            self._compressed_prefix = AgentMessage(
                role=cp["role"],
                content=cp["content"],
                round_idx=cp.get("round_idx", -1),
                timestamp=cp.get("timestamp", ""),
                token_count=cp.get("token_count", 0),
            )
        else:
            self._compressed_prefix = None


# ─── 长期记忆 Redis Stack 实现 ────────────────────────────────────────

class RedisLongTermMemory:
    """Redis Stack 长期记忆存储（RedisJSON + RediSearch）。"""

    INDEX_NAME = "ltm_idx"
    KEY_PREFIX = "ltm:entry:"
    COUNTER_KEY = "ltm:counter"

    def __init__(self, redis_client=None) -> None:
        self._r = redis_client or _redis_client()
        self._ensure_index()

    def _ensure_index(self) -> None:
        _redis, _, NumericField, TagField, TextField, IndexDefinition, IndexType, *_ = _get_redis()
        try:
            self._r.ft(self.INDEX_NAME).info()
        except _redis.ResponseError:
            schema = (
                TextField("$.title", as_name="title"),
                TextField("$.content", as_name="content"),
                TagField("$.type", as_name="type"),
                TagField("$.tags[*]", as_name="tags"),
                NumericField("$.access_count", as_name="access_count"),
                TextField("$.created_at", as_name="created_at", sortable=True),
            )
            definition = IndexDefinition(prefix=[self.KEY_PREFIX], index_type=IndexType.JSON)
            self._r.ft(self.INDEX_NAME).create_index(schema, definition=definition)

    def _next_id(self) -> int:
        return self._r.incr(self.COUNTER_KEY)

    def add(self, type: EntryType, title: str, content: str, tags: list[str] | None = None) -> int:
        entry_id = self._next_id()
        key = f"{self.KEY_PREFIX}{entry_id}"
        doc = {
            "id": entry_id,
            "type": type,
            "title": title,
            "content": content,
            "tags": tags or [],
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "access_count": 0,
        }
        self._r.json().set(key, "$", doc)
        return entry_id

    @staticmethod
    def _build_query(query: str, entry_type: EntryType | None = None) -> str:
        """将用户查询转为 RediSearch 查询字符串。"""
        import re

        tokens = re.split(r'[，,。；;！!？?\s]+', query.strip())
        tokens = [t for t in tokens if len(t) >= 2]

        if not tokens:
            tokens = [query.strip()]

        parts = []
        for i, t in enumerate(tokens):
            t = t.replace('"', '').replace("'", "")
            if i >= len(tokens) - 2 and len(t) > 1:
                parts.append(f'"{t}" | "{t}"*')
            else:
                parts.append(f'"{t}"')

        search = " | ".join(parts)
        if entry_type:
            search = f"(@type:{{{entry_type}}}) ({search})"
        return search

    def search(
        self, query: str, top_k: int = 5, entry_type: EntryType | None = None
    ) -> list[KnowledgeEntry]:
        _redis, _, _, _, _, _, _, Query, *_ = _get_redis()
        qs = self._build_query(query, entry_type)
        try:
            results = self._r.ft(self.INDEX_NAME).search(
                Query(qs).paging(0, top_k).sort_by("access_count", asc=False)
            )
        except _redis.ResponseError:
            return []

        entries = []
        for doc in results.docs:
            d = json.loads(doc.json)
            entries.append(KnowledgeEntry(
                id=d.get("id"),
                type=d["type"],
                title=d["title"],
                content=d["content"],
                tags=d.get("tags", []),
                created_at=d.get("created_at", ""),
                access_count=d.get("access_count", 0),
            ))

        if entries:
            pipe = self._r.pipeline()
            for e in entries:
                if e.id:
                    pipe.json().numincr(f"{self.KEY_PREFIX}{e.id}", "$.access_count", 1)
            try:
                pipe.execute()
            except _redis.RedisError:
                pass

        return entries

    def recall(self, query: str, top_k: int = 5) -> str:
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
        _redis, _, _, _, _, _, _, Query, *_ = _get_redis()
        qs = "*" if not entry_type else f"@type:{{{entry_type}}}"
        try:
            results = self._r.ft(self.INDEX_NAME).search(
                Query(qs).paging(0, limit).sort_by("created_at", asc=False)
            )
        except _redis.ResponseError:
            return []

        entries = []
        for doc in results.docs:
            d = json.loads(doc.json)
            entries.append(KnowledgeEntry(
                id=d.get("id"), type=d["type"], title=d["title"],
                content=d["content"], tags=d.get("tags", []),
                created_at=d.get("created_at", ""), access_count=d.get("access_count", 0),
            ))
        return entries

    def stats(self) -> dict:
        _redis, _, _, _, _, _, _, Query, reducers = _get_redis()
        try:
            info = self._r.ft(self.INDEX_NAME).info()
            total = getattr(info, "num_docs", 0)
        except _redis.ResponseError:
            total = 0

        by_type = {}
        if total > 0:
            try:
                results = self._r.ft(self.INDEX_NAME).search(
                    Query("*").paging(0, 0).group_by("@type", reducers.count())
                )
                for row in getattr(results, "rows", []):
                    by_type[row[0]] = row[1]
            except _redis.ResponseError:
                pass

        return {"total": total, "by_type": by_type}

    def delete(self, entry_id: int) -> bool:
        key = f"{self.KEY_PREFIX}{entry_id}"
        return bool(self._r.delete(key))