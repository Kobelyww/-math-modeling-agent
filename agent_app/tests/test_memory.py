"""Smoke tests for the memory system (SQLite backend, no Redis required)."""

import pytest

from agent_app.memory import (
    AgentMessage,
    KnowledgeEntry,
    LongTermMemory,
    MemoryManager,
    SharedMemory,
)


class TestSharedMemory:
    def test_post_and_retrieve(self):
        sm = SharedMemory()
        sm.post("modeler", "使用 NS 模型进行交通流建模")
        sm.post("programmer", "import numpy as np")
        assert len(sm._messages) == 2
        assert sm.latest_by_role("modeler").content == "使用 NS 模型进行交通流建模"

    def test_format_context(self):
        sm = SharedMemory()
        sm.post("modeler", "建模输出示例")
        ctx = sm.format_context(roles=["modeler"])
        assert "建模输出示例" in ctx

    def test_recent(self):
        sm = SharedMemory()
        for i in range(20):
            sm.post("agent", f"message {i}")
        assert len(sm.recent(5)) == 5
        assert sm.recent(1)[0].content == "message 19"

    def test_clear(self):
        sm = SharedMemory()
        sm.post("agent", "test")
        sm.clear()
        assert len(sm._messages) == 0
        assert sm.round_idx == 0

    def test_round_advance(self):
        sm = SharedMemory()
        sm.post("agent", "round 0")
        sm.advance_round()
        sm.post("agent", "round 1")
        assert sm.round_idx == 1
        assert sm._messages[1].round_idx == 1


class TestLongTermMemory:
    @pytest.fixture
    def ltm(self, tmp_path):
        db = tmp_path / "test_memory.db"
        ltm = LongTermMemory(db_path=db)
        yield ltm

    def test_add_and_search(self, ltm):
        ltm.add("problem", "交通流优化", "使用 NS 模型优化交通流", ["traffic"])
        results = ltm.search("交通流", top_k=3)
        assert len(results) > 0
        assert results[0].type == "problem"

    def test_recall_format(self, ltm):
        ltm.add("pattern", "灵敏度分析模式", "Sobol 方法进行全局灵敏度分析", ["sensitivity"])
        text = ltm.recall("灵敏度", top_k=3)
        assert "长期记忆" in text
        assert "Sobol" in text

    def test_stats(self, ltm):
        ltm.add("problem", "test", "content", [])
        ltm.add("mistake", "test err", "content", [])
        stats = ltm.stats()
        assert stats["total"] >= 2


class TestMemoryManager:
    def test_sqlite_fallback(self):
        mm = MemoryManager(use_redis=False)
        assert mm.use_redis is False
        mm.learn("problem", "测试题", "测试内容", ["test"])
        results = mm.search("测试")
        assert len(results) > 0

    def test_remember_and_context(self):
        mm = MemoryManager(use_redis=False)
        mm.remember("modeler", "建模测试输出")
        ctx = mm.get_context()
        assert "建模测试输出" in ctx

    def test_archive_solve(self):
        mm = MemoryManager(use_redis=False)
        mm.stm.post("modeling", "使用线性规划模型")
        mm.archive_solve("优化问题", "解决方案摘要")
        results = mm.search("优化问题")
        assert any(r.type == "problem" for r in results)

    def test_stats(self):
        mm = MemoryManager(use_redis=False)
        stats = mm.stats()
        assert "stm_messages" in stats
        assert "ltm_total" in stats
        assert "compressions" in stats