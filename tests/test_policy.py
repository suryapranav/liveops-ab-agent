"""The decision policy on healthy and deliberately broken experiments."""
import pytest

from liveops_agent.guardrails import apply_decision_policy

FULL_EVIDENCE = [
    {"name": "sample_ratio_check", "arguments": {}, "result": {}},
    {"name": "compare_arms", "arguments": {"metric": "retention_7"}, "result": {}},
    {"name": "power_check", "arguments": {"metric": "retention_7"}, "result": {}},
]


def memo(decision):
    return {"decision": decision, "answer": "", "key_numbers": [], "risks": []}


def rules(events):
    return sorted(e.rule for e in events)


# A big target effect (10 pp) makes 1000 users per arm adequately powered.
HEALTHY = dict(target_mde_abs=0.10)


def test_healthy_experiment_decision_stands(make_experiment):
    exp = make_experiment(**HEALTHY)
    assert apply_decision_policy(exp, memo("do_not_ship"), FULL_EVIDENCE, []) == ("do_not_ship", [])


@pytest.mark.parametrize("decision", ["ship", "do_not_ship"])
def test_srm_blocks(make_experiment, decision):
    exp = make_experiment(n_control=1000, n_treatment=1300, **HEALTHY)
    final, events = apply_decision_policy(exp, memo(decision), FULL_EVIDENCE, [])
    assert final == "blocked" and rules(events) == ["srm"]


def test_underpowered_blocks(make_experiment):
    exp = make_experiment(target_mde_abs=0.01)  # 1000/arm cannot detect 1 pp
    final, events = apply_decision_policy(exp, memo("ship"), FULL_EVIDENCE, [])
    assert final == "blocked" and rules(events) == ["underpowered"]


def test_stopped_early_blocks(make_experiment):
    exp = make_experiment(planned_users_per_arm=5000, **HEALTHY)
    final, events = apply_decision_policy(exp, memo("ship"), FULL_EVIDENCE, [])
    assert final == "blocked" and rules(events) == ["stopped_early"]


def test_reaching_the_plan_is_fine(make_experiment):
    exp = make_experiment(planned_users_per_arm=1000, **HEALTHY)
    assert apply_decision_policy(exp, memo("ship"), FULL_EVIDENCE, [])[0] == "ship"


def test_decision_without_evidence_blocks(make_experiment):
    exp = make_experiment(**HEALTHY)
    only_compare = [FULL_EVIDENCE[1]]
    final, events = apply_decision_policy(exp, memo("do_not_ship"), only_compare, [])
    assert final == "blocked"
    assert "sample_ratio_check()" in events[0].detail and "power_check(retention_7)" in events[0].detail


def test_evidence_on_the_wrong_metric_does_not_count(make_experiment):
    exp = make_experiment(**HEALTHY)
    wrong_metric = [dict(c, arguments={"metric": "retention_1"}) if c["arguments"] else c
                    for c in FULL_EVIDENCE]
    assert apply_decision_policy(exp, memo("ship"), wrong_metric, [])[0] == "blocked"


def test_failed_tool_calls_do_not_count_as_evidence(make_experiment):
    exp = make_experiment(**HEALTHY)
    failed = [dict(c, result={"error": "boom"}) for c in FULL_EVIDENCE]
    assert apply_decision_policy(exp, memo("ship"), failed, [])[0] == "blocked"


@pytest.mark.parametrize("decision", ["inconclusive", "not_applicable"])
def test_non_calls_pass_but_still_carry_warnings(make_experiment, decision):
    exp = make_experiment(n_control=1000, n_treatment=1300, **HEALTHY)
    final, events = apply_decision_policy(exp, memo(decision), [], [])
    assert final == decision and rules(events) == ["srm"]


def test_unsupported_numbers_block_any_decision(make_experiment):
    exp = make_experiment(**HEALTHY)
    final, events = apply_decision_policy(exp, memo("not_applicable"), [], ["number 9 in text"])
    assert final == "blocked" and rules(events) == ["unsupported_numbers"]


def test_no_memo_is_an_error(make_experiment):
    assert apply_decision_policy(make_experiment(), None, [], []) == ("error", [])
