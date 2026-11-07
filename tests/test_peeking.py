import pytest

from liveops_ab import simulate_aa_peeking


def test_single_look_holds_alpha():
    r = simulate_aa_peeking(n_looks=1, n_sims=20_000, seed=0)
    assert r.fpr_final_look == r.fpr_any_look
    assert r.fpr_final_look == pytest.approx(0.05, abs=0.006)


def test_five_looks_inflates_to_known_value():
    # Armitage, McPherson & Rowe (1969): 5 equally spaced looks at a nominal
    # 5% level give an overall false-positive rate of about 14%.
    r = simulate_aa_peeking(n_looks=5, n_sims=20_000, seed=0)
    assert r.fpr_final_look == pytest.approx(0.05, abs=0.006)
    assert r.fpr_any_look == pytest.approx(0.142, abs=0.01)


def test_more_looks_more_false_positives():
    rates = [simulate_aa_peeking(n_looks=k, n_sims=10_000, seed=1).fpr_any_look
             for k in (1, 2, 5, 20)]
    assert rates == sorted(rates)


def test_fpr_by_look_is_cumulative():
    r = simulate_aa_peeking(n_looks=10, n_sims=5_000, seed=2)
    assert list(r.fpr_by_look) == sorted(r.fpr_by_look)
    assert r.fpr_by_look[-1] == r.fpr_any_look


def test_uneven_batches_still_use_every_user():
    r = simulate_aa_peeking(n_per_arm=1_003, n_looks=7, n_sims=500, seed=0)
    assert r.n_per_arm == 1_003


def test_rejects_bad_input():
    with pytest.raises(ValueError):
        simulate_aa_peeking(n_per_arm=3, n_looks=5)
