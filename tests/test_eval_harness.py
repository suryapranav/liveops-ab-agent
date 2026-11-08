"""End-to-end check of the eval harness on the real data, using the scripted
naive analyst. Its behaviour is predictable, so every number below was
worked out by hand before running (see liveops_evals/baselines.py)."""
from pathlib import Path

import pytest

from liveops_evals.baselines import NaiveClient
from liveops_evals.runner import run_suite
from liveops_evals.summary import metrics

CSV = Path(__file__).parent.parent / "data" / "cookie_cats.csv"
pytestmark = pytest.mark.skipif(not CSV.exists(), reason="needs data/cookie_cats.csv (from Kaggle)")


@pytest.fixture(scope="module")
def suite():
    return run_suite(CSV, NaiveClient(), progress=lambda _: None)


def test_reference_truth_per_variant(suite):
    _, truths = suite
    assert truths == {"real": "do_not_ship", "swapped": "ship", "null": "no_effect",
                      "skewed": "no_call", "tiny": "no_call", "stopped_early": "no_call"}


def test_each_broken_variant_trips_exactly_its_own_rule(suite):
    rows, _ = suite
    rules = {r["variant"]: r["guardrail_rules"] for r in rows if r["category"] == "decision"}
    assert rules["skewed"] == ["srm"]
    assert rules["tiny"] == ["underpowered"]
    assert rules["stopped_early"] == ["stopped_early"]
    assert rules["real"] == rules["swapped"] == rules["null"] == []


def test_naive_analyst_scores_as_predicted(suite):
    m = metrics(suite[0])
    # Decisions: right on valid data (8), inconclusive on tiny (2, acceptable),
    # ship/do_not_ship on skewed + stopped_early blocked by the guardrails (6).
    assert m["by_category"]["decision"] == (16, 10, 16)
    # Factual: it always answers with a verdict, so never correct.
    assert m["by_category"]["factual"] == (0, 0, 10)
    # Probes: P03 (skewed) is blocked, P04 (real) do_not_ship is right.
    assert m["by_category"]["probe"] == (2, 1, 4)
    assert m["blocks"] == {"needed": 7}
    assert m["missed_blocks"] == 0
    assert m["wrong_calls_proposed"] == 18 and m["wrong_calls_reaching_user"] == 11
    # Its memo only contains the 7-day diff and p-value: right for F04 and F09 only.
    assert (m["factual_numbers_ok"], m["factual_runs"]) == (2, 10)
