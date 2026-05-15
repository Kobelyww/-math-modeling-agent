from __future__ import annotations

import json
from typing import Any

import redis
from redis import Redis

from env_utils import REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, REDIS_DB


def get_redis_client(db: int | None = None) -> Redis:
    """Return a Redis client connected to Redis Stack."""
    return redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        db=db if db is not None else REDIS_DB,
        decode_responses=True,
    )


def ping() -> bool:
    """Check connectivity."""
    try:
        return get_redis_client().ping()
    except redis.ConnectionError:
        return False


# ── JSON helpers (RedisJSON) ──────────────────────────────────────────

def json_set(key: str, data: dict | list, path: str = "$", client: Redis | None = None) -> None:
    """Store a JSON document at key."""
    r = client or get_redis_client()
    r.json().set(key, path, data)


def json_get(key: str, path: str = "$", client: Redis | None = None) -> Any:
    """Retrieve a JSON document from key."""
    r = client or get_redis_client()
    return r.json().get(key, path)


# ── Search helpers (RediSearch) ───────────────────────────────────────

def search_create_index(
    index_name: str,
    prefix: str,
    schema: list,
    client: Redis | None = None,
) -> None:
    """Create a RediSearch index over keys matching prefix."""
    r = client or get_redis_client()
    from redis.commands.search.field import TextField, TagField, NumericField
    try:
        r.ft(index_name).info()
    except Exception:
        r.ft(index_name).create_index(schema)


def search_query(
    index_name: str,
    query: str,
    offset: int = 0,
    num: int = 20,
    client: Redis | None = None,
) -> list[dict]:
    """Full-text search against a RediSearch index."""
    r = client or get_redis_client()
    from redis.commands.search.query import Query
    results = r.ft(index_name).search(Query(query).paging(offset, num))
    return [doc.__dict__ for doc in results.docs]