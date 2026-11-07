"""The agent loop.

1. Send the question plus tool descriptions to the model.
2. If the model asks for tools, run them and send the results back.
3. Repeat until the model answers without calling a tool, or until
   max_steps (a hard cap, so a confused model cannot loop forever).
4. Ask once more for the decision memo as schema-constrained JSON.
5. Guardrails (step 3): if the memo contains numbers no tool produced, ask
   for ONE rewrite; then apply the decision policy, which may block the
   model's decision. The model's own decision is kept for comparison.

The run record (AgentRun) keeps every tool call and the token counts;
step 4 (observability) builds on it.
"""
import json
from dataclasses import asdict, dataclass, field

from .guardrails import apply_decision_policy, find_unsupported_numbers

from .memo import MEMO_SCHEMA, MemoError, parse_memo
from .tools import TOOL_SCHEMAS, dispatch

SYSTEM_PROMPT = """You are an A/B test analyst for a mobile game. Answer the user's question about the experiment by calling tools.

Rules:
- Never calculate or guess numbers yourself. Every number you use must come from a tool result.
- For a ship / don't-ship question, call experiment_overview, sample_ratio_check, then compare_arms and power_check for every metric before deciding.
- If sample_ratio_check reports srm_detected = true, the data is untrustworthy: do not recommend shipping.
- Never segment or filter by sum_gamerounds: it is affected by the treatment.
- When you have what you need, reply in one short paragraph without calling a tool."""

MEMO_INSTRUCTION = """Now write the decision memo as JSON.
- decision: "ship", "do_not_ship", "inconclusive", or "not_applicable" if the question is not a ship decision.
- answer: a short paragraph answering the question.
- key_numbers: every number the answer uses, copied exactly as it appears in a tool result, with the name of that tool.
- Keep the units used in the tool results (percent, percentage points). Do not convert units or do arithmetic.
- risks: caveats a decision-maker should know.
Use only numbers that appear in the tool results above."""

REPAIR_INSTRUCTION = """These numbers in your memo do not appear in any tool result:
{problems}
Rewrite the memo as JSON. For each one, use the number exactly as written in a tool result,
in the same units (do not convert, e.g. to basis points), or delete it."""


@dataclass
class AgentRun:
    question: str
    tool_calls: list = field(default_factory=list)   # dicts: name, arguments, result
    messages: list = field(default_factory=list)
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    stop_reason: str = ""                            # "model_finished" or "max_steps"
    memo: dict | None = None
    memo_error: str | None = None
    memo_repairs: int = 0
    unsupported_numbers: list = field(default_factory=list)
    model_decision: str | None = None                # what the model said
    final_decision: str = ""                         # after guardrails
    guardrail_events: list = field(default_factory=list)


def _chat(client, run, **kwargs):
    """One model call, with the token bookkeeping in one place."""
    response = client.chat(run.messages, **kwargs)
    run.llm_calls += 1
    run.input_tokens += response.input_tokens
    run.output_tokens += response.output_tokens
    return response


def _request_memo(client, run, instruction):
    """Ask for the memo; store it (or the reason it was invalid) on the run."""
    run.messages.append({"role": "user", "content": instruction})
    response = _chat(client, run, response_format=MEMO_SCHEMA)
    run.messages.append(response.message)
    try:
        run.memo, run.memo_error = parse_memo(response.content), None
    except MemoError as e:
        run.memo, run.memo_error = None, str(e)


def run_agent(question, experiment, client, max_steps=8, max_repairs=1):
    run = AgentRun(question=question)
    run.messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    run.stop_reason = "max_steps"
    for _ in range(max_steps):
        response = _chat(client, run, tools=TOOL_SCHEMAS)
        run.messages.append(response.message)
        if not response.tool_calls:
            run.stop_reason = "model_finished"
            break
        for call in response.tool_calls:
            result = dispatch(experiment, call.name, call.arguments)
            run.tool_calls.append({"name": call.name, "arguments": call.arguments, "result": result})
            run.messages.append({"role": "tool", "tool_name": call.name, "content": json.dumps(result)})

    _request_memo(client, run, MEMO_INSTRUCTION)

    # Number provenance: one chance to fix made-up numbers, then block.
    if run.memo:
        run.unsupported_numbers = find_unsupported_numbers(run.memo, run.tool_calls)
        while run.unsupported_numbers and run.memo_repairs < max_repairs:
            run.memo_repairs += 1
            problems = "\n".join(f"- {p}" for p in run.unsupported_numbers)
            _request_memo(client, run, REPAIR_INSTRUCTION.format(problems=problems))
            run.unsupported_numbers = (find_unsupported_numbers(run.memo, run.tool_calls)
                                       if run.memo else [])

    run.model_decision = run.memo["decision"] if run.memo else None  # after any rewrite
    run.final_decision, events = apply_decision_policy(
        experiment, run.memo, run.tool_calls, run.unsupported_numbers)
    run.guardrail_events = [asdict(e) for e in events]
    return run
