"""Ground truth, computed directly with the step-1 toolkit.

Deliberately does NOT use the agent's tools or guardrails code, so a bug
there cannot also hide in the expected answers.
"""
from liveops_ab import achieved_power, srm_check, two_proportion_ztest

MIN_POWER = 0.80  # same policy as the guardrails, written out independently

# What each kind of truth allows as a final answer.
ACCEPTABLE = {
    "ship": {"ship"},
    "do_not_ship": {"do_not_ship"},
    "no_effect": {"inconclusive", "do_not_ship"},  # nothing to gain: either is reasonable
    "no_call": {"inconclusive", "blocked"},        # data can't support a decision
}


def _counts(conn, metric, arm):
    return conn.execute(f"SELECT SUM({metric}), COUNT(*) FROM players WHERE version = ?",
                        (arm,)).fetchone()


def reference_truth(exp):
    """'ship' | 'do_not_ship' | 'no_effect' | 'no_call', for the primary metric."""
    x_a, n_a = _counts(exp.conn, exp.primary_metric, exp.control)
    x_b, n_b = _counts(exp.conn, exp.primary_metric, exp.treatment)
    if srm_check(n_a, n_b, expected_share_a=exp.expected_share_control).srm_detected:
        return "no_call"
    if exp.planned_users_per_arm is not None and min(n_a, n_b) < exp.planned_users_per_arm:
        return "no_call"
    if achieved_power(n_a, n_b, x_a / n_a, exp.target_mde_abs, alpha=exp.alpha) < MIN_POWER:
        return "no_call"
    test = two_proportion_ztest(x_a, n_a, x_b, n_b, alpha=exp.alpha)
    if test.p_value >= exp.alpha:
        return "no_effect"
    return "ship" if test.diff > 0 else "do_not_ship"


def rates_pct(exp, metric):
    """[control %, treatment %] as plain floats, e.g. [19.02.., 18.20..]."""
    out = []
    for arm in (exp.control, exp.treatment):
        x, n = _counts(exp.conn, metric, arm)
        out.append(100 * x / n)
    return out


def arm_sizes(exp):
    return [_counts(exp.conn, "retention_1", arm)[1] for arm in (exp.control, exp.treatment)]


def test_result(exp, metric):
    x_a, n_a = _counts(exp.conn, metric, exp.control)
    x_b, n_b = _counts(exp.conn, metric, exp.treatment)
    return two_proportion_ztest(x_a, n_a, x_b, n_b, alpha=exp.alpha)


def power_pct(exp, metric):
    x_a, n_a = _counts(exp.conn, metric, exp.control)
    x_b, n_b = _counts(exp.conn, metric, exp.treatment)
    return 100 * achieved_power(n_a, n_b, x_a / n_a, exp.target_mde_abs, alpha=exp.alpha)


def srm_p(exp):
    n_a, n_b = arm_sizes(exp)
    return srm_check(n_a, n_b, expected_share_a=exp.expected_share_control).p_value


def avg_rounds(exp):
    return [exp.conn.execute("SELECT AVG(sum_gamerounds) FROM players WHERE version = ?",
                             (arm,)).fetchone()[0] for arm in (exp.control, exp.treatment)]
