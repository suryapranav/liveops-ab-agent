"""Small input validators shared by the statistics modules.

Bad inputs (negative counts, more successes than users) should fail loudly
here rather than produce a plausible-looking but meaningless p-value.
"""
import numbers


def require_count(value, name):
    """A count must be a non-negative integer (bool is rejected on purpose)."""
    if isinstance(value, bool) or not isinstance(value, numbers.Integral):
        raise TypeError(f"{name} must be an integer, got {value!r}")
    if value < 0:
        raise ValueError(f"{name} must be >= 0, got {value}")


def require_group(successes, n, name):
    """Validate one arm: n users, of whom `successes` had the outcome."""
    require_count(n, f"{name} n")
    require_count(successes, f"{name} successes")
    if n == 0:
        raise ValueError(f"{name} has no users")
    if successes > n:
        raise ValueError(f"{name} successes ({successes}) > n ({n})")


def require_probability(value, name, *, open_interval=True):
    if open_interval and not 0 < value < 1:
        raise ValueError(f"{name} must be strictly between 0 and 1, got {value}")
    if not open_interval and not 0 <= value <= 1:
        raise ValueError(f"{name} must be between 0 and 1, got {value}")
