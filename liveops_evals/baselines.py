"""A scripted 'naive analyst' used to check the eval harness itself.

It runs every check the guardrails require (SRM, compare, power on 7-day
retention) but then ignores SRM, power and early stopping, ignores what the
question asked, and decides on significance and sign alone. Its behaviour
is fully predictable, so tests can assert exactly how the harness scores it.
It needs no Ollama, so the whole suite runs in seconds.
"""
import json

from liveops_agent.llm import scripted_text, scripted_tool_call

STEPS = [("sample_ratio_check", {}),
         ("compare_arms", {"metric": "retention_7"}),
         ("power_check", {"metric": "retention_7"})]


class NaiveClient:
    def chat(self, messages, tools=None, response_format=None):
        tool_results = [m for m in messages if m["role"] == "tool"]
        if response_format is None:
            if len(tool_results) < len(STEPS):
                name, args = STEPS[len(tool_results)]
                return scripted_tool_call(name, args, tokens=(0, 0))
            return scripted_text("done", tokens=(0, 0))

        compare = next(json.loads(m["content"]) for m in tool_results
                       if m["tool_name"] == "compare_arms")
        if not compare["significant"]:
            decision = "inconclusive"
        else:
            decision = "ship" if compare["diff_pp"] > 0 else "do_not_ship"
        memo = {
            "decision": decision,
            "answer": f"7-day retention changed by {compare['diff_pp']} pp (p = {compare['p_value']}).",
            "key_numbers": [{"source_tool": "compare_arms", "field": "diff_pp", "value": compare["diff_pp"]},
                            {"source_tool": "compare_arms", "field": "p_value", "value": compare["p_value"]}],
            "risks": [],
        }
        return scripted_text(json.dumps(memo), tokens=(0, 0))
