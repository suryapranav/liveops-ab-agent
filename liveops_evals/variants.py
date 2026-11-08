"""Experiment variants used by the evals.

Each variant is the real Cookie Cats data with ONE documented change, so the
correct answer is known by construction (and recomputed by reference.py):

  real           unchanged                                   -> gate_40 loses on 7-day retention
  swapped        gate_30 and gate_40 labels swapped          -> gate_40 "wins" by the same margin
  null           labels randomly shuffled (seed 0)           -> no true effect
  skewed         8% of gate_40 users who did NOT retain are  -> looks like a win, but the split
                 dropped, like a logging bug                    is broken (SRM)
  tiny           random 2% of players                        -> far too small (underpowered)
  stopped_early  first 60% of players (by userid), with the  -> stopped before the planned size
                 plan set to the full size
"""
import numpy as np

from liveops_ab.data import CONTROL, TREATMENT
from liveops_ab.db import build_database


def real(df):
    return df, {}


def swapped(df):
    out = df.copy()
    out["version"] = df["version"].map({CONTROL: TREATMENT, TREATMENT: CONTROL})
    return out, {}


def null(df, seed=0):
    out = df.copy()
    # A permutation keeps the arm sizes, so only the link to outcomes is broken.
    out["version"] = np.random.default_rng(seed).permutation(df["version"].to_numpy())
    return out, {}


def skewed(df, fraction=0.08, seed=0):
    treatment_size = int((df["version"] == TREATMENT).sum())
    lost_candidates = df.index[(df["version"] == TREATMENT) & (~df["retention_7"])]
    drop = np.random.default_rng(seed).choice(
        lost_candidates, size=int(fraction * treatment_size), replace=False)
    return df.drop(index=drop), {}


def tiny(df, fraction=0.02, seed=0):
    return df.sample(frac=fraction, random_state=seed), {}


def stopped_early(df, fraction=0.6):
    planned = int(df["version"].value_counts().min())   # the full data is "the plan"
    prefix = df.sort_values("userid").iloc[: int(fraction * len(df))]
    return prefix, {"planned_users_per_arm": planned}


VARIANTS = {f.__name__: f for f in (real, swapped, null, skewed, tiny, stopped_early)}


def build_variant_databases(df, directory):
    """Write one SQLite database per variant; return {name: path}."""
    paths = {}
    for name, make in VARIANTS.items():
        variant_df, settings = make(df)
        paths[name] = build_database(variant_df, directory / f"{name}.db",
                                     name=f"cookie_cats_{name}", **settings)
    return paths
