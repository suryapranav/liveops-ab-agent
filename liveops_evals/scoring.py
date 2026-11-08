"""Scoring one agent run against its case.

Outcome of the FINAL decision (after guardrails):
  correct     in the acceptable set
  wrong_call  "ship" or "do_not_ship" reached the user but was not acceptable
  safe_miss   wrong, but no call reached the user (blocked / inconclusive / n.a.)
  error       no valid memo

Every block is also classified:
  needed          the data could not support a decision (reference: no_call)
  caught_wrong    the data was fine but the model's decision was wrong
  unnecessary     the model's decision was right and was blocked anyway
"""
import re
from decimal import Decimal

from .reference import ACCEPTABLE

CALLS = {"ship", "do_not_ship"}
_NUMBER = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")
_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")


def acceptable_decisions(case, truth):
    return ACCEPTABLE[truth] if case.expected == "reference" else set(case.expected)


def _written_numbers(memo):
    """(text, value) for every number the memo shows, key numbers included."""
    texts = [memo["answer"], *memo["risks"]] + [repr(float(k["value"])) for k in memo["key_numbers"]]
    found = []
    for text in texts:
        for m in _NUMBER.findall(_THOUSANDS.sub("", text)):
            found.append((m, float(m)))
    return found


def _shows(expected, written_text, written):
    """Does a written number show `expected`, possibly rounded? Sign ignored.
    0 never counts as a rounding of a non-zero value."""
    if written == 0 and expected != 0:
        return False
    decimals = max(0, -Decimal(written_text).as_tuple().exponent)
    return abs(abs(expected) - abs(written)) <= 0.5 * 10 ** -decimals + 1e-12


def numbers_present(memo, expected_numbers):
    written = _written_numbers(memo)
    return all(any(_shows(e, t, w) for t, w in written) for e in expected_numbers)


def score(case, truth, run, expected_numbers=None):
    acceptable = acceptable_decisions(case, truth)
    final, proposed = run.final_decision, run.model_decision

    if final == "error" or run.memo is None:
        outcome = "error"
    elif final in acceptable:
        outcome = "correct"
    elif final in CALLS:
        outcome = "wrong_call"
    else:
        outcome = "safe_miss"

    block = None
    if final == "blocked":
        if truth == "no_call":
            block = "needed"
        elif proposed not in acceptable:
            block = "caught_wrong"
        else:
            block = "unnecessary"

    numbers_ok = None
    if expected_numbers is not None and run.memo is not None:
        numbers_ok = numbers_present(run.memo, expected_numbers)

    sql_calls = [c for c in run.tool_calls if c["name"] == "run_sql"]
    return {
        "id": case.id, "category": case.category, "variant": case.variant,
        "question": case.question, "truth": truth, "acceptable": sorted(acceptable),
        "model_decision": proposed, "final_decision": final,
        "model_correct": proposed in acceptable,
        "outcome": outcome, "block": block,
        "guardrail_rules": [e["rule"] for e in run.guardrail_events],
        "numbers_ok": numbers_ok,
        "expected_numbers": expected_numbers,
        "memo_repairs": run.memo_repairs,
        "unsupported_numbers_left": len(run.unsupported_numbers),
        "tool_calls": [c["name"] for c in run.tool_calls],
        "tool_errors": sum("error" in c["result"] for c in run.tool_calls),
        "sql_calls": len(sql_calls),
        "sql_rejected": sum("query rejected" in c["result"].get("error", "") for c in sql_calls),
        "stop_reason": run.stop_reason,
        "duration_s": round(run.duration_ms / 1000, 2),
        "input_tokens": run.input_tokens, "output_tokens": run.output_tokens,
    }
