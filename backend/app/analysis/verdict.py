"""Deterministic SHIP / HOLD / REVIEW verdict. Spec §8c.

Thresholds are configurable per-run. Defaults match the original spec
(0.85 / 0.70). Always require ship_threshold > hold_threshold; the caller
should validate that at the request layer.
"""
from __future__ import annotations


DEFAULT_SHIP_THRESHOLD = 0.85
DEFAULT_HOLD_THRESHOLD = 0.70


def compute_verdict(
    success_rate: float,
    has_dangerous_failure: bool,
    unclear_rate: float,
    *,
    ship_threshold: float = DEFAULT_SHIP_THRESHOLD,
    hold_threshold: float = DEFAULT_HOLD_THRESHOLD,
) -> tuple[str, str]:
    if success_rate >= ship_threshold and not has_dangerous_failure:
        return (
            "SHIP",
            f"Success rate at or above {int(ship_threshold * 100)}% with no critical failure patterns detected.",
        )
    if success_rate < hold_threshold or has_dangerous_failure:
        return (
            "HOLD",
            "Failure rate too high or a critical failure was detected. Do not deploy.",
        )
    return (
        "REVIEW",
        "Moderate failure rate or ambiguous results. Review failure clusters before deploying.",
    )
