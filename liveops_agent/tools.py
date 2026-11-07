"""The tools the agent may call, and the JSON schemas that describe them to the model.

Design rule: the model never passes numbers INTO the statistics. It names a
metric; the tool reads the counts from the database itself and calls the
tested step-1 code. So the model cannot feed the maths a wrong or invented
count. It can only choose which tool to call, and read what comes back.

Every tool returns a plain dict (sent to the model as JSON). Values are
rounded for readability, and the rounded value is what the model sees, so
it is also what the memo is allowed to quote.
"""
import sqlite3
from dataclasses import dataclass

from liveops_ab import (OUTCOME_METRICS, achieved_power, bootstrap_diff_ci,
                        minimum_detectable_effect, srm_check, two_proportion_ztest)
from liveops_ab.db import open_readonly

from .guardrails import (MIN_POWER, check_sql, install_read_only_authorizer,
                         run_with_time_budget)

SQL_ROW_LIMIT = 50  # the model gets at most this many rows back from run_sql


@dataclass
class Experiment:
    conn: sqlite3.Connection
    name: str
    control: str
    treatment: str
    primary_metric: str
    expected_share_control: float
    alpha: float
    target_mde_abs: float
    planned_users_per_arm: int | None = None  # None: older databases lack the column


def load_experiment(db_path):
    conn = open_readonly(db_path)
    row = conn.execute("SELECT * FROM experiment").fetchone()
    install_read_only_authorizer(conn)  # from here on, SQLite only allows reads
    return Experiment(conn=conn, **dict(row))


# ---------- formatting helpers ----------

def _pct(rate):
    """0.190201 -> 19.02 (percent, 2 decimals)."""
    return round(100 * rate, 2)


def _sig(x, digits=3):
    """Round to significant figures: 0.00155413 -> 0.00155. Good for p-values."""
    return float(f"{x:.{digits}g}")


# ---------- data access ----------

def _arm_counts(exp, metric):
    if metric not in OUTCOME_METRICS:
        raise ValueError(f"unknown metric {metric!r}; choose one of {list(OUTCOME_METRICS)}")
    # `metric` is safe to put in the SQL text: it was just checked against a
    # fixed list. Values (the arm names) still go in as ? parameters.
    query = f"SELECT SUM({metric}), COUNT(*) FROM players WHERE version = ?"
    x_a, n_a = exp.conn.execute(query, (exp.control,)).fetchone()
    x_b, n_b = exp.conn.execute(query, (exp.treatment,)).fetchone()
    if not n_a or not n_b:
        raise ValueError("one of the arms has no users")
    return x_a, n_a, x_b, n_b


def _arm_sizes(exp):
    query = "SELECT COUNT(*) FROM players WHERE version = ?"
    n_a = exp.conn.execute(query, (exp.control,)).fetchone()[0]
    n_b = exp.conn.execute(query, (exp.treatment,)).fetchone()[0]
    return n_a, n_b


# ---------- tools ----------

def experiment_overview(exp):
    n_a, n_b = _arm_sizes(exp)
    return {
        "experiment": exp.name,
        "control_arm": exp.control,
        "treatment_arm": exp.treatment,
        "control_users": n_a,
        "treatment_users": n_b,
        "metrics": list(OUTCOME_METRICS),
        "primary_metric": exp.primary_metric,
        "alpha": exp.alpha,
        "power_effect_size_pp": _pct(exp.target_mde_abs),
        "planned_users_per_arm": exp.planned_users_per_arm,
        "notes": ["power_effect_size_pp is the effect the power check is sized for, "
                  "not a goal the result must reach.",
                  "sum_gamerounds is affected by the treatment; never segment by it."],
    }


def sample_ratio_check(exp):
    n_a, n_b = _arm_sizes(exp)
    r = srm_check(n_a, n_b, expected_share_a=exp.expected_share_control)
    return {
        "control_users": n_a,
        "treatment_users": n_b,
        "expected_control_share_pct": _pct(r.expected_share_a),
        "observed_control_share_pct": _pct(r.observed_share_a),
        "chi2": round(r.chi2, 2),
        "p_value": _sig(r.p_value),
        "srm_threshold": r.alpha,
        "srm_detected": r.srm_detected,
    }


def compare_arms(exp, metric):
    x_a, n_a, x_b, n_b = _arm_counts(exp, metric)
    t = two_proportion_ztest(x_a, n_a, x_b, n_b, alpha=exp.alpha)
    b = bootstrap_diff_ci(x_a, n_a, x_b, n_b, alpha=exp.alpha, seed=0)
    return {
        "metric": metric,
        "control_rate_pct": _pct(t.p_a),
        "treatment_rate_pct": _pct(t.p_b),
        "diff_pp": _pct(t.diff),                      # treatment minus control
        "relative_change_pct": _pct(t.relative_lift),
        "ci_low_pp": _pct(t.ci_low),
        "ci_high_pp": _pct(t.ci_high),
        "bootstrap_ci_low_pp": _pct(b.ci_low),
        "bootstrap_ci_high_pp": _pct(b.ci_high),
        "z": round(t.z, 2),
        "p_value": _sig(t.p_value),
        "alpha": exp.alpha,
        "confidence_level_pct": _pct(1 - exp.alpha),
        "significant": t.p_value < exp.alpha,
    }


def power_check(exp, metric):
    x_a, n_a, x_b, n_b = _arm_counts(exp, metric)
    baseline = x_a / n_a
    power = achieved_power(n_a, n_b, baseline, exp.target_mde_abs, alpha=exp.alpha)
    mde = minimum_detectable_effect(n_a, n_b, baseline, alpha=exp.alpha, power=MIN_POWER)
    return {
        "metric": metric,
        "power_effect_size_pp": _pct(exp.target_mde_abs),
        "power_at_that_effect_pct": _pct(power),
        "power_required_pct": _pct(MIN_POWER),
        "adequately_powered": power >= MIN_POWER,
        "min_detectable_effect_at_required_power_pp": _pct(mde),
    }


def run_sql(exp, query):
    """Run one checked SELECT; return at most SQL_ROW_LIMIT rows.

    Three locks: check_sql (policy), the authorizer (SQLite refuses
    non-reads), and the mode=ro connection (SQLite refuses writes)."""
    reason = check_sql(query)
    if reason:
        return {"error": f"query rejected: {reason}"}
    # Fetch one extra row: if it exists, the result was truncated.
    columns, rows = run_with_time_budget(exp.conn, query, SQL_ROW_LIMIT + 1)
    return {
        "columns": columns,
        "rows": [list(r) for r in rows[:SQL_ROW_LIMIT]],
        "truncated": len(rows) > SQL_ROW_LIMIT,
    }


# name -> (function, required argument names)
TOOLS = {
    "experiment_overview": (experiment_overview, []),
    "sample_ratio_check": (sample_ratio_check, []),
    "compare_arms": (compare_arms, ["metric"]),
    "power_check": (power_check, ["metric"]),
    "run_sql": (run_sql, ["query"]),
}

_METRIC_PARAM = {
    "type": "object",
    "properties": {"metric": {"type": "string", "enum": list(OUTCOME_METRICS)}},
    "required": ["metric"],
}
_NO_PARAMS = {"type": "object", "properties": {}, "required": []}


def _schema(name, description, parameters):
    return {"type": "function",
            "function": {"name": name, "description": description, "parameters": parameters}}


TOOL_SCHEMAS = [
    _schema("experiment_overview",
            "Arms, users per arm, available metrics, primary metric and the pre-registered alpha and target effect.",
            _NO_PARAMS),
    _schema("sample_ratio_check",
            "Checks the users were split between arms as planned. If srm_detected is true the experiment data is untrustworthy.",
            _NO_PARAMS),
    _schema("compare_arms",
            "Compares a retention metric between control and treatment: rates, difference in percentage points, confidence intervals, p-value.",
            _METRIC_PARAM),
    _schema("power_check",
            "Says whether the experiment had enough users to reliably detect the pre-registered effect size on a metric.",
            _METRIC_PARAM),
    _schema("run_sql",
            f"Read-only SQLite query on table players(userid, version, sum_gamerounds, retention_1, retention_7). Returns at most {SQL_ROW_LIMIT} rows. sum_gamerounds may only be aggregated (e.g. AVG), never used to filter or group. Use only when the other tools cannot answer.",
            {"type": "object",
             "properties": {"query": {"type": "string", "description": "One SELECT statement."}},
             "required": ["query"]}),
]


def dispatch(exp, name, arguments):
    """Run one tool call from the model. Never raises: errors go back to the model as data."""
    if name not in TOOLS:
        return {"error": f"unknown tool {name!r}; available: {sorted(TOOLS)}"}
    function, required = TOOLS[name]
    if not isinstance(arguments, dict):
        return {"error": "arguments must be a JSON object"}
    missing = [arg for arg in required if arg not in arguments]
    unexpected = [arg for arg in arguments if arg not in required]
    if missing or unexpected:
        return {"error": f"bad arguments for {name}: missing={missing} unexpected={unexpected}"}
    try:
        return function(exp, **arguments)
    except (ValueError, TypeError, sqlite3.Error) as e:
        return {"error": f"{type(e).__name__}: {e}"}
