"""Power and sample size for comparing two rates (two-sided test).

Vocabulary:
- p_baseline: the control arm's rate (e.g. 0.19 for 7-day retention).
- mde_abs: minimum detectable effect, absolute (0.01 = 1 percentage point).
  The treatment rate is assumed to be p_baseline + mde_abs.
- power: probability the test detects the effect if it really exists.

All three functions use the same normal-approximation model, so they are
consistent with each other: achieved_power(required_sample_size(...)) is
at least the requested power (tested in tests/test_power.py).

The formula ignores the probability of rejecting in the *wrong* direction
(treatment looks significantly worse when it is truly better). For any
realistic effect size that term is negligible (far below 1e-6).
"""
import math
from statistics import NormalDist

from ._checks import require_count, require_probability

_NORMAL = NormalDist()


def _treatment_rate(p_baseline, mde_abs):
    require_probability(p_baseline, "p_baseline")
    if mde_abs == 0:
        raise ValueError("mde_abs must be non-zero")
    p_treat = p_baseline + mde_abs
    require_probability(p_treat, "p_baseline + mde_abs")
    return p_treat


def required_sample_size(p_baseline, mde_abs, alpha=0.05, power=0.8):
    """Users needed PER ARM (equal arms) to detect mde_abs with `power`.

    n = (z_{1-alpha/2} * sqrt(2 * pbar * (1 - pbar))
         + z_{power}  * sqrt(p1 * (1 - p1) + p2 * (1 - p2)))**2 / mde**2
    where pbar = (p1 + p2) / 2. The first term is the noise under H0
    (one shared rate), the second the noise under H1 (two rates).
    """
    require_probability(alpha, "alpha")
    require_probability(power, "power")
    p1 = p_baseline
    p2 = _treatment_rate(p_baseline, mde_abs)
    p_bar = (p1 + p2) / 2
    z_alpha = _NORMAL.inv_cdf(1 - alpha / 2)
    z_power = _NORMAL.inv_cdf(power)
    numerator = (
        z_alpha * math.sqrt(2 * p_bar * (1 - p_bar))
        + z_power * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))
    ) ** 2
    return math.ceil(numerator / mde_abs ** 2)


def achieved_power(n_a, n_b, p_baseline, mde_abs, alpha=0.05):
    """Power of a test that already has n_a and n_b users (arms may differ).

    We reject when |diff| > z_alpha * SE0 (SE under H0, pooled rate).
    If the true difference is mde, diff ~ Normal(mde, SE1) (SE under H1), so
    power = P(diff > z_alpha * SE0) = Phi((|mde| - z_alpha * SE0) / SE1).
    """
    require_count(n_a, "n_a")
    require_count(n_b, "n_b")
    if n_a == 0 or n_b == 0:
        raise ValueError("both arms need users")
    require_probability(alpha, "alpha")
    p1 = p_baseline
    p2 = _treatment_rate(p_baseline, mde_abs)
    p_pool = (n_a * p1 + n_b * p2) / (n_a + n_b)
    se0 = math.sqrt(p_pool * (1 - p_pool) * (1 / n_a + 1 / n_b))
    se1 = math.sqrt(p1 * (1 - p1) / n_a + p2 * (1 - p2) / n_b)
    z_alpha = _NORMAL.inv_cdf(1 - alpha / 2)
    return _NORMAL.cdf((abs(mde_abs) - z_alpha * se0) / se1)


def minimum_detectable_effect(n_a, n_b, p_baseline, alpha=0.05, power=0.8):
    """Smallest positive absolute lift detectable with `power` at these sizes.

    No closed form for unequal arms, so we use bisection: achieved_power
    increases with mde, so we halve the search interval until it is tiny.
    Returns math.inf if even the largest possible lift is not detectable.
    """
    require_probability(power, "power")
    low = 1e-9
    high = (1 - p_baseline) - 1e-9  # treatment rate must stay below 1
    if achieved_power(n_a, n_b, p_baseline, high, alpha) < power:
        return math.inf
    for _ in range(100):  # interval shrinks by 2**100: far past float precision
        mid = (low + high) / 2
        if achieved_power(n_a, n_b, p_baseline, mid, alpha) < power:
            low = mid
        else:
            high = mid
    return high
