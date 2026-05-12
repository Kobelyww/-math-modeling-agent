"""共享记忆：仅公开信息的总线。信息隔离在 orchestrator 的 context 构建中实现。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MemoryEntry:
    role: str
    content: str
    round_idx: int = 0
    public: bool = True


class SharedMemory:
    def __init__(self) -> None:
        self._entries: list[MemoryEntry] = []

    def add(self, role: str, content: str, public: bool = True) -> None:
        self._entries.append(MemoryEntry(role=role, content=content, public=public))

    def public_entries(self) -> list[MemoryEntry]:
        return [e for e in self._entries if e.public]

    def all_entries(self) -> list[MemoryEntry]:
        return self._entries

    def recent(self, n: int = 20) -> list[MemoryEntry]:
        return self._entries[-n:]

    def clear(self) -> None:
        self._entries.clear()
