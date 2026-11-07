import numpy as np
import pytest

from liveops_ab import bootstrap_diff_ci, two_proportion_ztest


def test_binomial_shortcut_matches_explicit_resampling():
    # The module claims: resampling users with replacement == drawing a
    # Binomial(n, x/n) count. Check it against the slow, literal version.
    x_a, n_a, x_b, n_b = 60, 300, 85, 320
    fast = bootstrap_diff_ci(x_a, n_a, x_b, n_b, n_boot=20_000, seed=3)

    rng = np.random.default_rng(4)
    users_a = np.array([1] * x_a + [0] * (n_a - x_a))
    users_b = np.array([1] * x_b + [0] * (n_b - x_b))
    diffs = [
        rng.choice(users_b, n_b).mean() - rng.choice(users_a, n_a).mean()
        for _ in range(20_000)
    ]
    slow_low, slow_high = np.quantile(diffs, [0.025, 0.975])
    assert fast.ci_low == pytest.approx(slow_low, abs=0.005)
    assert fast.ci_high == pytest.approx(slow_high, abs=0.005)


def test_agrees_with_normal_ci_for_large_samples():
    args = (8_500, 44_700, 8_280, 45_489)
    boot = bootstrap_diff_ci(*args, seed=0)
    wald = two_proportion_ztest(*args)
    assert boot.ci_low == pytest.approx(wald.ci_low, abs=0.0007)
    assert boot.ci_high == pytest.approx(wald.ci_high, abs=0.0007)


def test_reproducible_with_seed():
    a = bootstrap_diff_ci(100, 1000, 120, 1000, seed=7)
    b = bootstrap_diff_ci(100, 1000, 120, 1000, seed=7)
    assert a == b


def test_rejects_too_few_resamples():
    with pytest.raises(ValueError):
        bootstrap_diff_ci(100, 1000, 120, 1000, n_boot=50)
