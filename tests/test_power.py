import math

import numpy as np
import pytest

from liveops_ab import (achieved_power, minimum_detectable_effect,
                        required_sample_size, two_proportion_ztest)


def test_required_n_gives_requested_power():
    n = required_sample_size(0.19, 0.01, alpha=0.05, power=0.8)
    assert achieved_power(n, n, 0.19, 0.01) >= 0.8
    assert achieved_power(n - 1, n - 1, 0.19, 0.01) < 0.8  # n is the minimum


def test_required_n_by_simulation():
    # The formula is an approximation, so check it against reality: run many
    # simulated experiments at that n with the true effect, count detections.
    p_a, mde = 0.19, 0.01
    n = required_sample_size(p_a, mde, power=0.8)
    rng = np.random.default_rng(2)
    trials = 4_000
    detected = 0
    for x_a, x_b in zip(rng.binomial(n, p_a, trials), rng.binomial(n, p_a + mde, trials)):
        detected += two_proportion_ztest(int(x_a), n, int(x_b), n).p_value < 0.05
    assert detected / trials == pytest.approx(0.8, abs=0.02)


def test_more_power_or_smaller_effect_needs_more_users():
    base = required_sample_size(0.45, 0.02)
    assert required_sample_size(0.45, 0.02, power=0.9) > base
    assert required_sample_size(0.45, 0.01) > base
    # Halving the effect roughly quadruples n (n scales with 1 / mde**2).
    assert required_sample_size(0.45, 0.01) / base == pytest.approx(4, rel=0.02)


def test_mde_inverts_achieved_power():
    mde = minimum_detectable_effect(44_700, 45_489, 0.19)
    assert achieved_power(44_700, 45_489, 0.19, mde) == pytest.approx(0.8, abs=1e-9)


def test_tiny_sample_has_huge_mde():
    assert minimum_detectable_effect(50, 50, 0.19) > 0.2
    assert achieved_power(50, 50, 0.19, 0.01) < 0.1


def test_impossible_mde_is_infinite():
    assert minimum_detectable_effect(2, 2, 0.5) == math.inf


@pytest.mark.parametrize("args", [(0.9, 0.2), (0.0, 0.1), (0.5, 0.0)])
def test_rejects_bad_rates(args):
    with pytest.raises(ValueError):
        required_sample_size(*args)
