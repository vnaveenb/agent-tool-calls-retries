"""Tests for the retry decorator."""
from __future__ import annotations

import asyncio
import pytest

from src.retry import with_retry
from src.tools.base import ToolResult, ToolError


class TestRetry:
    def test_succeeds_first_try(self):
        call_count = 0

        @with_retry(max_attempts=4, base_delay=0.01, jitter=False, tool_name="test")
        def always_works():
            nonlocal call_count
            call_count += 1
            return ToolResult(success=True, output="ok")

        result = asyncio.run(always_works())
        assert result.success is True
        assert result.output == "ok"
        assert call_count == 1

    def test_succeeds_on_third_attempt(self):
        call_count = 0

        @with_retry(max_attempts=4, base_delay=0.01, jitter=False, tool_name="test")
        def fails_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("temporary failure")
            return ToolResult(success=True, output="recovered")

        result = asyncio.run(fails_twice())
        assert result.success is True
        assert result.output == "recovered"
        assert call_count == 3

    def test_exhausts_all_attempts(self):
        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.01, jitter=False, tool_name="flaky_tool")
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("permanent failure")

        with pytest.raises(ToolError) as exc_info:
            asyncio.run(always_fails())

        assert call_count == 3
        assert "flaky_tool" in str(exc_info.value)
        assert "3 attempts" in str(exc_info.value)

    def test_exponential_backoff_timing(self):
        """Verify that retries take progressively longer (rough check)."""
        import time
        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.05, jitter=False, tool_name="test")
        def fails_then_works():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("fail")
            return ToolResult(success=True, output="done")

        start = time.perf_counter()
        result = asyncio.run(fails_then_works())
        elapsed = time.perf_counter() - start

        assert result.success is True
        # Should have waited ~0.05 + ~0.10 = ~0.15s (no jitter)
        assert elapsed >= 0.12  # Allow some tolerance

    def test_works_with_async_functions(self):
        call_count = 0

        @with_retry(max_attempts=4, base_delay=0.01, jitter=False, tool_name="async_test")
        async def async_tool():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RuntimeError("async fail")
            return ToolResult(success=True, output="async ok")

        result = asyncio.run(async_tool())
        assert result.success is True
        assert result.output == "async ok"
        assert call_count == 2
