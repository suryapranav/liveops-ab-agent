"""A/A simulation: how much does "peeking" inflate false positives?

Peeking = checking the p-value repeatedly while data comes in and stopping
as soon as it dips below alpha. Each look is another chance for noise to
cross the line, so the overall false-positive rate climbs above alpha.

Simulation design:
- Both arms have the SAME true rate p (an A/A test), so every
  "significant" result is a false positive by construction.
- Users arrive in n_looks equal batches. After each batch we run the
  pooled two-proportion z-test on all data so far.
- We report two rates:
    fpr_final_look: share of simulations significant at the last look only
                    (the honest fixed-horizon test; should be close to alpha)
    fpr_any_look:   share significant at ANY look (what a peeker would get)

Speed trick: the number of successes in a batch of b users is
Binomial(b, p), so we draw one binomial per batch instead of b coin flips.
"""
import math
from dataclasses import dataclass
from statistics import NormalDist

import numpy as np

from ._checks import require_count, require_probability


@dataclass(frozen=True)
class PeekingResult:
    p: float
    n_per_arm: int
    n_looks: int
    alpha: float
    n_sims: int
    seed: int
    fpr_final_look: float
    fpr_any_look: float
    mc_standard_error: float     # Monte Carlo noise in fpr_any_look
    fpr_by_look: tuple           # share significant at ANY look up to look k


def simulate_aa_peeking(p=0.45, n_per_arm=10_000, n_looks=5, alpha=0.05,
                        n_sims=10_000, seed=0):
    require_probability(p, "p")
    require_probability(alpha, "alpha")
    for name, value in [("n_per_arm", n_per_arm), ("n_looks", n_looks), ("n_sims", n_sims)]:
        require_count(value, name)
        if value == 0:
            raise ValueError(f"{name} must be > 0")
    if n_looks > n_per_arm:
        raise ValueError("cannot have more looks than users per arm")

    # Look boundaries, e.g. 10_000 users and 5 looks -> 2000, 4000, ..., 10_000.
    # Rounding means batches can differ by one user when it doesn't divide evenly.
    cumulative_n = np.round(np.linspace(0, n_per_arm, n_looks + 1)).astype(int)[1:]
    batch_sizes = np.diff(cumulative_n, prepend=0)

    rng = np.random.default_rng(seed)
    # Shape (n_sims, n_looks): successes in each batch, for each simulation.
    batch_x_a = rng.binomial(batch_sizes, p, size=(n_sims, n_looks))
    batch_x_b = rng.binomial(batch_sizes, p, size=(n_sims, n_looks))
    cum_x_a = np.cumsum(batch_x_a, axis=1)
    cum_x_b = np.cumsum(batch_x_b, axis=1)

    # Same pooled z-test as proportions.two_proportion_ztest, vectorised.
    # Arms are equal size here, so 1/n_a + 1/n_b = 2/n.
    p_a = cum_x_a / cumulative_n
    p_b = cum_x_b / cumulative_n
    p_pool = (cum_x_a + cum_x_b) / (2 * cumulative_n)
    se = np.sqrt(p_pool * (1 - p_pool) * 2 / cumulative_n)
    with np.errstate(divide="ignore", invalid="ignore"):
        z = np.where(se > 0, (p_b - p_a) / se, 0.0)

    # |z| > z_crit is the same decision as p_value < alpha, and cheaper.
    z_crit = NormalDist().inv_cdf(1 - alpha / 2)
    significant = np.abs(z) > z_crit                       # (n_sims, n_looks)
    significant_so_far = np.logical_or.accumulate(significant, axis=1)

    fpr_any = float(significant_so_far[:, -1].mean())
    return PeekingResult(
        p=p, n_per_arm=n_per_arm, n_looks=n_looks, alpha=alpha,
        n_sims=n_sims, seed=seed,
        fpr_final_look=float(significant[:, -1].mean()),
        fpr_any_look=fpr_any,
        mc_standard_error=math.sqrt(fpr_any * (1 - fpr_any) / n_sims),
        fpr_by_look=tuple(float(v) for v in significant_so_far.mean(axis=0)),
    )
