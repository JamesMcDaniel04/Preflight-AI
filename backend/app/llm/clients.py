"""LLM clients with semaphore + exponential backoff.

The OpenAI key is resolved per-call from a contextvar — set it once at the
top of a request/task with `set_openai_key(...)` and every nested LLM call in
the same context will use it. Falls back to the env-var key when no override
is set, which keeps local dev without BYOK working.
"""
from __future__ import annotations

import contextvars
import threading
import time
from typing import Iterable

from openai import OpenAI
from openai import RateLimitError, APITimeoutError, APIConnectionError, APIError

from ..config import get_settings

_settings = get_settings()
_semaphore = threading.Semaphore(_settings.max_concurrent_llm_calls)

_openai_key_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "openai_key", default=None
)
_client_cache: dict[str, OpenAI] = {}
_cache_lock = threading.Lock()


def set_openai_key(key: str | None) -> contextvars.Token:
    """Set the OpenAI key for the current context. Returns a token to reset."""
    return _openai_key_var.set(key or None)


def reset_openai_key(token: contextvars.Token) -> None:
    _openai_key_var.reset(token)


def _resolve_key() -> str:
    key = _openai_key_var.get() or _settings.openai_api_key
    if not key:
        raise RuntimeError(
            "No OpenAI API key available. Either set OPENAI_API_KEY in the "
            "environment or pass an X-OpenAI-Key header on the request."
        )
    return key


def get_openai() -> OpenAI:
    key = _resolve_key()
    with _cache_lock:
        client = _client_cache.get(key)
        if client is None:
            client = OpenAI(api_key=key)
            _client_cache[key] = client
        return client


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
