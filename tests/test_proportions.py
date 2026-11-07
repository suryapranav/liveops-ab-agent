import math

import numpy as np
import pytest
from scipy import stats

from liveops_ab import two_proportion_ztest


def test_pvalue_matches_scipy_chi2_without_correction():
    # For a 2x2 table, Pearson chi-square (no Yates correction) is exactly
    # the square of the pooled two-proportion z statistic.
    x_a, n_a, x_b, n_b = 8_500, 44_700, 8_280, 45_489
    result = two_proportion_ztest(x_a, n_a, x_b, n_b)
    table = [[x_a, n_a - x_a], [x_b, n_b - x_b]]
    chi2, p_value, _, _ = stats.chi2_contingency(table, correction=False)
    assert result.z ** 2 == pytest.approx(chi2)
    assert result.p_value == pytest.approx(p_value)


def test_hand_computed_example():
    # 20% vs 25% on 1000 users each.
    result = two_proportion_ztest(200, 1000, 250, 1000)
    assert result.diff == pytest.approx(0.05)
    assert result.relative_lift == pytest.approx(0.25)
    se_pooled = math.sqrt(0.225 * 0.775 * (2 / 1000))
    assert result.z == pytest.approx(0.05 / se_pooled)
    se_unpooled = math.sqrt(0.2 * 0.8 / 1000 + 0.25 * 0.75 / 1000)
    assert result.ci_low == pytest.approx(0.05 - 1.959964 * se_unpooled, rel=1e-6)
    assert result.ci_high == pytest.approx(0.05 + 1.959964 * se_unpooled, rel=1e-6)


def test_sign_convention_is_treatment_minus_control():
    result = two_proportion_ztest(300, 1000, 250, 1000)
    assert result.diff < 0 and result.z < 0 and result.ci_high < 0.05


def test_identical_arms():
    result = two_proportion_ztest(450, 1000, 450, 1000)
    assert result.diff == 0 and result.z == 0
    assert result.p_value == pytest.approx(1.0)


def test_degenerate_all_zero():
    result = two_proportion_ztest(0, 100, 0, 100)
    assert result.p_value == 1.0
    assert math.isnan(result.relative_lift)


def test_ci_coverage_by_simulation():
    # Build many experiments with a known true difference and check the 95%
    # interval contains it about 95% of the time.
    rng = np.random.default_rng(1)
    p_a, p_b, n = 0.19, 0.20, 20_000
    hits = 0
    trials = 2_000
    for x_a, x_b in zip(rng.binomial(n, p_a, trials), rng.binomial(n, p_b, trials)):
        r = two_proportion_ztest(int(x_a), n, int(x_b), n)
        hits += r.ci_low <= p_b - p_a <= r.ci_high
    assert hits / trials == pytest.approx(0.95, abs=0.015)


@pytest.mark.parametrize("args", [(5, 4, 1, 10), (1, 0, 1, 10), (-1, 10, 1, 10)])
def test_rejects_bad_input(args):
    with pytest.raises(ValueError):
        two_proportion_ztest(*args)
