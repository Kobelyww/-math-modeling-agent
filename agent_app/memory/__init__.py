"""长短时记忆系统。

Short-term: 单次求解任务的对话历史（进程内/Redis 持久化）
Long-term:  跨会话持久知识（SQLite+FTS5 或 Redis Stack）
"""

from .short_term import AgentMessage, SharedMemory
from .long_term import LongTermMemory, KnowledgeEntry
from .compressor import ContextCompressor
from .manager import MemoryManager
from .redis_backends import RedisLongTermMemory, RedisSharedMemory

__all__ = [
    "AgentMessage", "SharedMemory",
    "LongTermMemory", "KnowledgeEntry",
    "ContextCompressor", "MemoryManager",
    "RedisLongTermMemory", "RedisSharedMemory",
]