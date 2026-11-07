import json
from dataclasses import asdict

import pytest

from liveops_agent import ScriptedClient, run_agent
from liveops_agent.llm import parse_ollama_response, scripted_text, scripted_tool_call
from liveops_agent.tools import load_experiment
from liveops_agent.trace import Tracer, summarize


class FakeClock:
    """Each read advances time by exactly 0.1 s, so durations are predictable."""
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        self.t += 0.1
        return self.t


def test_span_records_timing_output_and_tokens():
    tracer = Tracer(clock=FakeClock())          # start = 0.1
    with tracer.span("llm", "step", {"q": 1}) as span:   # enter: 0.2
        span["output"] = "hi"
        span["input_tokens"] = 7                # exit: 0.3
    (s,) = tracer.spans
    assert (s.kind, s.name, s.input, s.output, s.input_tokens) == ("llm", "step", {"q": 1}, "hi", 7)
    assert (s.start_ms, s.duration_ms) == (100.0, 100.0)


def test_span_is_recorded_even_when_the_block_raises():
    tracer = Tracer(clock=FakeClock())
    with pytest.raises(ValueError):
        with tracer.span("tool", "boom", {}):
            raise ValueError("bad")
    assert tracer.spans[0].error == "ValueError: bad"


def test_summarize():
    tracer = Tracer(clock=FakeClock())
    for name in ("a", "b"):
        with tracer.span("llm", name, {}) as span:
            span["input_tokens"], span["output_tokens"] = 10, 2
    with tracer.span("tool", "t", {}) as span:
        span["error"] = "x"
    totals = summarize(tracer.spans)
    assert totals["llm"] == {"count": 2, "duration_ms": 200.0, "errors": 0,
                             "input_tokens": 20, "output_tokens": 4}
    assert totals["tool"]["errors"] == 1


MEMO = {"decision": "inconclusive", "answer": "Unclear.", "key_numbers": [], "risks": []}
INVENTED = {**MEMO, "answer": "Fell by 3.7 pp."}


def test_agent_trace_covers_every_step(db_path):
    exp = load_experiment(db_path)
    client = ScriptedClient([
        scripted_tool_call("sample_ratio_check", tokens=(100, 10)),
        scripted_tool_call("compare_arms", {"metric": "sum_gamerounds"}, tokens=(200, 12)),
        scripted_text("done", tokens=(300, 8)),
        scripted_text(json.dumps(INVENTED), tokens=(400, 50)),
        scripted_text(json.dumps(MEMO), tokens=(500, 40)),
    ])
    run = run_agent("q", exp, client, tracer=Tracer(clock=FakeClock()))

    assert [(s.kind, s.name) for s in run.spans] == [
        ("llm", "agent_step_1"), ("tool", "sample_ratio_check"),
        ("llm", "agent_step_2"), ("tool", "compare_arms"),
        ("llm", "agent_step_3"),
        ("llm", "memo"), ("guardrail", "number_check"),
        ("llm", "memo_repair_1"), ("guardrail", "number_check"),
        ("guardrail", "decision_policy"),
    ]
    by_name = {s.name: s for s in run.spans}
    # The first call sees system + user; the second sees only the new tool result.
    assert [m["role"] for m in by_name["agent_step_1"].input["new_messages"]] == ["system", "user"]
    assert [m["role"] for m in by_name["agent_step_2"].input["new_messages"]] == ["tool"]
    assert by_name["agent_step_1"].input["tools_offered"][0] == "experiment_overview"
    assert by_name["memo"].input["json_schema"] and not by_name["memo"].input["tools_offered"]
    # The bad tool call shows up as an error span; the good one does not.
    assert "unknown metric" in by_name["compare_arms"].error
    assert by_name["sample_ratio_check"].error is None
    # Guardrail spans record what they decided.
    assert run.spans[6].output == ['number 3.7 in "Fell by 3.7 pp." is not in any tool output']
    assert run.spans[8].output == []
    assert by_name["decision_policy"].output["final_decision"] == "inconclusive"
    # Span tokens add up to the run totals.
    assert run.span_totals["llm"]["input_tokens"] == run.input_tokens == 1500
    assert run.span_totals["llm"]["count"] == run.llm_calls == 5
    assert run.span_totals["tool"]["errors"] == 1
    # Spans are in time order and the run lasts at least as long as its last span.
    starts = [s.start_ms for s in run.spans]
    assert starts == sorted(starts)
    assert run.duration_ms >= run.spans[-1].start_ms + run.spans[-1].duration_ms
    # The whole run can be saved as JSON.
    json.dumps(asdict(run))


def test_ollama_server_timings_are_converted_to_ms():
    r = parse_ollama_response({"message": {"role": "assistant", "content": "x"},
                               "total_duration": 2_500_000_000, "load_duration": 1_000_000})
    assert r.server_timings_ms == {"total_duration": 2500.0, "load_duration": 1.0}
