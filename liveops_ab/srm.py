"""Sample-ratio-mismatch (SRM) check.

If users were randomised with a known split (e.g. 50/50), the observed arm
sizes should be close to that split. A large deviation means assignment or
logging is broken, so any comparison between the arms is untrustworthy,
however good the metric looks.

Test: chi-square goodness-of-fit with two categories (1 degree of freedom).
With one degree of freedom, chi2 = z**2 for a standard normal z, so the
p-value is P(|Z| >= sqrt(chi2)) = 2 * Phi(-sqrt(chi2)).
"""
import math
from dataclasses import dataclass
from statistics import NormalDist

from ._checks import require_count, require_probability

# Strict on purpose. SRM is a "the data is broken" alarm, run on every
# experiment, so a loose threshold would raise false alarms constantly.
# 0.001 is a common industry convention; it is a parameter, not a law.
DEFAULT_SRM_ALPHA = 0.001


@dataclass(frozen=True)
class SRMResult:
    n_a: int
    n_b: int
    expected_share_a: float
    observed_share_a: float
    chi2: float
    p_value: float
    alpha: float
    srm_detected: bool


def srm_check(n_a, n_b, expected_share_a=0.5, alpha=DEFAULT_SRM_ALPHA):
    """Check whether arm sizes n_a, n_b are consistent with the planned split."""
    require_count(n_a, "n_a")
    require_count(n_b, "n_b")
    require_probability(expected_share_a, "expected_share_a")
    require_probability(alpha, "alpha")
    total = n_a + n_b
    if total == 0:
        raise ValueError("no users in either arm")

    expected_a = total * expected_share_a
    expected_b = total - expected_a
    chi2 = (n_a - expected_a) ** 2 / expected_a + (n_b - expected_b) ** 2 / expected_b
    # Phi(-z) instead of 1 - Phi(z): avoids losing precision for large z.
    p_value = 2 * NormalDist().cdf(-math.sqrt(chi2))

    return SRMResult(
        n_a=n_a,
        n_b=n_b,
        expected_share_a=expected_share_a,
        observed_share_a=n_a / total,
        chi2=chi2,
        p_value=p_value,
        alpha=alpha,
        srm_detected=p_value < alpha,
    )
