"""Load and validate the Cookie Cats A/B test CSV.

Columns: userid, version (gate_30 | gate_40), sum_gamerounds,
retention_1, retention_7 (booleans).

IMPORTANT: sum_gamerounds is measured AFTER assignment. Moving the gate
changes how many rounds people play, so it is an outcome of the treatment,
not a fixed property of the player. Splitting users by it ("players with
>50 rounds") compares different kinds of people in each arm and biases the
result. So this module only exposes the pre-registered retention outcomes
for arm comparisons, and refuses anything else.
"""
import pandas as pd

REQUIRED_COLUMNS = ("userid", "version", "sum_gamerounds", "retention_1", "retention_7")
CONTROL, TREATMENT = "gate_30", "gate_40"
ARMS = (CONTROL, TREATMENT)
OUTCOME_METRICS = ("retention_1", "retention_7")


def load_cookie_cats(path):
    """Read the CSV and fail loudly if it does not look like Cookie Cats."""
    df = pd.read_csv(path)

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"missing columns: {missing}")

    unknown_arms = set(df["version"].unique()) - set(ARMS)
    if unknown_arms:
        raise ValueError(f"unexpected version values: {sorted(unknown_arms)}")
    for arm in ARMS:
        if not (df["version"] == arm).any():
            raise ValueError(f"no users in arm {arm}")

    if df["userid"].duplicated().any():
        raise ValueError("duplicate userid rows: a user must be counted once")

    for metric in OUTCOME_METRICS:
        values = set(df[metric].unique())
        if not values <= {True, False}:  # also accepts 0/1, since 1 == True
            raise ValueError(f"{metric} must be boolean, found {sorted(map(str, values))}")
        df[metric] = df[metric].astype(bool)

    return df


def arm_counts(df, metric):
    """Return {arm: (successes, n)} for one pre-registered retention metric."""
    if metric not in OUTCOME_METRICS:
        raise ValueError(
            f"{metric!r} is not an allowed outcome; use one of {OUTCOME_METRICS}. "
            "(sum_gamerounds is post-treatment and must not be used to segment.)"
        )
    counts = {}
    for arm in ARMS:
        arm_rows = df.loc[df["version"] == arm, metric]
        counts[arm] = (int(arm_rows.sum()), int(len(arm_rows)))
    return counts
