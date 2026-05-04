from app.simulation.personas import PERSONAS, allocate_counts


def test_share_weights_sum_to_one():
    assert abs(sum(p.share for p in PERSONAS) - 1.0) < 1e-6


def test_allocate_counts_distribute_total_exactly():
    for total in (5, 50, 100, 250, 500, 7):
        allocations = allocate_counts(total)
        assert sum(c for _, c in allocations) == total


def test_allocate_zero():
    assert allocate_counts(0) == []


def test_normal_user_gets_majority():
    allocations = dict((p.seed, c) for p, c in allocate_counts(100))
    assert allocations["normal_user"] >= max(c for s, c in allocations.items() if s != "normal_user")
