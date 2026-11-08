"""The decision memo: a fixed JSON shape, validated, then rendered to Markdown.

The memo is requested with Ollama's `format` = MEMO_SCHEMA, which constrains
the model's output to valid JSON of this shape. We still validate it here,
because a different backend might not enforce the schema.

key_numbers lists each number the memo relies on as (source_tool, field,
value): the tool, the exact field name in that tool's result, and the value.
The guardrails check result[field] == value. There is deliberately no
free-text label: a live run showed the model attaching a wrong label
("srm_detected") to a real number, so the field name IS the label.
"""
import json

DECISIONS = ("ship", "do_not_ship", "inconclusive", "not_applicable")

MEMO_SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {"type": "string", "enum": list(DECISIONS)},
        "answer": {"type": "string"},
        "key_numbers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source_tool": {"type": "string"},
                    "field": {"type": "string"},
                    "value": {"type": "number"},
                },
                "required": ["source_tool", "field", "value"],
            },
        },
        "risks": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["decision", "answer", "key_numbers", "risks"],
}


class MemoError(ValueError):
    pass


def parse_memo(text):
    """Parse and validate the model's memo JSON. Raises MemoError if malformed."""
    try:
        memo = json.loads(text)
    except json.JSONDecodeError as e:
        raise MemoError(f"memo is not valid JSON: {e}") from e
    if not isinstance(memo, dict):
        raise MemoError("memo must be a JSON object")
    missing = [k for k in MEMO_SCHEMA["required"] if k not in memo]
    if missing:
        raise MemoError(f"memo is missing fields: {missing}")
    if memo["decision"] not in DECISIONS:
        raise MemoError(f"decision must be one of {DECISIONS}, got {memo['decision']!r}")
    for item in memo["key_numbers"]:
        if not isinstance(item, dict) or not {"source_tool", "field", "value"} <= item.keys():
            raise MemoError(f"bad key_numbers entry: {item!r}")
        if isinstance(item["value"], bool) or not isinstance(item["value"], (int, float)):
            raise MemoError(f"key number {item['field']!r} is not a number")
    return memo


def render_memo(question, memo, final_decision=None, guardrail_events=()):
    final_decision = final_decision or memo["decision"]
    lines = ["# Decision memo", "", f"**Question:** {question}", ""]
    if final_decision == memo["decision"]:
        lines.append(f"**Decision:** `{final_decision}`")
    else:
        lines.append(f"**Decision:** `{final_decision}` "
                     f"(model proposed `{memo['decision']}`; overridden by guardrails)")
    if guardrail_events:
        lines += ["", "**Guardrails:**"]
        lines += [f"- `{e['rule']}`: {e['detail']}" for e in guardrail_events]
    lines += [
        "",
        memo["answer"],
        "",
        "## Key numbers",
        "",
        "| Source tool | Field | Value |",
        "|---|---|---|",
    ]
    lines += [f"| `{k['source_tool']}` | `{k['field']}` | {k['value']} |" for k in memo["key_numbers"]]
    lines += ["", "## Risks", ""]
    lines += [f"- {risk}" for risk in memo["risks"]] or ["- None stated"]
    return "\n".join(lines) + "\n"
