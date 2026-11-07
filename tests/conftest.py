"""Shared fixture: a small synthetic experiment database with known counts."""
import pandas as pd
import pytest

from liveops_ab.db import build_database


def make_players(n_control=1000, n_treatment=1000, ret7_control=200, ret7_treatment=180):
    """Players with exactly the requested numbers of 7-day retainers per arm.
    1-day retention is set to 450 retainers per 1000 users in both arms."""
    rows = []
    userid = 0
    for arm, n, ret7 in [("gate_30", n_control, ret7_control), ("gate_40", n_treatment, ret7_treatment)]:
        for i in range(n):
            userid += 1
            rows.append({"userid": userid, "version": arm, "sum_gamerounds": i % 100,
                         "retention_1": i < n * 0.45, "retention_7": i < ret7})
    return pd.DataFrame(rows)


@pytest.fixture
def db_path(tmp_path):
    return build_database(make_players(), tmp_path / "exp.db")
