"""Aggregate saved traces: latency, tokens, errors, guardrail activity.

Usage: python scripts/trace_report.py [traces_dir]
"""
import json
import sys
from collections import Counter
from pathlib import Path


def percentile(values, q):
    """Nearest-rank percentile: the smallest value with at least q% of values <= it."""
    ordered = sorted(values)
    rank = max(1, -(-len(ordered) * q // 100))  # ceil(n * q / 100), at least 1
    return ordered[int(rank) - 1]


def load_traces(directory):
    return [json.loads(p.read_text()) for p in sorted(Path(directory).glob("*.json"))]


def report(traces):
    n = len(traces)
    if n == 0:
        return "no traces"
    totals = [t["duration_ms"] / 1000 for t in traces]
    llm = [s for t in traces for s in t["spans"] if s["kind"] == "llm"]
    tools = [s for t in traces for s in t["spans"] if s["kind"] == "tool"]
    tool_errors = Counter(s["name"] for s in tools if s["error"])
    blocked = [t for t in traces if t["final_decision"] == "blocked"]
    rules = Counter(e["rule"] for t in blocked for e in t["guardrail_events"])
    overridden = sum(t["final_decision"] != t["model_decision"] for t in traces)

    lines = [
        f"Traces: {n}",
        f"Latency per question (s): p50 {percentile(totals, 50):.1f} | "
        f"p95 {percentile(totals, 95):.1f} | max {max(totals):.1f}",
        f"LLM calls: {len(llm)} ({len(llm) / n:.1f}/question) | "
        f"p50 {percentile([s['duration_ms'] for s in llm], 50) / 1000:.1f}s per call",
        f"Tokens per question: in {sum(s['input_tokens'] for s in llm) / n:.0f} | "
        f"out {sum(s['output_tokens'] for s in llm) / n:.0f}",
        f"Tool calls: {len(tools)} ({len(tools) / n:.1f}/question) | "
        f"errors: {sum(tool_errors.values())} {dict(tool_errors) or ''}",
        f"Hit max_steps: {sum(t['stop_reason'] == 'max_steps' for t in traces)} | "
        f"memo errors: {sum(t['memo'] is None for t in traces)} | "
        f"memo rewrites: {sum(t['memo_repairs'] for t in traces)}",
        f"Final decisions: {dict(Counter(t['final_decision'] for t in traces))}",
        f"Overridden by guardrails: {overridden} | blocked by rule: {dict(rules)}",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    print(report(load_traces(sys.argv[1] if len(sys.argv) > 1 else "traces")))
