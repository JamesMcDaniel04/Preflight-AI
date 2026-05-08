"""AgentAdapter contract.

Each adapter knows how to take a list of messages and return the agent's reply
text + the wall-clock latency it took. The runner doesn't care whether that's a
local LLM call, an HTTP POST to a customer's deployed endpoint, or something
else — it just calls `adapter.send(messages)`.

`prepends_system` tells the runner whether the system prompt should be included
in the message list:
  - True for the prompt-only adapter (we run the user's prompt as the system
    message of a fresh OpenAI call).
  - False for HTTP adapters (the user's deployed endpoint already has its own
    system context; sending ours would conflict with it).
"""
from __future__ import annotations

import contextvars
from abc import ABC, abstractmethod


_agent_auth_header_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "agent_auth_header", default=None
)


def set_agent_auth_header(value: str | None) -> contextvars.Token:
    return _agent_auth_header_var.set(value or None)


def reset_agent_auth_header(token: contextvars.Token) -> None:
    _agent_auth_header_var.reset(token)


def get_agent_auth_header() -> str | None:
    return _agent_auth_header_var.get()


class AgentAdapter(ABC):
    """Common interface for all agent backends."""

    prepends_system: bool = True

    @abstractmethod
    def send(
        self,
        messages: list[dict],
        *,
        max_tokens: int = 600,
    ) -> tuple[str, int]:
        """Returns (text, latency_ms)."""

    @property
    def description(self) -> str:
        """Short human-readable description of the adapter, used in logs."""
        return self.__class__.__name__
