"""Prompt-only adapter — wraps existing chat_complete.

Used for the legacy "paste your system prompt" flow. Behavior is unchanged from
the pre-adapter pipeline; the adapter abstraction just lets the runner stay
agnostic about what's behind the curtain.
"""
from __future__ import annotations

from ..llm.clients import chat_complete
from .base import AgentAdapter


class PromptAdapter(AgentAdapter):
    prepends_system = True

    def __init__(self, *, model: str | None) -> None:
        self.model = model

    def send(
        self,
        messages: list[dict],
        *,
        max_tokens: int = 600,
    ) -> tuple[str, int]:
        return chat_complete(
            messages,
            model=self.model,
            temperature=0.7,
            max_tokens=max_tokens,
        )

    @property
    def description(self) -> str:
        return f"PromptAdapter(model={self.model or 'default'})"
