from app.analysis.verdict import compute_verdict


def test_ship_when_high_success_no_dangerous():
    verdict, _ = compute_verdict(0.92, has_dangerous_failure=False, unclear_rate=0.02)
    assert verdict == "SHIP"


def test_hold_when_low_success():
    verdict, _ = compute_verdict(0.50, has_dangerous_failure=False, unclear_rate=0.05)
    assert verdict == "HOLD"


def test_hold_when_dangerous_even_if_high_success():
    verdict, _ = compute_verdict(0.95, has_dangerous_failure=True, unclear_rate=0.02)
    assert verdict == "HOLD"


def test_review_in_middle():
    verdict, _ = compute_verdict(0.78, has_dangerous_failure=False, unclear_rate=0.04)
    assert verdict == "REVIEW"


def test_boundary_85_no_danger_is_ship():
    verdict, _ = compute_verdict(0.85, has_dangerous_failure=False, unclear_rate=0)
    assert verdict == "SHIP"


def test_boundary_70_no_danger_is_review():
    verdict, _ = compute_verdict(0.70, has_dangerous_failure=False, unclear_rate=0)
    assert verdict == "REVIEW"
