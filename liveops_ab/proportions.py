"""Two-proportion z-test and confidence interval for a difference in rates.

Convention used everywhere in this package: arm A is control, arm B is
treatment, and diff = p_b - p_a (positive means treatment is higher).
"""
import math
from dataclasses import dataclass
from statistics import NormalDist

from ._checks import require_group, require_probability


@dataclass(frozen=True)
class TwoProportionResult:
    x_a: int
    n_a: int
    x_b: int
    n_b: int
    p_a: float
    p_b: float
    diff: float           # p_b - p_a, absolute (0.01 = 1 percentage point)
    relative_lift: float  # diff / p_a (nan if p_a == 0)
    z: float
    p_value: float        # two-sided
    ci_low: float
    ci_high: float
    alpha: float


def two_proportion_ztest(x_a, n_a, x_b, n_b, alpha=0.05):
    """Compare the rate x_a/n_a (control) with x_b/n_b (treatment).

    The test and the interval deliberately use different standard errors:
    - Test: under H0 both arms share one true rate, so we estimate that one
      rate from the pooled data ("pooled SE").
    - Interval: we are estimating the difference, so we do NOT assume the
      rates are equal; each arm keeps its own variance ("unpooled SE").
    Both rely on the normal approximation, which is fine when each arm has
    plenty of successes and failures (true for ~45k users per arm).
    """
    require_group(x_a, n_a, "arm A")
    require_group(x_b, n_b, "arm B")
    require_probability(alpha, "alpha")
    normal = NormalDist()

    p_a = x_a / n_a
    p_b = x_b / n_b
    diff = p_b - p_a

    p_pool = (x_a + x_b) / (n_a + n_b)
    se_pooled = math.sqrt(p_pool * (1 - p_pool) * (1 / n_a + 1 / n_b))
    if se_pooled == 0:
        # Both arms are all-0 or all-1: identical, nothing to test.
        z, p_value = 0.0, 1.0
    else:
        z = diff / se_pooled
        p_value = 2 * normal.cdf(-abs(z))

    se_unpooled = math.sqrt(p_a * (1 - p_a) / n_a + p_b * (1 - p_b) / n_b)
    z_crit = normal.inv_cdf(1 - alpha / 2)

    return TwoProportionResult(
        x_a=x_a, n_a=n_a, x_b=x_b, n_b=n_b,
        p_a=p_a, p_b=p_b,
        diff=diff,
        relative_lift=diff / p_a if p_a > 0 else math.nan,
        z=z, p_value=p_value,
        ci_low=diff - z_crit * se_unpooled,
        ci_high=diff + z_crit * se_unpooled,
        alpha=alpha,
    )
