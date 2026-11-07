import sqlite3

import pytest

from liveops_agent.guardrails import check_sql, run_with_time_budget
from liveops_agent.tools import load_experiment


@pytest.mark.parametrize("query", [
    "SELECT COUNT(*) FROM players",
    "select version, avg(retention_7) from players group by version;",
    "WITH t AS (SELECT * FROM players) SELECT COUNT(*) FROM t",
    "SELECT version, AVG(sum_gamerounds), MAX( sum_gamerounds ) FROM players GROUP BY version",
])
def test_allowed(query):
    assert check_sql(query) is None


@pytest.mark.parametrize("query, fragment", [
    ("", "non-empty"),
    ("DELETE FROM players", "only SELECT"),
    ("PRAGMA table_info(players)", "only SELECT"),
    ("SELECT 1; DROP TABLE players", "one statement"),
    ("SELECT 1 -- sneaky", "comments"),
    ("SELECT * FROM players WHERE sum_gamerounds > 30", "post-treatment"),
    ("SELECT sum_gamerounds > 30 AS heavy, AVG(retention_7) FROM players GROUP BY heavy", "post-treatment"),
    ("SELECT * FROM players ORDER BY sum_gamerounds DESC", "post-treatment"),
    ("SELECT AVG(sum_gamerounds) FROM players WHERE SUM_GAMEROUNDS < 5", "post-treatment"),
])
def test_rejected(query, fragment):
    assert fragment in check_sql(query)


@pytest.mark.parametrize("query", [
    "PRAGMA table_info(players)",                                  # passes mode=ro, not the authorizer
    "ATTACH DATABASE ':memory:' AS other",
    "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c) SELECT x FROM c LIMIT 5",
])
def test_authorizer_blocks_what_the_string_check_might_miss(db_path, query):
    # Calls the connection directly, bypassing check_sql, to test the second lock alone.
    exp = load_experiment(db_path)
    with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
        exp.conn.execute(query).fetchall()


def test_time_budget_aborts_slow_query(db_path):
    exp = load_experiment(db_path)
    slow = "SELECT COUNT(*) FROM players a, players b, players c"  # 2000**3 row combinations
    with pytest.raises(sqlite3.OperationalError, match="interrupted"):
        run_with_time_budget(exp.conn, slow, max_rows=10, budget_s=0.2)
    # the connection still works afterwards
    assert run_with_time_budget(exp.conn, "SELECT COUNT(*) FROM players", 10)[1][0][0] == 2000
