"""The agent loop.

1. Send the question plus tool descriptions to the model.
2. If the model asks for tools, run them and send the results back.
3. Repeat until the model answers without calling a tool, or until
   max_steps (a hard cap, so a confused model cannot loop forever).
4. Ask once more for the decision memo as schema-constrained JSON.

The run record (AgentRun) keeps every tool call and the token counts;
step 4 (observability) builds on it.
"""
import json
from dataclasses import dataclass, field

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
- risks: caveats a decision-maker should know.
Use only numbers that appear in the tool results above."""


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


def _chat(client, run, **kwargs):
    """One model call, with the token bookkeeping in one place."""
    response = client.chat(run.messages, **kwargs)
    run.llm_calls += 1
    run.input_tokens += response.input_tokens
    run.output_tokens += response.output_tokens
    return response


def run_agent(question, experiment, client, max_steps=8):
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

    run.messages.append({"role": "user", "content": MEMO_INSTRUCTION})
    memo_response = _chat(client, run, response_format=MEMO_SCHEMA)
    run.messages.append(memo_response.message)
    try:
        run.memo = parse_memo(memo_response.content)
    except MemoError as e:
        run.memo_error = str(e)
    return run
