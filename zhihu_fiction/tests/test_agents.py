"""Tests for agent tools and ReviewerAgent."""
import pytest
from unittest.mock import MagicMock

from zhihu_fiction.agents import (
    _make_analyze_topic,
    _make_plan_outline,
    _make_write_draft,
    _make_polish_draft,
    _make_synthesize,
    ReviewerAgent,
)


class TestAgentTools:
    def test_analyze_topic_is_tool(self):
        llm = MagicMock()
        llm.invoke.return_value = MagicMock(content="选题分析报告内容")
        tool = _make_analyze_topic(llm)
        assert hasattr(tool, "invoke")
        result = tool.invoke({"topic": "穿越古代", "hot_trends": "热榜...", "skills": "技能卡..."})
        assert "选题分析报告内容" in result

    def test_plan_outline_is_tool(self):
        llm = MagicMock()
        llm.invoke.return_value = MagicMock(content="故事大纲内容")
        tool = _make_plan_outline(llm)
        result = tool.invoke({"topic": "穿越古代", "topic_analysis": "分析报告", "skills": "技能卡"})
        assert "故事大纲内容" in result

    def test_write_draft_is_tool(self):
        llm = MagicMock()
        llm.invoke.return_value = MagicMock(content="完整小说正文3000字")
        tool = _make_write_draft(llm)
        result = tool.invoke({"topic": "穿越古代", "outline": "大纲", "skills": "技能卡", "revision_feedback": ""})
        assert "完整小说正文3000字" in result

    def test_polish_draft_is_tool(self):
        llm = MagicMock()
        llm.invoke.return_value = MagicMock(content="润色后的小说全文")
        tool = _make_polish_draft(llm)
        result = tool.invoke({"topic": "穿越古代", "draft": "初稿", "feedback": "改进开篇"})
        assert "润色后的小说全文" in result

    def test_synthesize_is_tool(self):
        llm = MagicMock()
        llm.invoke.return_value = MagicMock(content="发布方案")
        tool = _make_synthesize(llm)
        result = tool.invoke({"topic": "穿越古代", "topic_analysis": "分析", "outline": "大纲", "final_draft": "终稿"})
        assert "发布方案" in result


class TestReviewerAgent:
    def test_review_returns_score(self):
        llm = MagicMock()
        review_output = (
            "1) 开篇钩子力：8 分\n2) 节奏把控：7 分\n3) 人设一致性：6 分\n"
            "4) 逻辑自洽：7 分\n5) 情绪张力：8 分\n6) 金句密度：5 分\n"
            "7) 结尾余韵：7 分\n8) 知乎适配度：8 分\n"
        )
        llm.invoke.return_value = MagicMock(content=review_output)
        reviewer = ReviewerAgent(llm)
        result = reviewer.review("小说正文", "测试选题")
        assert "total_score" in result
        assert result["total_score"] == pytest.approx(7.0, 0.5)

    def test_review_extract_score_fallback(self):
        llm = MagicMock()
        llm.invoke.return_value = MagicMock(content="写得很好，没有具体分数")
        reviewer = ReviewerAgent(llm)
        result = reviewer.review("小说正文", "测试选题")
        assert result["total_score"] == 5.0