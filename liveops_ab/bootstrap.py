"""Percentile bootstrap confidence interval for a difference in rates.

Why have this when the z-test already gives a CI? It is an independent
check that does not rely on the normal approximation. If the two intervals
disagree badly, the normal approximation is suspect.

Speed trick (and why it is exact, not an approximation):
Resampling n users with replacement from an arm where x of n retained means
each resampled user independently retains with probability x/n. The number
of retained users in the resample is therefore exactly Binomial(n, x/n).
So instead of building a 45,000-element array 10,000 times, we draw 10,000
binomial counts. tests/test_bootstrap.py checks this against the slow way.
"""
from dataclasses import dataclass

import numpy as np

from ._checks import require_count, require_group, require_probability


@dataclass(frozen=True)
class BootstrapResult:
    diff: float      # observed p_b - p_a
    ci_low: float
    ci_high: float
    alpha: float
    n_boot: int
    seed: int


def bootstrap_diff_ci(x_a, n_a, x_b, n_b, alpha=0.05, n_boot=10_000, seed=0):
    """Percentile bootstrap CI for p_b - p_a. Same seed -> same answer."""
    require_group(x_a, n_a, "arm A")
    require_group(x_b, n_b, "arm B")
    require_probability(alpha, "alpha")
    require_count(n_boot, "n_boot")
    if n_boot < 1000:
        raise ValueError("n_boot should be at least 1000 for stable tails")

    rng = np.random.default_rng(seed)
    boot_p_a = rng.binomial(n_a, x_a / n_a, size=n_boot) / n_a
    boot_p_b = rng.binomial(n_b, x_b / n_b, size=n_boot) / n_b
    boot_diffs = boot_p_b - boot_p_a

    ci_low, ci_high = np.quantile(boot_diffs, [alpha / 2, 1 - alpha / 2])
    return BootstrapResult(
        diff=x_b / n_b - x_a / n_a,
        ci_low=float(ci_low),
        ci_high=float(ci_high),
        alpha=alpha,
        n_boot=n_boot,
        seed=seed,
    )
