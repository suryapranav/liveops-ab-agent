import pandas as pd
import pytest

from liveops_ab import arm_counts, load_cookie_cats


def write_csv(tmp_path, rows):
    path = tmp_path / "cookie_cats.csv"
    pd.DataFrame(rows, columns=["userid", "version", "sum_gamerounds",
                                "retention_1", "retention_7"]).to_csv(path, index=False)
    return path


GOOD_ROWS = [
    (1, "gate_30", 10, True, False),
    (2, "gate_30", 0, False, False),
    (3, "gate_40", 50, True, True),
    (4, "gate_40", 5, True, False),
    (5, "gate_40", 1, False, False),
]


def test_counts(tmp_path):
    df = load_cookie_cats(write_csv(tmp_path, GOOD_ROWS))
    assert arm_counts(df, "retention_1") == {"gate_30": (1, 2), "gate_40": (2, 3)}
    assert arm_counts(df, "retention_7") == {"gate_30": (0, 2), "gate_40": (1, 3)}


def test_refuses_post_treatment_metric(tmp_path):
    df = load_cookie_cats(write_csv(tmp_path, GOOD_ROWS))
    with pytest.raises(ValueError, match="post-treatment"):
        arm_counts(df, "sum_gamerounds")


def test_rejects_duplicate_users(tmp_path):
    with pytest.raises(ValueError, match="duplicate"):
        load_cookie_cats(write_csv(tmp_path, GOOD_ROWS + [GOOD_ROWS[0]]))


def test_rejects_unknown_arm(tmp_path):
    with pytest.raises(ValueError, match="unexpected version"):
        load_cookie_cats(write_csv(tmp_path, GOOD_ROWS + [(9, "gate_50", 1, True, True)]))


def test_rejects_missing_arm(tmp_path):
    with pytest.raises(ValueError, match="no users in arm gate_40"):
        load_cookie_cats(write_csv(tmp_path, GOOD_ROWS[:2]))


def test_rejects_missing_retention_values(tmp_path):
    rows = GOOD_ROWS + [(9, "gate_30", 1, None, True)]
    with pytest.raises(ValueError, match="retention_1 must be boolean"):
        load_cookie_cats(write_csv(tmp_path, rows))
