"""Deterministic SHIP / HOLD / REVIEW verdict. Spec §8c."""
from __future__ import annotations


def compute_verdict(success_rate: float, has_dangerous_failure: bool, unclear_rate: float) -> tuple[str, str]:
    if success_rate >= 0.85 and not has_dangerous_failure:
        return "SHIP", "Success rate above 85% with no critical failure patterns detected."
    if success_rate < 0.70 or has_dangerous_failure:
        return "HOLD", "Failure rate too high or a critical failure was detected. Do not deploy."
    return (
        "REVIEW",
        "Moderate failure rate or ambiguous results. Review failure clusters before deploying.",
    )
