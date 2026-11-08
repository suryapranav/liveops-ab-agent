import pandas as pd

from liveops_evals.variants import null, real, skewed, stopped_early, swapped, tiny
from conftest import make_players

DF = make_players(2000, 2000, 400, 380)


def counts(df):
    return df["version"].value_counts().to_dict()


def test_real_is_unchanged():
    out, settings = real(DF)
    assert out.equals(DF) and settings == {}


def test_swapped_swaps_labels_only():
    out, _ = swapped(DF)
    assert counts(out) == counts(DF)
    before = DF.groupby("version")["retention_7"].sum()
    after = out.groupby("version")["retention_7"].sum()
    assert after["gate_40"] == before["gate_30"] and after["gate_30"] == before["gate_40"]


def test_null_keeps_arm_sizes_and_is_seeded():
    a, _ = null(DF, seed=0)
    b, _ = null(DF, seed=0)
    assert counts(a) == counts(DF)
    assert a["version"].tolist() == b["version"].tolist()
    assert a["version"].tolist() != DF["version"].tolist()


def test_skewed_drops_only_treatment_non_retainers():
    out, _ = skewed(DF, fraction=0.08)
    dropped = DF.loc[~DF.index.isin(out.index)]
    assert len(dropped) == int(0.08 * 2000)
    assert set(dropped["version"]) == {"gate_40"} and not dropped["retention_7"].any()


def test_tiny_samples_a_fraction():
    out, _ = tiny(DF, fraction=0.02)
    assert len(out) == round(0.02 * len(DF))


def test_stopped_early_is_a_prefix_with_a_plan():
    shuffled = DF.sample(frac=1, random_state=1)        # input order must not matter
    out, settings = stopped_early(shuffled, fraction=0.6)
    assert settings == {"planned_users_per_arm": 2000}
    assert out["userid"].tolist() == sorted(DF["userid"])[: int(0.6 * len(DF))]
