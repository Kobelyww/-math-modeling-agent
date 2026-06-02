"""Tests for Pipeline orchestration logic."""
import pytest
from unittest.mock import MagicMock, patch

from zhihu_fiction.pipeline import Pipeline, select_topic

# ---- Prevent test pollution of real output/ ----

@pytest.fixture(autouse=True)
def _isolate_pipeline_output(tmp_path, monkeypatch):
    """Redirect Pipeline output to a temp directory so tests don't write to real runs.jsonl."""
    import zhihu_fiction.pipeline as pmod
    monkeypatch.setattr(pmod, "RUN_DIR", tmp_path / ".pipeline")
    monkeypatch.setattr(pmod, "SCHEDULE_FILE", tmp_path / ".pipeline" / "schedule.json")


class TestSelectTopic:
    def test_parses_topic_and_genre(self):
        llm = MagicMock()
        response = MagicMock()
        response.content = "选题：密室逃脱\n题材：悬疑\n理由：热度高"
        llm.invoke.return_value = response
        hot_items = [{"title": "密室逃脱", "hot_score": 5000, "excerpt": ""}]
        result = select_topic(hot_items, llm)
        assert result["topic"] == "密室逃脱"
        assert result["genre"] == "悬疑"

    def test_fallback_to_first_hot(self):
        llm = MagicMock()
        response = MagicMock()
        response.content = "乱七八糟没有匹配格式"
        llm.invoke.return_value = response
        hot_items = [{"title": "热门第一", "hot_score": 9999}]
        result = select_topic(hot_items, llm)
        assert result["topic"] == "热门第一"


class TestPipeline:
    def test_run_with_provided_topic(self):
        coordinator = MagicMock()
        reviewer = MagicMock()
        llm = MagicMock()
        publisher = MagicMock()
        from langchain_core.messages import HumanMessage
        coordinator.invoke.return_value = {
            "messages": [HumanMessage(content="【小说正文】\n完整小说内容\n【发布方案】\n发布方案内容")]
        }
        reviewer.review.return_value = {"total_score": 7.5, "full_report": "评审报告"}
        scraper = MagicMock(return_value=[{"title": "热榜1", "hot_score": 5000, "excerpt": ""}])
        publisher.publish.return_value = {"success": True, "url": "https://zhuanlan.zhihu.com/p/123"}

        pipeline = Pipeline(
            coordinator=coordinator, reviewer=reviewer, llm=llm,
            publisher=publisher, scraper=scraper,
            quality_threshold=6.0, max_rewrites=2,
        )
        result = pipeline.run(topic="测试主题", genre="悬疑")

        assert result.topic == "测试主题"
        assert result.stages["scrape"].status == "ok"
        assert result.stages["create"].status == "ok"
        assert result.stages["review"].extra["score"] == 7.5
        assert result.stages["publish"].status == "ok"
        publisher.publish.assert_called_once()

    def test_skip_publish_when_quality_low(self):
        coordinator = MagicMock()
        reviewer = MagicMock()
        llm = MagicMock()
        publisher = MagicMock()
        from langchain_core.messages import HumanMessage
        coordinator.invoke.return_value = {
            "messages": [HumanMessage(content="【小说正文】\n不太好的小说\n【发布方案】\n方案")]
        }
        reviewer.review.return_value = {"total_score": 4.5, "full_report": "质量问题"}
        scraper = MagicMock(return_value=[{"title": "热榜1", "hot_score": 5000, "excerpt": ""}])

        pipeline = Pipeline(
            coordinator=coordinator, reviewer=reviewer, llm=llm,
            publisher=publisher, scraper=scraper,
            quality_threshold=6.0, max_rewrites=2,
        )
        result = pipeline.run(topic="测试主题")
        assert result.stages["publish"].status == "skipped"
        publisher.publish.assert_not_called()