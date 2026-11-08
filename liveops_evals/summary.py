"""Turn a list of scored runs into the headline metrics and a Markdown report."""
from collections import Counter, defaultdict

CALLS = {"ship", "do_not_ship"}


def _pct(k, n):
    return f"{k}/{n} ({100 * k / n:.0f}%)" if n else "0/0"


def _percentile(values, q):
    ordered = sorted(values)
    rank = max(1, -(-len(ordered) * q // 100))
    return ordered[int(rank) - 1]


def metrics(rows):
    n = len(rows)
    proposed_wrong = [r for r in rows if r["model_decision"] in CALLS and not r["model_correct"]]
    factual = [r for r in rows if r["numbers_ok"] is not None]
    repaired = [r for r in rows if r["memo_repairs"]]
    blocks = Counter(r["block"] for r in rows if r["block"])
    by_id = defaultdict(list)
    for r in rows:
        by_id[r["id"]].append(r["final_decision"])
    m = {
        "runs": n,
        "final_correct": sum(r["outcome"] == "correct" for r in rows),
        "model_correct": sum(r["model_correct"] for r in rows),
        "wrong_calls_proposed": len(proposed_wrong),
        "wrong_calls_reaching_user": sum(r["outcome"] == "wrong_call" for r in rows),
        "missed_blocks": sum(r["truth"] == "no_call" and r["final_decision"] in CALLS for r in rows),
        "blocks": dict(blocks),
        "factual_numbers_ok": sum(bool(r["numbers_ok"]) for r in factual),
        "factual_runs": len(factual),
        "rewrites": len(repaired),
        "rewrites_fixed": sum(r["unsupported_numbers_left"] == 0 for r in repaired),
        "sql_calls": sum(r["sql_calls"] for r in rows),
        "sql_rejected": sum(r["sql_rejected"] for r in rows),
        "errors": sum(r["outcome"] == "error" for r in rows),
        "max_steps": sum(r["stop_reason"] == "max_steps" for r in rows),
        "latency_p50_s": _percentile([r["duration_s"] for r in rows], 50) if rows else 0,
        "latency_p95_s": _percentile([r["duration_s"] for r in rows], 95) if rows else 0,
        "tokens_in_mean": round(sum(r["input_tokens"] for r in rows) / n) if n else 0,
        "tokens_out_mean": round(sum(r["output_tokens"] for r in rows) / n) if n else 0,
        "consistent_cases": sum(len(set(d)) == 1 for d in by_id.values()),
        "cases": len(by_id),
    }
    m["by_category"] = {
        cat: (sum(r["outcome"] == "correct" for r in rows if r["category"] == cat),
              sum(r["model_correct"] for r in rows if r["category"] == cat),
              sum(r["category"] == cat for r in rows))
        for cat in ("decision", "factual", "probe")
    }
    return m


def markdown(rows, title):
    m = metrics(rows)
    n = m["runs"]
    lines = [
        f"# {title}", "",
        "| Metric | Value |", "|---|---|",
        f"| Final decision correct (after guardrails) | {_pct(m['final_correct'], n)} |",
        f"| Model decision correct (before guardrails) | {_pct(m['model_correct'], n)} |",
        f"| Wrong ship/no-ship calls proposed by the model | {m['wrong_calls_proposed']} |",
        f"| Wrong ship/no-ship calls reaching the user | {m['wrong_calls_reaching_user']} |",
        f"| Calls on unsupportable data that got through (missed blocks) | {m['missed_blocks']} |",
        f"| Blocks: needed / caught wrong call / unnecessary | "
        f"{m['blocks'].get('needed', 0)} / {m['blocks'].get('caught_wrong', 0)} / "
        f"{m['blocks'].get('unnecessary', 0)} |",
        f"| Factual answers with the right numbers | {_pct(m['factual_numbers_ok'], m['factual_runs'])} |",
        f"| Memo rewrites (fixed / requested) | {m['rewrites_fixed']} / {m['rewrites']} |",
        f"| SQL queries (rejected / run) | {m['sql_rejected']} / {m['sql_calls']} |",
        f"| Memo errors / hit max_steps | {m['errors']} / {m['max_steps']} |",
        f"| Latency per question p50 / p95 | {m['latency_p50_s']:.1f} s / {m['latency_p95_s']:.1f} s |",
        f"| Tokens per question in / out (mean) | {m['tokens_in_mean']} / {m['tokens_out_mean']} |",
    ]
    if n > m["cases"]:
        lines.append(f"| Same final decision on every repeat | {_pct(m['consistent_cases'], m['cases'])} |")
    lines += ["", "| Category | Final correct | Model correct | Runs |", "|---|---|---|---|"]
    for cat, (final_ok, model_ok, total) in m["by_category"].items():
        lines.append(f"| {cat} | {final_ok} | {model_ok} | {total} |")
    lines += ["", "| Case | Variant | Truth | Model | Final | Outcome | Numbers | Guardrail rules |",
              "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        numbers = "" if r["numbers_ok"] is None else ("ok" if r["numbers_ok"] else "WRONG")
        lines.append(f"| {r['id']} | {r['variant']} | {r['truth']} | {r['model_decision']} | "
                     f"{r['final_decision']} | {r['outcome']} | {numbers} | "
                     f"{', '.join(r['guardrail_rules'])} |")
    return "\n".join(lines) + "\n"
