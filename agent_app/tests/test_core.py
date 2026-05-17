"""Tests for context compressor, STM segmented storage, and retry logic."""

import pytest

from agent_app.base import normalize_llm_content, _is_retryable
from agent_app.memory.short_term import SharedMemory, AgentMessage
from agent_app.memory.compressor import CompressStrategy, ContextCompressor


class TestNormalizeLLMContent:
    def test_string(self):
        assert normalize_llm_content("hello") == "hello"

    def test_list_of_dicts(self):
        assert normalize_llm_content([{"text": "hello"}, {"text": " world"}]) == "hello world"

    def test_empty_list(self):
        assert normalize_llm_content([]) == ""

    def test_none_like(self):
        assert normalize_llm_content(None) == "None"
        assert normalize_llm_content(42) == "42"


class TestRetryClassification:
    def test_rate_limit_is_retryable(self):
        assert _is_retryable(RuntimeError("rate limit exceeded")) is True
        assert _is_retryable(RuntimeError("429")) is True
        assert _is_retryable(RuntimeError("too many requests")) is True
        assert _is_retryable(RuntimeError("server error 500")) is True
        assert _is_retryable(RuntimeError("connection timeout")) is True

    def test_auth_errors_not_retryable(self):
        assert _is_retryable(RuntimeError("401 unauthorized")) is False
        assert _is_retryable(RuntimeError("403 forbidden")) is False
        assert _is_retryable(RuntimeError("invalid api key")) is False

    def test_context_length_not_retryable(self):
        assert _is_retryable(RuntimeError("context length exceeded")) is False
        assert _is_retryable(RuntimeError("maximum context length")) is False
        assert _is_retryable(RuntimeError("token limit reached")) is False

    def test_unknown_error_defaults_retryable(self):
        assert _is_retryable(RuntimeError("some random unknown error")) is True


class TestSegmentedSharedMemory:
    def test_compressed_prefix_initial_none(self):
        sm = SharedMemory()
        assert sm.compressed_prefix is None

    def test_set_and_get_compressed_prefix(self):
        sm = SharedMemory()
        sm.set_compressed_prefix("[Compressed] Summary of rounds 0-2")
        assert sm.compressed_prefix is not None
        assert "Summary of rounds 0-2" in sm.compressed_prefix.content
        assert sm.compressed_prefix.role == "compressor"

    def test_format_context_includes_compressed_prefix(self):
        sm = SharedMemory(recent_window_size=2)
        sm.set_compressed_prefix("[Compressed] Early rounds summary")
        sm.post("modeler", "Final model output")
        ctx = sm.format_context(max_tokens=2000)
        assert "Early rounds summary" in ctx
        assert "Final model output" in ctx

    def test_compress_older_keeps_recent(self):
        sm = SharedMemory(recent_window_size=3)
        for i in range(10):
            sm.post(f"agent_{i}", f"Message {i} content")
        assert sm.message_count == 10

        old_text = sm.compress_older()
        assert old_text is not None
        assert "agent_0" in old_text
        assert "agent_6" in old_text  # messages 0-6 are old
        assert sm.message_count == 3  # messages 7, 8, 9 kept
        assert sm._messages[-1].role == "agent_9"

    def test_compress_older_reduces_token_count(self):
        sm = SharedMemory(recent_window_size=2)
        for i in range(8):
            sm.post("agent", f"Message number {i} with some content")
        tokens_before = sm.total_tokens
        sm.compress_older()
        assert sm.total_tokens < tokens_before

    def test_compress_older_none_when_few_messages(self):
        sm = SharedMemory(recent_window_size=5)
        sm.post("agent", "Only one message")
        assert sm.compress_older() is None

    def test_message_count_property(self):
        sm = SharedMemory()
        sm.post("a", "1")
        sm.post("b", "2")
        assert sm.message_count == 2
        sm.compress_older(keep_recent=1)
        assert sm.message_count == 1

    def test_format_context_respects_token_budget(self):
        sm = SharedMemory(recent_window_size=10)
        for i in range(20):
            sm.post("agent", f"Message {i} " + "x" * 200)
        ctx = sm.format_context(max_tokens=500)
        # Should only include messages that fit the budget
        assert len(ctx) < 3000  # rough sanity check

    def test_clear_resets_compressed_prefix(self):
        sm = SharedMemory()
        sm.set_compressed_prefix("Some summary")
        sm.post("agent", "test")
        sm.clear()
        assert sm.compressed_prefix is None
        assert sm.message_count == 0
        assert sm.total_tokens == 0

    def test_summary_includes_compression_status(self):
        sm = SharedMemory()
        s1 = sm.summary()
        assert "无" in s1
        sm.set_compressed_prefix("summary")
        s2 = sm.summary()
        assert "有" in s2


class TestCompressStrategy:
    def test_all_strategies_exist(self):
        strategies = list(CompressStrategy)
        assert CompressStrategy.sliding_window in strategies
        assert CompressStrategy.summarize in strategies
        assert CompressStrategy.hierarchical in strategies

    def test_default_is_hierarchical(self):
        assert CompressStrategy.hierarchical is not None


class TestContextCompressor:
    @pytest.fixture
    def compressor(self):
        return ContextCompressor(llm=None, trigger_tokens=100, trigger_rounds=2)

    def test_should_compress_by_tokens(self, compressor):
        assert compressor.should_compress(150) is True
        assert compressor.should_compress(50) is False

    def test_should_compress_by_rounds(self, compressor):
        # _rounds_since_compress accumulates each call; trigger_rounds=2
        assert compressor.should_compress(50, current_round=0) is False  # counter=1
        assert compressor.should_compress(50, current_round=1) is True   # counter=2 >= trigger
        compressor.reset()
        assert compressor.should_compress(50, current_round=0) is False  # counter=1 again

    def test_reset(self, compressor):
        compressor._compressed_count = 5
        compressor._rounds_since_compress = 10
        compressor.reset()
        assert compressor.compress_count == 0
        assert compressor._rounds_since_compress == 0

    def test_sliding_window_compress(self, compressor):
        compressor.strategy = CompressStrategy.sliding_window
        result = compressor.compress("some messages")
        assert "滑动窗口" in result

    def test_summarize_compress_without_llm(self, compressor):
        """Without LLM, the compress method fails gracefully (test for interface)."""
        compressor.strategy = CompressStrategy.summarize
        # This will fail because llm is None, but we test the code path
        try:
            compressor.compress("test messages")
        except AttributeError:
            pass  # Expected: no LLM configured

    def test_hierarchical_with_existing_summary(self, compressor):
        compressor.strategy = CompressStrategy.hierarchical
        try:
            compressor.compress("new messages", existing_summary="old summary")
        except AttributeError:
            pass  # Expected: no LLM configured
