"""Guardrails, enforced in code. None of these depend on the model obeying a prompt.

Three groups:
1. SQL:      what run_sql may execute.
2. Numbers:  every number in the memo must come from a tool output.
3. Decision: when the agent is NOT allowed to call a result (ship / do_not_ship).
"""
import re
import sqlite3
import time
from dataclasses import dataclass
from decimal import Decimal

from liveops_ab import achieved_power, srm_check, two_proportion_ztest

# ======================================================================
# 1. SQL
# ======================================================================

SQL_TIME_BUDGET_S = 2.0

# The only things a query may do: SELECT, read columns, call functions
# (COUNT, AVG, ...). Everything else (PRAGMA, ATTACH, writes, recursive
# CTEs...) is denied by SQLite itself while it compiles the query.
_ALLOWED_SQL_ACTIONS = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION}

# sum_gamerounds may be summarised per arm (AVG/SUM/...), never used to
# filter, group or sort players: that would be segmenting by a post-treatment
# variable. Rule: strip every aggregate(sum_gamerounds); if the column is
# still mentioned anywhere, reject the query.
_AGGREGATE_OF_ROUNDS = re.compile(r"\b(avg|sum|min|max|count|total)\s*\(\s*sum_gamerounds\s*\)", re.I)


def _authorizer(action, arg1, arg2, db_name, trigger_name):
    return sqlite3.SQLITE_OK if action in _ALLOWED_SQL_ACTIONS else sqlite3.SQLITE_DENY


def install_read_only_authorizer(conn):
    """Second lock on top of mode=ro: SQLite refuses any non-read action."""
    conn.set_authorizer(_authorizer)


def check_sql(query):
    """Return None if the query is allowed, else the reason it is rejected."""
    if not isinstance(query, str) or not query.strip():
        return "query must be a non-empty string"
    text = query.strip().rstrip(";").strip()
    if ";" in text:
        return "only one statement is allowed"
    if "--" in text or "/*" in text:
        return "SQL comments are not allowed"
    if not re.match(r"(select|with)\b", text, re.I):
        return "only SELECT queries are allowed"
    if "sum_gamerounds" in _AGGREGATE_OF_ROUNDS.sub("", text).lower():
        return ("sum_gamerounds is post-treatment: it may only be aggregated "
                "(e.g. AVG(sum_gamerounds)), not used to filter, group or sort")
    return None


def run_with_time_budget(conn, query, max_rows, budget_s=SQL_TIME_BUDGET_S):
    """Execute and fetch up to max_rows, aborting if it takes longer than budget_s."""
    deadline = time.monotonic() + budget_s
    # SQLite calls the handler every 10,000 steps; returning True aborts the
    # query with sqlite3.OperationalError("interrupted").
    conn.set_progress_handler(lambda: time.monotonic() > deadline, 10_000)
    try:
        cursor = conn.execute(query)
        columns = [d[0] for d in cursor.description or []]
        rows = cursor.fetchmany(max_rows)
        return columns, rows
    finally:
        conn.set_progress_handler(None, 0)


# ======================================================================
# 2. Numbers
# ======================================================================

# Numbers that legitimately appear in prose without coming from a tool:
# "day 1", "day 7", "gate 30", "gate 40". Known gap: a made-up 7 would pass.
TEXT_NUMBER_ALLOWLIST = {1.0, 7.0, 30.0, 40.0}

# A number not glued to a word or a dot before it, so the 7 in "retention_7"
# and the 40 in "gate_40" are not picked up.
# Includes scientific notation: "3.41e-22" is one number, not 3.41 and 22
# (a live eval run showed the split version blocking correct memos).
_NUMBER_IN_TEXT = re.compile(r"(?<![\w.])[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")
# A comma between digits followed by exactly three digits is a thousands separator.
_THOUSANDS_SEPARATOR = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")


def _numbers_in(obj):
    """All numbers inside a tool result (nested dicts/lists). Booleans excluded."""
    if isinstance(obj, bool):
        return []
    if isinstance(obj, (int, float)):
        return [float(obj)]
    if isinstance(obj, dict):
        return [n for value in obj.values() for n in _numbers_in(value)]
    if isinstance(obj, list):
        return [n for value in obj for n in _numbers_in(value)]
    return []


def _decimals(written):
    """How many decimals the writer used: '0.82' -> 2, '97' -> 0."""
    return max(0, -Decimal(str(written)).as_tuple().exponent)


def _is_rounding_of(written, true_value, decimals):
    """True if `written` is `true_value` rounded to `decimals` places
    (so 96.6 and 97 both count as coming from 96.63; 96.7 does not).
    Strict `<`: a value exactly half a unit away (0.05 vs a written 0) is
    ambiguous, so it does not count. (A live run hit exactly this case.)"""
    return abs(true_value - written) < 0.5 * 10 ** -decimals


def _text_number_supported(written_text, sources):
    """Prose: rounding allowed, sign ignored (it is carried in words)."""
    written = abs(float(written_text))
    decimals = _decimals(written_text)
    return any(_is_rounding_of(written, abs(value), decimals) for value in sources)


_ROW_CELL = re.compile(r"rows\[(\d+)\]\[(\d+)\]")


def _field_values(result, field):
    """Values of `field` in one tool result: a plain key (compare_arms'
    "p_value"), a run_sql column name, or a run_sql cell like "rows[0][1]"."""
    if field in result and not isinstance(result[field], (dict, list)):
        return [result[field]]
    cell = _ROW_CELL.fullmatch(field)
    if cell and "rows" in result:
        row, column = int(cell.group(1)), int(cell.group(2))
        rows = result["rows"]
        return [rows[row][column]] if row < len(rows) and column < len(rows[row]) else []
    if field in result.get("columns", []):
        index = result["columns"].index(field)
        return [row[index] for row in result.get("rows", [])]
    return []


def _key_number_supported(item, tool_calls):
    """True if some call of item's source_tool returned exactly item's value
    in item's field. Exact: key numbers are copies, so no rounding, sign
    included. Booleans never match (True is not the number 1)."""
    for call in tool_calls:
        if call["name"] != item["source_tool"] or not isinstance(call["result"], dict):
            continue
        for value in _field_values(call["result"], item["field"]):
            if (isinstance(value, (int, float)) and not isinstance(value, bool)
                    and abs(value - item["value"]) < 1e-9):
                return True
    return False


def _is_flag(item, tool_calls):
    """Is the cited field a true/false flag in the cited tool's output?
    (Live evals: the model often cites srm_detected / adequately_powered as 0 or 1.)"""
    return any(call["name"] == item["source_tool"] and isinstance(call["result"], dict)
               and isinstance(call["result"].get(item["field"]), bool)
               for call in tool_calls)


def _context(text, start, end, width=40):
    """The words around a number, so the model can find what to fix."""
    left = max(0, start - width)
    return ("..." if left else "") + text[left:end + width].strip() + ("..." if end + width < len(text) else "")


def find_unsupported_numbers(memo, tool_calls):
    """List every number in the memo that no tool output supports.

    - key_numbers: the cited tool must have returned EXACTLY this value in
      the cited field (sign included).
    - answer / risks text: each number must match SOME tool output. Sign is
      ignored, because prose carries it in words ("fell by 0.82 pp").
    """
    problems = []
    all_values = [n for call in tool_calls for n in _numbers_in(call["result"])]

    for item in memo["key_numbers"]:
        if _is_flag(item, tool_calls):
            problems.append(f"key number {item['source_tool']}.{item['field']}: that field is "
                            f"true/false, not a number. Remove it from key_numbers.")
        elif not _key_number_supported(item, tool_calls):
            problems.append(f"key number {item['source_tool']}.{item['field']} = {item['value']}: "
                            f"no {item['source_tool']} result has that value in field "
                            f"\"{item['field']}\"")

    texts = [memo["answer"], *memo["risks"]]
    for text in texts:
        text = _THOUSANDS_SEPARATOR.sub("", text)  # "44,700" -> "44700"
        for match in _NUMBER_IN_TEXT.finditer(text):
            number = match.group().lstrip("+")
            if abs(float(number)) in TEXT_NUMBER_ALLOWLIST:
                continue
            if not _text_number_supported(number, all_values):
                problems.append(f'number {number} in "{_context(text, match.start(), match.end())}" '
                                f"is not in any tool output")
    return problems


# ======================================================================
# 3. Decision policy
# ======================================================================

MIN_POWER = 0.80
CALLS_A_RESULT = {"ship", "do_not_ship"}


@dataclass(frozen=True)
class GuardrailEvent:
    rule: str
    detail: str


def data_validity_events(exp):
    """Problems with the experiment itself, recomputed by code from the
    database (not read from the transcript, so the model cannot skip them)."""
    from .tools import _arm_counts, _arm_sizes  # local import avoids a circular import

    events = []
    n_a, n_b = _arm_sizes(exp)
    srm = srm_check(n_a, n_b, expected_share_a=exp.expected_share_control)
    if srm.srm_detected:
        events.append(GuardrailEvent(
            "srm", f"sample ratio mismatch: {n_a} vs {n_b} users, p={srm.p_value:.3g}"))

    planned = exp.planned_users_per_arm
    if planned is not None and min(n_a, n_b) < planned:
        events.append(GuardrailEvent(
            "stopped_early", f"planned {planned} users per arm, smallest arm has {min(n_a, n_b)}"))

    x_a, n_a, x_b, n_b = _arm_counts(exp, exp.primary_metric)
    power = achieved_power(n_a, n_b, x_a / n_a, exp.target_mde_abs, alpha=exp.alpha)
    if power < MIN_POWER:
        events.append(GuardrailEvent(
            "underpowered", f"power {power:.0%} on {exp.primary_metric} for a "
                            f"{exp.target_mde_abs:.1%} effect (need {MIN_POWER:.0%})"))
    return events


def contradicts_evidence(exp, decision):
    """Does the decision disagree with the primary-metric result? Recomputed from the DB.

    - "ship" needs a significant INCREASE in the primary metric.
    - "do_not_ship" is wrong if the primary metric significantly increased.
    (A live eval run had the model say "ship" while its own memo described a
    significant decrease.) Returns a GuardrailEvent or None."""
    from .tools import _arm_counts  # local import avoids a circular import

    x_a, n_a, x_b, n_b = _arm_counts(exp, exp.primary_metric)
    test = two_proportion_ztest(x_a, n_a, x_b, n_b, alpha=exp.alpha)
    significant_increase = test.p_value < exp.alpha and test.diff > 0
    observed = f"{exp.primary_metric} changed {100 * test.diff:+.2f} pp, p={test.p_value:.3g}"
    if decision == "ship" and not significant_increase:
        return GuardrailEvent("contradicts_evidence",
                              f"ship requires a significant increase; {observed}")
    if decision == "do_not_ship" and significant_increase:
        return GuardrailEvent("contradicts_evidence",
                              f"do_not_ship despite a significant increase; {observed}")
    return None


def missing_evidence(exp, tool_calls):
    """Tool calls a ship/do_not_ship decision must be based on."""
    required = [("sample_ratio_check", None),
                ("compare_arms", exp.primary_metric),
                ("power_check", exp.primary_metric)]
    done = {(c["name"], c["arguments"].get("metric") if isinstance(c["arguments"], dict) else None)
            for c in tool_calls if "error" not in c["result"]}
    return [f"{name}({metric or ''})" for name, metric in required if (name, metric) not in done]


def apply_decision_policy(exp, memo, tool_calls, unsupported_numbers):
    """Return (final_decision, events).

    final_decision is the model's decision, unless a guardrail blocks it:
    - "error"   : no valid memo was produced
    - "blocked" : unsupported numbers in the memo, or a ship/do_not_ship
                  call made despite SRM / early stopping / low power /
                  missing evidence, or one that contradicts the primary
                  metric's result
    Validity problems are still reported (as events) on answers that do not
    call a result, so a reader of any answer sees that the data is suspect.
    """
    if memo is None:
        return "error", []
    events = data_validity_events(exp)
    if unsupported_numbers:
        events.append(GuardrailEvent("unsupported_numbers", "; ".join(unsupported_numbers)))
        return "blocked", events
    if memo["decision"] in CALLS_A_RESULT:
        # So far `events` holds only data-validity problems. Compare the decision
        # with the result only when there are none: on a broken split (e.g. the
        # skewed eval variant) the "increase" is an artefact, not evidence.
        data_is_trustworthy = not events
        missing = missing_evidence(exp, tool_calls)
        if missing:
            events.append(GuardrailEvent("missing_evidence", "not called: " + ", ".join(missing)))
        contradiction = contradicts_evidence(exp, memo["decision"]) if data_is_trustworthy else None
        if contradiction:
            events.append(contradiction)
        if events:
            return "blocked", events
    return memo["decision"], events
