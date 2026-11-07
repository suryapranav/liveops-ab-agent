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
             [{"label": "diff", "value": -0.82, "source_tool": "compare_arms"}])
    assert find_unsupported_numbers(m, CALLS) == []


def test_invented_number_in_text_is_caught():
    problems = find_unsupported_numbers(memo("Retention fell by 1.5 pp."), CALLS)
    assert problems == ['number 1.5 in "Retention fell by 1.5 pp." is not in any tool output']


def test_key_number_must_match_the_cited_tool():
    # 0.00155 exists, but in compare_arms, not power_check.
    m = memo(key_numbers=[{"label": "p", "value": 0.00155, "source_tool": "power_check"}])
    assert "not found in output of power_check" in find_unsupported_numbers(m, CALLS)[0]


def test_key_number_sign_matters():
    m = memo(key_numbers=[{"label": "diff", "value": 0.82, "source_tool": "compare_arms"}])
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
    m = memo(key_numbers=[{"label": "x", "value": 1, "source_tool": "compare_arms"}])
    assert len(find_unsupported_numbers(m, CALLS)) == 1


def test_unit_conversion_is_not_allowed():
    # Live run: -0.82 pp written as "82 basis points". Correct arithmetic, but
    # arithmetic done by the model, which is what this guardrail forbids.
    problems = find_unsupported_numbers(memo("82 basis points lower retention"), CALLS)
    assert len(problems) == 1 and "82 basis points" in problems[0]


def test_key_numbers_must_be_exact_copies():
    m = memo(key_numbers=[{"label": "power", "value": 96.6, "source_tool": "power_check"}])
    assert len(find_unsupported_numbers(m, CALLS)) == 1


def test_regression_zero_is_not_alpha_rounded():
    # Live run: key number "sum_gamerounds = 0" slipped through because 0.05
    # (alpha) is half a unit away from 0 at one decimal place.
    overview = [{"name": "experiment_overview", "arguments": {}, "result": {"alpha": 0.05}}]
    m = memo("We use 0.0 as the cut-off.",
             [{"label": "sum_gamerounds", "value": 0, "source_tool": "experiment_overview"}])
    assert len(find_unsupported_numbers(m, overview)) == 2


def test_context_points_at_the_problem():
    text = "x" * 100 + " fell by 9.9 pp " + "y" * 100
    problem = find_unsupported_numbers(memo(text), CALLS)[0]
    assert "fell by 9.9 pp" in problem and problem.count("...") == 2
