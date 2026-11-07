import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "trace_report", Path(__file__).parent.parent / "scripts" / "trace_report.py")
trace_report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trace_report)


def test_percentile_nearest_rank():
    values = list(range(1, 11))          # 1..10
    assert trace_report.percentile(values, 50) == 5
    assert trace_report.percentile(values, 95) == 10
    assert trace_report.percentile([7], 50) == 7


def trace(decision, model_decision, seconds, events=(), tool_error=None, repairs=0):
    return {
        "duration_ms": seconds * 1000, "final_decision": decision, "model_decision": model_decision,
        "guardrail_events": [{"rule": r, "detail": ""} for r in events],
        "stop_reason": "model_finished", "memo": {}, "memo_repairs": repairs,
        "spans": [
            {"kind": "llm", "name": "agent_step_1", "duration_ms": 1000, "input_tokens": 100,
             "output_tokens": 10, "error": None},
            {"kind": "tool", "name": "compare_arms", "duration_ms": 5, "input_tokens": 0,
             "output_tokens": 0, "error": tool_error},
        ],
    }


def test_report():
    traces = [
        trace("do_not_ship", "do_not_ship", 20),
        trace("blocked", "do_not_ship", 30, events=["missing_evidence"], tool_error="bad", repairs=1),
    ]
    text = trace_report.report(traces)
    assert "Traces: 2" in text
    assert "p50 20.0 | p95 30.0" in text
    assert "errors: 1 {'compare_arms': 1}" in text
    assert "memo rewrites: 1" in text
    assert "Overridden by guardrails: 1 | blocked by rule: {'missing_evidence': 1}" in text
