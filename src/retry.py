from __future__ import annotations

import asyncio
import functools
import random
import logging
from typing import Any, Callable

from .tools.base import ToolResult, ToolError

logger = logging.getLogger(__name__)


def with_retry(
    max_attempts: int = 4,
    base_delay: float = 1.0,
    jitter: bool = True,
    tool_name: str = "unknown",
):
    """Decorator that retries a tool function with exponential backoff.

    On failure after all attempts, raises ToolError so the agent
    observes the failure and can adapt its approach.
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> ToolResult:
            last_error: Exception | None = None

            for attempt in range(max_attempts):
                try:
                    result = fn(*args, **kwargs)
                    if asyncio.iscoroutine(result):
                        result = await result
                    return result
                except Exception as e:
                    last_error = e
                    if attempt < max_attempts - 1:
                        delay = base_delay * (2 ** attempt)
                        if jitter:
                            delay += random.uniform(0, 0.5)
                        logger.warning(
                            f"Tool '{tool_name}' attempt {attempt + 1}/{max_attempts} "
                            f"failed: {e}. Retrying in {delay:.2f}s..."
                        )
                        await asyncio.sleep(delay)

            # All attempts exhausted
            error_msg = f"Failed after {max_attempts} attempts. Last error: {last_error}"
            logger.error(f"Tool '{tool_name}': {error_msg}")
            raise ToolError(tool_name, error_msg)

        return wrapper
    return decorator
