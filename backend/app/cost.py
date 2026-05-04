"""Quick cost + time estimate from spec §13.

Numbers are linearly interpolated from the table; this is for UI display only,
not billing. Real cost depends on model and prompt length.
"""
from __future__ import annotations


_TABLE = {
    50: (0.06, 90),
    100: (0.11, 150),
    250: (0.30, 300),
    500: (0.57, 540),
}


def estimate(scenario_count: int) -> tuple[float, int]:
    """Returns (estimated_cost_usd, estimated_seconds)."""
    keys = sorted(_TABLE.keys())
    if scenario_count <= keys[0]:
        cost, secs = _TABLE[keys[0]]
        return cost * (scenario_count / keys[0]), int(secs * (scenario_count / keys[0]))
    if scenario_count >= keys[-1]:
        cost, secs = _TABLE[keys[-1]]
        return cost * (scenario_count / keys[-1]), int(secs * (scenario_count / keys[-1]))
    # Linear interp between bracketing points.
    for lo, hi in zip(keys, keys[1:]):
        if lo <= scenario_count <= hi:
            t = (scenario_count - lo) / (hi - lo)
            c = _TABLE[lo][0] + t * (_TABLE[hi][0] - _TABLE[lo][0])
            s = _TABLE[lo][1] + t * (_TABLE[hi][1] - _TABLE[lo][1])
            return float(c), int(s)
    return _TABLE[keys[-1]]
