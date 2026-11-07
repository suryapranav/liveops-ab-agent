import pytest
from scipy import stats

from liveops_ab import srm_check


def test_matches_scipy_chisquare():
    result = srm_check(50_400, 49_600)
    reference = stats.chisquare([50_400, 49_600], f_exp=[50_000, 50_000])
    assert result.chi2 == pytest.approx(reference.statistic)
    assert result.p_value == pytest.approx(reference.pvalue)


def test_perfect_split_is_fine():
    result = srm_check(10_000, 10_000)
    assert result.chi2 == 0
    assert result.p_value == pytest.approx(1.0)
    assert not result.srm_detected


def test_skewed_split_is_detected():
    # 52/48 on 100k users is far outside what chance produces.
    result = srm_check(52_000, 48_000)
    assert result.srm_detected
    assert result.p_value < 1e-30


def test_unequal_planned_split():
    # A planned 90/10 split observed as 90/10 is NOT a mismatch...
    assert not srm_check(9_000, 1_000, expected_share_a=0.9).srm_detected
    # ...but the same counts against a 50/50 plan are.
    assert srm_check(9_000, 1_000, expected_share_a=0.5).srm_detected


def test_threshold_is_respected():
    # Pick counts whose p-value lands between 0.001 and 0.05.
    result = srm_check(10_150, 9_850)
    assert 0.001 < result.p_value < 0.05
    assert not result.srm_detected                         # default alpha = 0.001
    assert srm_check(10_150, 9_850, alpha=0.05).srm_detected


@pytest.mark.parametrize("args", [(-1, 10), (0, 0), (1.5, 10), (True, 10)])
def test_rejects_bad_input(args):
    with pytest.raises((ValueError, TypeError)):
        srm_check(*args)
