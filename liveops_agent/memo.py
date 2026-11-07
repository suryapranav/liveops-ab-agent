"""The decision memo: a fixed JSON shape, validated, then rendered to Markdown.

The memo is requested with Ollama's `format` = MEMO_SCHEMA, which constrains
the model's output to valid JSON of this shape. We still validate it here,
because a different backend might not enforce the schema.

key_numbers lists each number the memo relies on together with the tool it
claims to come from. Step 3 (guardrails) checks those claims against the
actual tool outputs.
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
                    "label": {"type": "string"},
                    "value": {"type": "number"},
                    "source_tool": {"type": "string"},
                },
                "required": ["label", "value", "source_tool"],
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
        if not isinstance(item, dict) or not {"label", "value", "source_tool"} <= item.keys():
            raise MemoError(f"bad key_numbers entry: {item!r}")
        if isinstance(item["value"], bool) or not isinstance(item["value"], (int, float)):
            raise MemoError(f"key number {item['label']!r} is not a number")
    return memo


def render_memo(question, memo):
    lines = [
        "# Decision memo",
        "",
        f"**Question:** {question}",
        "",
        f"**Decision:** `{memo['decision']}`",
        "",
        memo["answer"],
        "",
        "## Key numbers",
        "",
        "| Number | Value | Source tool |",
        "|---|---|---|",
    ]
    lines += [f"| {k['label']} | {k['value']} | `{k['source_tool']}` |" for k in memo["key_numbers"]]
    lines += ["", "## Risks", ""]
    lines += [f"- {risk}" for risk in memo["risks"]] or ["- None stated"]
    return "\n".join(lines) + "\n"
