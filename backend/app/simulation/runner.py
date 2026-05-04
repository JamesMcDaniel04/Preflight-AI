"""Run the user's base prompt against each generated scenario input."""
from __future__ import annotations

from ..llm.clients import chat_complete


def run_scenario(base_prompt: str, scenario_input: str, *, model: str | None = None) -> tuple[str, int, str | None]:
    """Returns (output, latency_ms, error)."""
    messages = [
        {"role": "system", "content": base_prompt},
        {"role": "user", "content": scenario_input},
    ]
    try:
        output, latency_ms = chat_complete(messages, model=model, temperature=0.7, max_tokens=600)
        return output, latency_ms, None
    except Exception as e:  # captured per-scenario so one bad call doesn't kill the whole run
        return "", 0, str(e)[:500]
