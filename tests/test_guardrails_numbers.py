from liveops_agent.guardrails import find_unsupported_numbers

CALLS = [
    {"name": "compare_arms", "arguments": {"metric": "retention_7"},
     "result": {"control_rate_pct": 19.02, "treatment_rate_pct": 18.2, "diff_pp": -0.82,
                "p_value": 0.00155, "alpha": 0.05, "confidence_level_pct": 95.0,
                "significant": True}},
    {"name": "power_check", "arguments": {"metric": "retention_7"},
     "result": {"power_at_that_effect_pct": 96.63, "power_required_pct": 80.0}},
]


def memo(answer="", key_numbers=(), risks=()):
    return {"decision": "do_not_ship", "answer": answer,
            "key_numbers": list(key_numbers), "risks": list(risks)}


def test_clean_memo_passes():
    m = memo("7-day retention fell from 19.02% to 18.20% (-0.82 pp, p = 0.00155), "
             "with 96.63% power at the 95% level.",
             [{"source_tool": "compare_arms", "field": "diff_pp", "value": -0.82}])
    assert find_unsupported_numbers(m, CALLS) == []


def test_invented_number_in_text_is_caught():
    problems = find_unsupported_numbers(memo("Retention fell by 1.5 pp."), CALLS)
    assert problems == ['number 1.5 in "Retention fell by 1.5 pp." is not in any tool output']


def test_key_number_must_match_the_cited_tool():
    # 0.00155 exists, but in compare_arms, not power_check.
    m = memo(key_numbers=[{"source_tool": "power_check", "field": "p_value", "value": 0.00155}])
    assert "no power_check result has that value" in find_unsupported_numbers(m, CALLS)[0]


def test_key_number_sign_matters():
    m = memo(key_numbers=[{"source_tool": "compare_arms", "field": "diff_pp", "value": 0.82}])
    assert len(find_unsupported_numbers(m, CALLS)) == 1


def test_text_sign_is_ignored():
    assert find_unsupported_numbers(memo("a drop of 0.82 percentage points"), CALLS) == []


def test_rounding_is_allowed_but_not_rounding_errors():
    assert find_unsupported_numbers(memo("power was 96.6%, about 97%"), CALLS) == []
    assert len(find_unsupported_numbers(memo("power was 96.7%"), CALLS)) == 1


def test_identifiers_and_allowlist_are_not_numbers():
    text = "gate_40 vs gate_30 on retention_7: day 1 and day 7 retention, gate 40"
    assert find_unsupported_numbers(memo(text), CALLS) == []


def test_risks_are_checked_too():
    assert len(find_unsupported_numbers(memo(risks=["Could cost 3% of revenue"]), CALLS)) == 1


def test_booleans_are_not_numbers():
    # significant=True must not let a "1" claim through via True == 1.
    m = memo(key_numbers=[{"source_tool": "compare_arms", "field": "significant", "value": 1}])
    assert len(find_unsupported_numbers(m, CALLS)) == 1


def test_unit_conversion_is_not_allowed():
    # Live run: -0.82 pp written as "82 basis points". Correct arithmetic, but
    # arithmetic done by the model, which is what this guardrail forbids.
    problems = find_unsupported_numbers(memo("82 basis points lower retention"), CALLS)
    assert len(problems) == 1 and "82 basis points" in problems[0]


def test_key_numbers_must_be_exact_copies():
    m = memo(key_numbers=[{"source_tool": "power_check", "field": "power_at_that_effect_pct", "value": 96.6}])
    assert len(find_unsupported_numbers(m, CALLS)) == 1


def test_regression_zero_is_not_alpha_rounded():
    # Live run: key number "sum_gamerounds = 0" slipped through because 0.05
    # (alpha) is half a unit away from 0 at one decimal place.
    overview = [{"name": "experiment_overview", "arguments": {}, "result": {"alpha": 0.05}}]
    m = memo("We use 0.0 as the cut-off.",
             [{"source_tool": "experiment_overview", "field": "sum_gamerounds", "value": 0}])
    assert len(find_unsupported_numbers(m, overview)) == 2


def test_context_points_at_the_problem():
    text = "x" * 100 + " fell by 9.9 pp " + "y" * 100
    problem = find_unsupported_numbers(memo(text), CALLS)[0]
    assert "fell by 9.9 pp" in problem and problem.count("...") == 2


SRM_CALL = {"name": "sample_ratio_check", "arguments": {},
            "result": {"p_value": 0.00861, "srm_detected": False, "chi2": 6.9}}


def test_regression_right_number_wrong_field():
    # Live trace: the rewrite kept the field "srm_detected" and swapped in 0.00861,
    # a real sample_ratio_check value, but from a different field. Must fail.
    m = memo(key_numbers=[{"source_tool": "sample_ratio_check", "field": "srm_detected", "value": 0.00861}])
    assert len(find_unsupported_numbers(m, [SRM_CALL])) == 1
    ok = memo(key_numbers=[{"source_tool": "sample_ratio_check", "field": "p_value", "value": 0.00861}])
    assert find_unsupported_numbers(ok, [SRM_CALL]) == []


def test_field_must_exist():
    m = memo(key_numbers=[{"source_tool": "compare_arms", "field": "made_up", "value": -0.82}])
    assert len(find_unsupported_numbers(m, CALLS)) == 1


def test_any_call_of_the_tool_counts():
    # compare_arms is usually called once per metric; either call can back the number.
    other = {"name": "compare_arms", "arguments": {"metric": "retention_1"}, "result": {"p_value": 0.0744}}
    m = memo(key_numbers=[{"source_tool": "compare_arms", "field": "p_value", "value": 0.0744}])
    assert find_unsupported_numbers(m, CALLS + [other]) == []


def test_sql_columns_are_fields():
    sql = {"name": "run_sql", "arguments": {"query": "..."},
           "result": {"columns": ["version", "avg_rounds"], "rows": [["gate_30", 52.46], ["gate_40", 51.3]],
                      "truncated": False}}
    ok = memo(key_numbers=[{"source_tool": "run_sql", "field": "avg_rounds", "value": 51.3}])
    assert find_unsupported_numbers(ok, [sql]) == []
    bad = memo(key_numbers=[{"source_tool": "run_sql", "field": "version", "value": 51.3}])
    assert len(find_unsupported_numbers(bad, [sql])) == 1


def test_thousands_separators():
    calls = [{"name": "sample_ratio_check", "arguments": {},
              "result": {"control_users": 44700, "treatment_users": 45489}}]
    assert find_unsupported_numbers(memo("44,700 vs 45,489 players"), calls) == []
    assert len(find_unsupported_numbers(memo("44,701 players"), calls)) == 1
    # a list "1,2,3" is not one number
    assert len(find_unsupported_numbers(memo("arms 44700,12,13"), calls)) == 2



def test_regression_scientific_notation_is_one_number():
    # Live eval (D09, D11, P03): "3.41e-22" was split into 3.41 and 22 and flagged.
    srm = [{"name": "sample_ratio_check", "arguments": {}, "result": {"p_value": 3.41e-22}}]
    assert find_unsupported_numbers(memo("SRM p-value of 3.41e-22."), srm) == []
    assert find_unsupported_numbers(memo("SRM p-value of 3.41E-22."), srm) == []
    assert len(find_unsupported_numbers(memo("SRM p-value of 3.5e-22."), srm)) == 1


def test_regression_sql_cell_reference():
    # Live eval (F07): the model cited run_sql values as rows[0][1].
    sql = [{"name": "run_sql", "arguments": {"query": "..."},
            "result": {"columns": ["version", "avg_rounds"],
                       "rows": [["gate_30", 52.45626398210291], ["gate_40", 51.29877552814966]],
                       "truncated": False}}]
    ok = memo(key_numbers=[{"source_tool": "run_sql", "field": "rows[0][1]", "value": 52.45626398210291},
                           {"source_tool": "run_sql", "field": "rows[1][1]", "value": 51.29877552814966}])
    assert find_unsupported_numbers(ok, sql) == []
    wrong_cell = memo(key_numbers=[{"source_tool": "run_sql", "field": "rows[1][1]", "value": 52.45626398210291}])
    out_of_range = memo(key_numbers=[{"source_tool": "run_sql", "field": "rows[5][1]", "value": 52.45626398210291}])
    assert len(find_unsupported_numbers(wrong_cell, sql)) == 1
    assert len(find_unsupported_numbers(out_of_range, sql)) == 1


def test_flags_get_a_specific_message():
    # Live eval: srm_detected / adequately_powered cited as 0 or 1 (33 times in 90 runs).
    m = memo(key_numbers=[{"source_tool": "sample_ratio_check", "field": "srm_detected", "value": 0}])
    (problem,) = find_unsupported_numbers(m, [SRM_CALL])
    assert "true/false, not a number" in problem
