"""Single source of truth for connection_type → adapter dispatch."""
from __future__ import annotations

from .base import AgentAdapter
from .http_openai_compat import HttpOpenAICompatAdapter
from .http_simple import HttpSimpleAdapter
from .prompt import PromptAdapter

CONNECTION_TYPES = {"prompt", "http_endpoint"}
ENDPOINT_FORMATS = {"simple", "openai_compat"}


def build_adapter(
    *,
    connection_type: str | None,
    model: str | None,
    endpoint_url: str | None,
    endpoint_format: str | None,
) -> AgentAdapter:
    """Build the right adapter for a run's connection config.

    Defaults to PromptAdapter when connection_type is missing/unknown so legacy
    rows from before this feature continue to work.
    """
    if connection_type == "http_endpoint":
        if not endpoint_url:
            raise ValueError("http_endpoint connection requires endpoint_url")
        fmt = endpoint_format or "openai_compat"
        if fmt == "simple":
            return HttpSimpleAdapter(url=endpoint_url)
        if fmt == "openai_compat":
            return HttpOpenAICompatAdapter(url=endpoint_url, model=model)
        raise ValueError(
            f"unknown endpoint_format '{fmt}'; expected one of {sorted(ENDPOINT_FORMATS)}"
        )
    return PromptAdapter(model=model)
