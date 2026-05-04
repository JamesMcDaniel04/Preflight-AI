from app.cost import estimate


def test_known_anchors():
    cost, secs = estimate(100)
    assert abs(cost - 0.11) < 1e-6
    assert secs == 150


def test_interpolation_between_anchors():
    cost_low, _ = estimate(100)
    cost_mid, _ = estimate(175)
    cost_high, _ = estimate(250)
    assert cost_low < cost_mid < cost_high
