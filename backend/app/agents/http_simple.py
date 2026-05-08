"""Simple `{message} -> {output}` HTTP adapter.

Posts the latest user message to the user's URL as JSON, expects a response
with a top-level text field. This is the minimal contract for hand-rolled
agent endpoints / internal prototypes.

Accepted response field aliases (in order): `output`, `response`, `reply`, `text`,
`content`. We prefer the first one found.
"""
from __future__ import annotations

import time

import httpx

from .base import AgentAdapter, get_agent_auth_header
from .retry import with_retry
from .safety import assert_endpoint_safe


_RESPONSE_FIELDS = ("output", "response", "reply", "text", "content")
_RETRYABLE = (httpx.TimeoutException, httpx.NetworkError)


def _last_user_message(messages: list[dict]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return str(message.get("content", ""))
    return ""


class HttpSimpleAdapter(AgentAdapter):
    prepends_system = False

    def __init__(self, *, url: str, timeout: float = 60.0) -> None:
        assert_endpoint_safe(url)
        self.url = url
        self.timeout = timeout

    def send(
        self,
        messages: list[dict],
        *,
        max_tokens: int = 600,
    ) -> tuple[str, int]:
        body = {"message": _last_user_message(messages)}
        headers = {"Content-Type": "application/json"}
        auth = get_agent_auth_header()
        if auth:
            headers["Authorization"] = auth

        def _call() -> httpx.Response:
            with httpx.Client(timeout=self.timeout) as client:
                return client.post(self.url, json=body, headers=headers)

        start = time.perf_counter()
        response = with_retry(_call, retryable=_RETRYABLE)
        latency_ms = int((time.perf_counter() - start) * 1000)

        if response.status_code >= 400:
            raise RuntimeError(
                f"endpoint returned HTTP {response.status_code}: {response.text[:300]}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError(f"endpoint returned non-JSON body: {response.text[:300]}") from exc

        text = _extract_text(payload)
        if text is None:
            raise RuntimeError(
                "endpoint response missing a recognized text field "
                f"({', '.join(_RESPONSE_FIELDS)}); got keys {list(payload)[:6]}"
            )
        return text, latency_ms

    @property
    def description(self) -> str:
        return f"HttpSimpleAdapter(url={self.url})"


def _extract_text(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None
    for key in _RESPONSE_FIELDS:
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None
