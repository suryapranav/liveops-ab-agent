"""Observability: every LLM call, tool call and guardrail check becomes a span.

A span records what went in, what came out, how long it took, tokens (for
LLM calls) and any error. One question = one trace = an ordered list of
spans, saved as JSON. scripts/trace_report.py aggregates many traces.

The clock is injectable so tests can use a fake clock and get exact,
repeatable durations.
"""
import time
from contextlib import contextmanager
from dataclasses import dataclass


@dataclass
class Span:
    kind: str              # "llm" | "tool" | "guardrail"
    name: str              # e.g. "agent_step_2", "compare_arms", "decision_policy"
    start_ms: float        # offset from the start of the run
    duration_ms: float
    input: object
    output: object
    error: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0


class Tracer:
    def __init__(self, clock=time.perf_counter):
        self.clock = clock
        self.started = clock()
        self.spans = []

    def _ms_since_start(self, t):
        return round((t - self.started) * 1000, 1)

    @contextmanager
    def span(self, kind, name, input):
        """Time a block of code and record it as a span.

        The caller gets a dict to fill in (output, error, tokens). The span
        is recorded even if the block raises; the exception is re-raised."""
        record = {"output": None, "error": None, "input_tokens": 0, "output_tokens": 0}
        start = self.clock()
        try:
            yield record
        except Exception as e:
            record["error"] = f"{type(e).__name__}: {e}"
            raise
        finally:
            end = self.clock()
            self.spans.append(Span(
                kind=kind, name=name,
                start_ms=self._ms_since_start(start),
                duration_ms=round((end - start) * 1000, 1),
                input=input, **record,
            ))

    def elapsed_ms(self):
        return self._ms_since_start(self.clock())


def summarize(spans):
    """Totals per span kind: how many, how long, tokens, errors."""
    totals = {}
    for s in spans:
        t = totals.setdefault(s.kind, {"count": 0, "duration_ms": 0.0, "errors": 0,
                                       "input_tokens": 0, "output_tokens": 0})
        t["count"] += 1
        t["duration_ms"] = round(t["duration_ms"] + s.duration_ms, 1)
        t["errors"] += s.error is not None
        t["input_tokens"] += s.input_tokens
        t["output_tokens"] += s.output_tokens
    return totals
