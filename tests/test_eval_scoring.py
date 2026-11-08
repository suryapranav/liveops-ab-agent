from types import SimpleNamespace

import pytest

from liveops_evals.cases import CASES, Case
from liveops_evals.scoring import numbers_present, score


def run(model, final, memo=True, tool_calls=(), repairs=0, left=0):
    memo_obj = {"decision": model, "answer": "", "key_numbers": [], "risks": []} if memo else None
    return SimpleNamespace(final_decision=final, model_decision=model, memo=memo_obj,
                           guardrail_events=[], memo_repairs=repairs, unsupported_numbers=[0] * left,
                           tool_calls=list(tool_calls), stop_reason="model_finished",
                           duration_ms=1000, input_tokens=1, output_tokens=1)


DECISION = Case("X", "decision", "real", "Ship?")
FACTUAL = Case("Y", "factual", "real", "Rates?", {"not_applicable"})


@pytest.mark.parametrize("truth, model, final, outcome, block", [
    ("do_not_ship", "do_not_ship", "do_not_ship", "correct", None),
    ("do_not_ship", "ship", "ship", "wrong_call", None),
    ("ship", "inconclusive", "inconclusive", "safe_miss", None),
    ("no_call", "ship", "blocked", "correct", "needed"),
    ("no_call", "inconclusive", "inconclusive", "correct", None),
    ("no_call", "ship", "ship", "wrong_call", None),
    ("no_effect", "do_not_ship", "do_not_ship", "correct", None),
    ("no_effect", "inconclusive", "inconclusive", "correct", None),
    ("ship", "ship", "blocked", "safe_miss", "unnecessary"),
    ("do_not_ship", "ship", "blocked", "safe_miss", "caught_wrong"),
    ("ship", None, "error", "error", None),
])
def test_decision_outcomes(truth, model, final, outcome, block):
    r = score(DECISION, truth, run(model, final, memo=final != "error"))
    assert (r["outcome"], r["block"]) == (outcome, block)


def test_factual_question_with_a_verdict_is_a_wrong_call():
    r = score(FACTUAL, "do_not_ship", run("do_not_ship", "do_not_ship"))
    assert r["outcome"] == "wrong_call" and not r["model_correct"]


def test_sql_rejections_are_counted():
    calls = [{"name": "run_sql", "arguments": {}, "result": {"error": "query rejected: x"}},
             {"name": "run_sql", "arguments": {}, "result": {"rows": []}}]
    r = score(FACTUAL, "do_not_ship", run("not_applicable", "not_applicable", tool_calls=calls))
    assert (r["sql_calls"], r["sql_rejected"], r["tool_errors"]) == (2, 1, 1)


def memo(answer, keys=()):
    return {"decision": "not_applicable", "answer": answer, "risks": [],
            "key_numbers": [{"source_tool": "t", "field": "f", "value": v} for v in keys]}


@pytest.mark.parametrize("answer, keys, expected, ok", [
    ("19.02% vs 18.20%", (), [19.0201, 18.2000], True),
    ("about 19% vs 18%", (), [19.0201, 18.2000], True),        # rounding is fine
    ("19.1% vs 18.2%", (), [19.0201, 18.2000], False),         # 19.1 is not a rounding of 19.02
    ("44,700 and 45,489 players", (), [44700, 45489], True),   # thousands separators
    ("a drop of 0.82 pp", (), [-0.8201], True),                # sign carried in words
    ("p is 0", (), [0.00155], False),                          # 0 is not a rounding of 0.00155
    ("see table", (0.00155,), [0.00155], True),                # key numbers count
    ("only one: 19.02", (), [19.0201, 18.2], False),           # all expected numbers needed
    ("p = 3.41e-22", (), [3.4123e-22], True),                  # scientific notation
])
def test_numbers_present(answer, keys, expected, ok):
    assert numbers_present(memo(answer, keys), expected) is ok


def test_case_list_is_well_formed():
    ids = [c.id for c in CASES]
    assert len(ids) == 30 and len(set(ids)) == 30
    assert {c.category for c in CASES} == {"decision", "factual", "probe"}
    assert all(c.numbers is not None for c in CASES if c.category == "factual")


def test_summary_counts_a_missed_block_and_consistency():
    from liveops_evals.summary import markdown, metrics
    rows = [score(DECISION, "no_call", run("ship", "ship")),        # bad data, call got through
            score(DECISION, "no_call", run("ship", "blocked")),     # bad data, blocked
            score(DECISION, "ship", run("ship", "ship"))]
    rows[2]["id"] = "Z"
    m = metrics(rows)
    assert m["missed_blocks"] == 1 and m["blocks"] == {"needed": 1}
    assert m["wrong_calls_reaching_user"] == 1
    # case X ran twice with different final decisions: not consistent; Z ran once.
    assert (m["consistent_cases"], m["cases"]) == (1, 2)
    assert "| Calls on unsupportable data that got through (missed blocks) | 1 |" in markdown(rows, "t")
