import json

import pytest

from liveops_agent import ScriptedClient, render_memo, run_agent
from liveops_agent.llm import parse_ollama_response, scripted_text, scripted_tool_call
from liveops_agent.memo import MemoError, parse_memo
from liveops_agent.tools import load_experiment

GOOD_MEMO = {
    "decision": "inconclusive",
    "answer": "No significant difference.",
    "key_numbers": [{"source_tool": "compare_arms", "field": "diff_pp", "value": -2.0}],
    "risks": ["Underpowered"],
}
NO_NUMBERS_MEMO = {"decision": "inconclusive", "answer": "Unclear.", "key_numbers": [], "risks": []}


@pytest.fixture
def exp(db_path):
    return load_experiment(db_path)


def test_full_loop(exp):
    client = ScriptedClient([
        scripted_tool_call("sample_ratio_check", tokens=(100, 10)),
        scripted_tool_call("compare_arms", {"metric": "retention_7"}, tokens=(200, 12)),
        scripted_text("Not significant.", tokens=(300, 8)),
        scripted_text(json.dumps(GOOD_MEMO), tokens=(400, 50)),
    ])
    run = run_agent("Should we ship gate_40?", exp, client)

    assert [c["name"] for c in run.tool_calls] == ["sample_ratio_check", "compare_arms"]
    assert run.tool_calls[1]["result"]["diff_pp"] == -2.0
    assert run.stop_reason == "model_finished"
    assert run.memo == GOOD_MEMO and run.memo_error is None
    assert run.model_decision == run.final_decision == "inconclusive"
    # 1000 users/arm is underpowered for 1 pp: reported, but an inconclusive answer stands.
    assert [e["rule"] for e in run.guardrail_events] == ["underpowered"]
    assert run.llm_calls == 4
    assert (run.input_tokens, run.output_tokens) == (1000, 80)

    # The second model call must have seen the first tool's result.
    second_request = client.requests[1]["messages"]
    assert second_request[-1]["role"] == "tool"
    assert json.loads(second_request[-1]["content"])["control_users"] == 1000
    # Tools are offered during the loop, but the memo call is schema-constrained instead.
    assert client.requests[0]["tools"] and client.requests[0]["response_format"] is None
    assert client.requests[-1]["tools"] is None and client.requests[-1]["response_format"]


def test_max_steps_stops_a_looping_model(exp):
    looping = [scripted_tool_call("sample_ratio_check") for _ in range(3)]
    client = ScriptedClient(looping + [scripted_text(json.dumps(NO_NUMBERS_MEMO))])
    run = run_agent("q", exp, client, max_steps=3)
    assert run.stop_reason == "max_steps"
    assert len(run.tool_calls) == 3
    assert run.memo == NO_NUMBERS_MEMO  # a memo is still requested


def test_tool_error_is_returned_to_model(exp):
    client = ScriptedClient([
        scripted_tool_call("compare_arms", {"metric": "sum_gamerounds"}),
        scripted_text("done"),
        scripted_text(json.dumps(NO_NUMBERS_MEMO)),
    ])
    run = run_agent("q", exp, client)
    assert "unknown metric" in run.tool_calls[0]["result"]["error"]
    assert "unknown metric" in client.requests[1]["messages"][-1]["content"]


def test_bad_memo_is_recorded_not_raised(exp):
    client = ScriptedClient([scripted_text("done"), scripted_text("not json")])
    run = run_agent("q", exp, client)
    assert run.memo is None and "not valid JSON" in run.memo_error
    assert run.final_decision == "error"


INVENTED = {**NO_NUMBERS_MEMO, "answer": "Retention fell by 3.7 pp."}


def test_invented_number_triggers_one_repair(exp):
    client = ScriptedClient([
        scripted_text("done"),
        scripted_text(json.dumps(INVENTED)),
        scripted_text(json.dumps(NO_NUMBERS_MEMO)),
    ])
    run = run_agent("q", exp, client)
    assert run.memo_repairs == 1 and run.unsupported_numbers == []
    assert run.memo == NO_NUMBERS_MEMO and run.final_decision == "inconclusive"
    assert "3.7" in client.requests[-1]["messages"][-1]["content"]  # the model was told what to fix


def test_repair_that_fails_is_blocked(exp):
    client = ScriptedClient([
        scripted_text("done"),
        scripted_text(json.dumps(INVENTED)),
        scripted_text(json.dumps(INVENTED)),
    ])
    run = run_agent("q", exp, client)
    assert run.memo_repairs == 1 and run.final_decision == "blocked"
    assert run.model_decision == "inconclusive"
    assert "unsupported_numbers" in [e["rule"] for e in run.guardrail_events]


def test_replay_of_live_run_2_is_now_blocked(make_experiment):
    # Live run 2: a factual question, only compare_arms called, memo said do_not_ship.
    exp = make_experiment(target_mde_abs=0.10)  # healthy, so only the evidence rule can fire
    memo = {"decision": "do_not_ship", "answer": "1-day retention is 45.0% vs 45.0%.",
            "key_numbers": [], "risks": []}
    client = ScriptedClient([
        scripted_tool_call("compare_arms", {"metric": "retention_1"}),
        scripted_text("done"),
        scripted_text(json.dumps(memo)),
    ])
    run = run_agent("What is 1-day retention in each arm?", exp, client)
    assert run.model_decision == "do_not_ship" and run.final_decision == "blocked"
    assert [e["rule"] for e in run.guardrail_events] == ["missing_evidence"]


@pytest.mark.parametrize("memo, fragment", [
    ({**GOOD_MEMO, "decision": "yes"}, "decision must be"),
    ({k: v for k, v in GOOD_MEMO.items() if k != "risks"}, "missing fields"),
    ({**GOOD_MEMO, "key_numbers": [{"field": "x", "value": "45%", "source_tool": "t"}]}, "not a number"),
    ({**GOOD_MEMO, "key_numbers": [{"label": "x", "value": 1.0, "source_tool": "t"}]}, "bad key_numbers"),
    ([], "JSON object"),
])
def test_parse_memo_rejects(memo, fragment):
    with pytest.raises(MemoError, match=fragment):
        parse_memo(json.dumps(memo))


def test_render_memo():
    text = render_memo("Ship?", GOOD_MEMO)
    assert "`inconclusive`" in text and "| `compare_arms` | `diff_pp` | -2.0 |" in text
    blocked = render_memo("Ship?", GOOD_MEMO, "blocked", [{"rule": "srm", "detail": "p=0.0001"}])
    assert "overridden by guardrails" in blocked and "`srm`: p=0.0001" in blocked


def test_parse_ollama_response():
    data = {
        "message": {"role": "assistant", "content": "",
                    "tool_calls": [{"function": {"name": "compare_arms",
                                                 "arguments": {"metric": "retention_1"}}},
                                   {"function": {"name": "power_check",
                                                 "arguments": '{"metric": "retention_7"}'}}]},
        "prompt_eval_count": 321, "eval_count": 12,
    }
    r = parse_ollama_response(data)
    assert [(c.name, c.arguments) for c in r.tool_calls] == [
        ("compare_arms", {"metric": "retention_1"}), ("power_check", {"metric": "retention_7"})]
    assert (r.input_tokens, r.output_tokens) == (321, 12)
