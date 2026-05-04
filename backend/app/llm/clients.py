"""LLM clients with semaphore + exponential backoff.

Slice 0 uses a synchronous OpenAI client (good enough for the thin E2E flow).
Concurrency is bounded by `MAX_CONCURRENT_LLM_CALLS` via a threading semaphore;
later slices that move to async/Celery will reuse the same wrappers.
"""
from __future__ import annotations

import threading
import time
from typing import Iterable

from openai import OpenAI
from openai import RateLimitError, APITimeoutError, APIConnectionError, APIError

from ..config import get_settings

_settings = get_settings()
_semaphore = threading.Semaphore(_settings.max_concurrent_llm_calls)
_client: OpenAI | None = None


def get_openai() -> OpenAI:
    global _client
    if _client is None:
        if not _settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY not configured")
        _client = OpenAI(api_key=_settings.openai_api_key)
    return _client


_RETRYABLE = (RateLimitError, APITimeoutError, APIConnectionError, APIError)


def _with_retry(fn, *, max_attempts: int = 4, base_delay: float = 0.8):
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except _RETRYABLE as e:
            last_exc = e
            if attempt == max_attempts - 1:
                raise
            time.sleep(base_delay * (2**attempt))
    raise last_exc  # pragma: no cover


def chat_complete(
    messages: list[dict],
    *,
    model: str | None = None,
    temperature: float = 0.7,
    response_format: dict | None = None,
    max_tokens: int | None = None,
) -> tuple[str, int]:
    """Returns (content, latency_ms)."""
    client = get_openai()
    model = model or _settings.default_model
    kwargs: dict = {"model": model, "messages": messages, "temperature": temperature}
    if response_format:
        kwargs["response_format"] = response_format
    if max_tokens:
        kwargs["max_tokens"] = max_tokens

    def _call():
        return client.chat.completions.create(**kwargs)

    with _semaphore:
        start = time.perf_counter()
        resp = _with_retry(_call)
        latency_ms = int((time.perf_counter() - start) * 1000)
        content = resp.choices[0].message.content or ""
        return content, latency_ms


def embed(texts: Iterable[str]) -> list[list[float]]:
    client = get_openai()
    texts = list(texts)
    if not texts:
        return []

    def _call():
        return client.embeddings.create(model=_settings.embedding_model, input=texts)

    with _semaphore:
        resp = _with_retry(_call)
        return [d.embedding for d in resp.data]
