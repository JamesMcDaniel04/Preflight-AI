"""Two-stage success classification.

Stage 1: deterministic heuristic_flag() — empty / refusal / hallucination signal.
Stage 2: LLM classification for non-flagged outputs.

Spec §7b. The patterns here are verbatim from the spec; do not "improve" them
without updating the spec — the heuristic's value is its predictability.
"""
from __future__ import annotations

import json

from .clients import chat_complete


REFUSAL_PATTERNS = ["i cannot", "i'm unable to", "as an ai", "i don't have access"]
HALLUCINATION_SIGNALS = ["i don't have information", "i'm not sure but", "it's possible that"]


def heuristic_flag(output: str | None) -> str | None:
    if not output or len(output.strip()) < 5:
        return "empty_response"
    lowered = output.lower()
    if any(p in lowered for p in REFUSAL_PATTERNS):
        return "refusal"
    if any(p in lowered for p in HALLUCINATION_SIGNALS):
        return "hallucination_signal"
    return None


_CLASSIFY_SYSTEM = (
    "You are an evaluator that classifies AI agent outputs against success "
    "criteria. Respond ONLY with JSON of the form "
    '{"result": "SUCCESS"|"FAILURE"|"UNCLEAR", "reason": "one sentence"}.'
)


def classify_with_llm(output: str, success_criteria: str, *, model: str | None = None) -> tuple[str, str]:
    """Returns (classified_as, failure_reason). classified_as is one of success/failure/unclear."""
    user = (
        f'Success criteria: "{success_criteria}"\n\n'
        f"AI agent output:\n{output}\n\n"
        "Classify and explain in one sentence."
    )
    messages = [
        {"role": "system", "content": _CLASSIFY_SYSTEM},
        {"role": "user", "content": user},
    ]
    raw, _ = chat_complete(
        messages,
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        max_tokens=200,
    )
    try:
        parsed = json.loads(raw)
        result = str(parsed.get("result", "UNCLEAR")).lower()
        if result not in {"success", "failure", "unclear"}:
            result = "unclear"
        reason = str(parsed.get("reason", ""))[:500]
    except (json.JSONDecodeError, AttributeError):
        result = "unclear"
        reason = "Classifier returned malformed JSON."
    return result, reason
