import sqlite3

import pytest

from liveops_ab.db import build_database, open_readonly
from conftest import make_players


def test_counts_round_trip(db_path):
    conn = open_readonly(db_path)
    rows = conn.execute(
        "SELECT version, COUNT(*), SUM(retention_7) FROM players GROUP BY version ORDER BY version"
    ).fetchall()
    assert [tuple(r) for r in rows] == [("gate_30", 1000, 200), ("gate_40", 1000, 180)]


def test_metadata_stored(db_path):
    row = open_readonly(db_path).execute("SELECT * FROM experiment").fetchone()
    assert row["primary_metric"] == "retention_7"
    assert row["alpha"] == 0.05 and row["expected_share_control"] == 0.5


@pytest.mark.parametrize("statement", [
    "DELETE FROM players",
    "UPDATE players SET retention_7 = 1",
    "INSERT INTO players VALUES (99999, 'gate_30', 1, 1, 1)",
    "DROP TABLE players",
    "CREATE TABLE x (a)",
])
def test_readonly_connection_blocks_writes(db_path, statement):
    conn = open_readonly(db_path)
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        conn.execute(statement)


def test_refuses_to_overwrite(db_path):
    with pytest.raises(FileExistsError):
        build_database(make_players(), db_path)


def test_path_with_spaces(tmp_path):
    path = build_database(make_players(10, 10, 2, 2), tmp_path / "my folder.db")
    assert open_readonly(path).execute("SELECT COUNT(*) FROM players").fetchone()[0] == 20
