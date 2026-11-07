import pytest

from liveops_ab import two_proportion_ztest
from liveops_agent.tools import (SQL_ROW_LIMIT, TOOL_SCHEMAS, TOOLS, dispatch,
                                 load_experiment)


@pytest.fixture
def exp(db_path):
    return load_experiment(db_path)


def test_every_schema_has_a_tool_and_vice_versa():
    schema_names = {s["function"]["name"] for s in TOOL_SCHEMAS}
    assert schema_names == set(TOOLS)
    for s in TOOL_SCHEMAS:
        name = s["function"]["name"]
        assert s["function"]["parameters"]["required"] == TOOLS[name][1]


def test_compare_arms_matches_step1_toolkit(exp):
    result = dispatch(exp, "compare_arms", {"metric": "retention_7"})
    direct = two_proportion_ztest(200, 1000, 180, 1000)
    assert result["control_rate_pct"] == 20.0
    assert result["treatment_rate_pct"] == 18.0
    assert result["diff_pp"] == -2.0
    assert result["p_value"] == pytest.approx(direct.p_value, rel=1e-2)
    assert result["significant"] is False


def test_srm_tool(exp):
    result = dispatch(exp, "sample_ratio_check", {})
    assert result["control_users"] == 1000 and result["srm_detected"] is False
    assert result["srm_threshold"] == 0.001


def test_power_tool(exp):
    result = dispatch(exp, "power_check", {"metric": "retention_7"})
    assert result["target_mde_pp"] == 1.0
    assert result["power_at_target_mde_pct"] < 20  # 1000 users/arm is far too few for 1 pp


def test_overview(exp):
    result = dispatch(exp, "experiment_overview", {})
    assert result["primary_metric"] == "retention_7"
    assert result["control_users"] + result["treatment_users"] == 2000


def test_sql_row_limit(exp):
    result = dispatch(exp, "run_sql", {"query": "SELECT userid FROM players"})
    assert len(result["rows"]) == SQL_ROW_LIMIT and result["truncated"] is True


def test_sql_aggregate(exp):
    result = dispatch(exp, "run_sql", {"query": "SELECT COUNT(*) AS n FROM players"})
    assert result == {"columns": ["n"], "rows": [[2000]], "truncated": False}


def test_sql_write_comes_back_as_error_not_crash(exp):
    result = dispatch(exp, "run_sql", {"query": "DELETE FROM players"})
    assert "readonly" in result["error"]
    assert dispatch(exp, "run_sql", {"query": "SELECT COUNT(*) FROM players"})["rows"] == [[2000]]


@pytest.mark.parametrize("name, args, fragment", [
    ("no_such_tool", {}, "unknown tool"),
    ("compare_arms", {}, "missing=['metric']"),
    ("compare_arms", {"metric": "sum_gamerounds"}, "unknown metric"),
    ("sample_ratio_check", {"metric": "retention_7"}, "unexpected=['metric']"),
    ("run_sql", {"query": "SELEC nonsense"}, "OperationalError"),
    ("compare_arms", "retention_7", "JSON object"),
])
def test_bad_calls_return_errors(exp, name, args, fragment):
    assert fragment in dispatch(exp, name, args)["error"]
