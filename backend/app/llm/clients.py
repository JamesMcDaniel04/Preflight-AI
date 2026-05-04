"""LLM clients with provider-aware BYOK support and retries."""
from __future__ import annotations

import contextvars
import threading
import time
from typing import Iterable

from anthropic import Anthropic
from openai import APIConnectionError, APIError, APITimeoutError, OpenAI, RateLimitError

from ..config import get_settings


_settings = get_settings()
_semaphore = threading.Semaphore(_settings.max_concurrent_llm_calls)

_openai_key_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "openai_key", default=None
)
_anthropic_key_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "anthropic_key", default=None
)
_openai_client_cache: dict[str, OpenAI] = {}
_anthropic_client_cache: dict[str, Anthropic] = {}
_cache_lock = threading.Lock()

_OPENAI_RETRYABLE = (RateLimitError, APITimeoutError, APIConnectionError, APIError)


def set_openai_key(key: str | None) -> contextvars.Token:
    return _openai_key_var.set(key or None)


def reset_openai_key(token: contextvars.Token) -> None:
    _openai_key_var.reset(token)


def set_anthropic_key(key: str | None) -> contextvars.Token:
    return _anthropic_key_var.set(key or None)


def reset_anthropic_key(token: contextvars.Token) -> None:
    _anthropic_key_var.reset(token)


def model_provider(model: str | None) -> str:
    value = (model or _settings.default_model).strip().lower()
    if value.startswith("anthropic:") or value.startswith("claude"):
        return "anthropic"
    return "openai"


def resolved_model_name(model: str | None) -> str:
    value = (model or _settings.default_model).strip()
    if value.lower().startswith("anthropic:"):
        return value.split(":", 1)[1]
    return value


def validate_model_access(
    model: str | None,
    *,
    openai_key: str | None = None,
    anthropic_key: str | None = None,
) -> str:
    provider = model_provider(model)
    effective_openai = openai_key or _settings.openai_api_key
    effective_anthropic = anthropic_key or _settings.anthropic_api_key

    if provider == "openai" and not effective_openai:
        raise RuntimeError("OpenAI model selected but no OpenAI API key is available.")
    if provider == "anthropic":
        if not effective_anthropic:
            raise RuntimeError("Anthropic model selected but no Anthropic API key is available.")
        if not effective_openai:
            raise RuntimeError(
                "Anthropic runs also require an OpenAI API key for embeddings and clustering."
            )
    return provider


def _resolve_openai_key() -> str:
    key = _openai_key_var.get() or _settings.openai_api_key
    if not key:
        raise RuntimeError(
            "No OpenAI API key available. Either set OPENAI_API_KEY in the environment "
            "or pass an X-OpenAI-Key header on the request."
        )
    return key


def _resolve_anthropic_key() -> str:
    key = _anthropic_key_var.get() or _settings.anthropic_api_key
    if not key:
        raise RuntimeError(
            "No Anthropic API key available. Either set ANTHROPIC_API_KEY in the environment "
            "or pass an X-Anthropic-Key header on the request."
        )
    return key


def get_openai() -> OpenAI:
    key = _resolve_openai_key()
    with _cache_lock:
        client = _openai_client_cache.get(key)
        if client is None:
            client = OpenAI(api_key=key)
            _openai_client_cache[key] = client
        return client


def get_anthropic() -> Anthropic:
    key = _resolve_anthropic_key()
    with _cache_lock:
        client = _anthropic_client_cache.get(key)
        if client is None:
            client = Anthropic(api_key=key)
            _anthropic_client_cache[key] = client
        return client


def _with_retry(fn, *, retryable: tuple[type[BaseException], ...], max_attempts: int = 4) -> object:
    last_exc: BaseException | None = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except retryable as exc:
            last_exc = exc
            if attempt == max_attempts - 1:
                raise
            time.sleep(0.8 * (2**attempt))
    raise last_exc  # pragma: no cover


def _chat_openai(
    messages: list[dict],
    *,
    model: str,
    temperature: float,
    response_format: dict | None,
    max_tokens: int | None,
) -> tuple[str, int]:
    client = get_openai()
    kwargs: dict = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if response_format:
        kwargs["response_format"] = response_format
    if max_tokens:
        kwargs["max_tokens"] = max_tokens

    def _call():
        return client.chat.completions.create(**kwargs)

    with _semaphore:
        start = time.perf_counter()
        resp = _with_retry(_call, retryable=_OPENAI_RETRYABLE)
        latency_ms = int((time.perf_counter() - start) * 1000)
        content = resp.choices[0].message.content or ""
        return content, latency_ms


def _chat_anthropic(
    messages: list[dict],
    *,
    model: str,
    temperature: float,
    max_tokens: int | None,
) -> tuple[str, int]:
    client = get_anthropic()
    system_parts: list[str] = []
    convo: list[dict] = []
    for message in messages:
        if message["role"] == "system":
            system_parts.append(str(message["content"]))
        else:
            convo.append({"role": message["role"], "content": str(message["content"])})

    def _call():
        kwargs = {
            "model": model,
            "messages": convo,
            "temperature": temperature,
            "max_tokens": max_tokens or 1024,
        }
        if system_parts:
            kwargs["system"] = "\n\n".join(system_parts)
        return client.messages.create(**kwargs)

    with _semaphore:
        start = time.perf_counter()
        resp = _with_retry(_call, retryable=(Exception,))
        latency_ms = int((time.perf_counter() - start) * 1000)
        parts = []
        for block in getattr(resp, "content", []):
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        return "".join(parts).strip(), latency_ms


def chat_complete(
    messages: list[dict],
    *,
    model: str | None = None,
    temperature: float = 0.7,
    response_format: dict | None = None,
    max_tokens: int | None = None,
) -> tuple[str, int]:
    resolved_model = resolved_model_name(model)
    provider = model_provider(model)
    if provider == "anthropic":
        return _chat_anthropic(
            messages,
            model=resolved_model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    return _chat_openai(
        messages,
        model=resolved_model,
        temperature=temperature,
        response_format=response_format,
        max_tokens=max_tokens,
    )


def embed(texts: Iterable[str]) -> list[list[float]]:
    client = get_openai()
    items = list(texts)
    if not items:
        return []

    def _call():
        return client.embeddings.create(model=_settings.embedding_model, input=items)

    with _semaphore:
        resp = _with_retry(_call, retryable=_OPENAI_RETRYABLE)
        return [d.embedding for d in resp.data]
