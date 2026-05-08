"""OpenAI-compatible chat-completions HTTP adapter.

Posts an OpenAI-shape request to the user's URL and parses the standard
`choices[0].message.content` reply. Works against:
  - OpenAI proper (api.openai.com/v1/chat/completions)
  - vLLM / TGI / Ollama / Together / Groq / Anyscale endpoints exposing the
    same shape
  - Any custom agent service that mirrors OpenAI's surface

The `model` field is included in the body for backends that require it but is
otherwise informational — the user's endpoint chooses the actual model.
"""
from __future__ import annotations

import time

import httpx

from .base import AgentAdapter, get_agent_auth_header
from .retry import with_retry
from .safety import assert_endpoint_safe


_RETRYABLE = (httpx.TimeoutException, httpx.NetworkError)


class HttpOpenAICompatAdapter(AgentAdapter):
    prepends_system = False

    def __init__(self, *, url: str, model: str | None, timeout: float = 60.0) -> None:
        assert_endpoint_safe(url)
        self.url = url
        self.model = model or "user-agent"
        self.timeout = timeout

    def send(
        self,
        messages: list[dict],
        *,
        max_tokens: int = 600,
    ) -> tuple[str, int]:
        body = {
            "model": self.model,
            "messages": [
                {"role": message["role"], "content": message["content"]}
                for message in messages
            ],
            "max_tokens": max_tokens,
        }
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

        text = _extract_choice_text(payload)
        if text is None:
            raise RuntimeError(
                "endpoint response missing choices[0].message.content; "
                f"got keys {list(payload)[:6] if isinstance(payload, dict) else type(payload).__name__}"
            )
        return text, latency_ms

    @property
    def description(self) -> str:
        return f"HttpOpenAICompatAdapter(url={self.url}, model={self.model})"


def _extract_choice_text(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first = choices[0]
    if not isinstance(first, dict):
        return None
    message = first.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content
    text = first.get("text")
    if isinstance(text, str):
        return text
    return None
