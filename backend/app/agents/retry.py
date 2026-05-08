"""Shared retry policy for adapter calls.

Mirrors the inline logic in `llm/clients.py:_with_retry` so both LLM and HTTP
calls converge on the same backoff behavior. Pulled out to avoid duplication.
"""
from __future__ import annotations

import time
from typing import Callable, TypeVar

T = TypeVar("T")


def with_retry(
    fn: Callable[[], T],
    *,
    retryable: tuple[type[BaseException], ...],
    max_attempts: int = 4,
    base_delay: float = 0.8,
) -> T:
    last_exc: BaseException | None = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except retryable as exc:
            last_exc = exc
            if attempt == max_attempts - 1:
                raise
            time.sleep(base_delay * (2**attempt))
    raise last_exc  # pragma: no cover
