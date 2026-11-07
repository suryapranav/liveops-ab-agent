"""Ask the agent one question about the Cookie Cats experiment.

Usage:
  python scripts/ask.py "Should we ship gate_40?"
  python scripts/ask.py "Should we ship gate_40?" --model qwen3.5:4b

Builds data/cookie_cats.db from data/cookie_cats.csv on first use, prints
the span timeline and the memo, and saves the full trace to traces/.
"""
import argparse
import json
from dataclasses import asdict
from pathlib import Path

from liveops_ab import load_cookie_cats
from liveops_ab.db import build_database
from liveops_agent import OllamaClient, load_experiment, render_memo, run_agent


def print_timeline(run):
    print(f"\n{'start ms':>9} {'ms':>8}  {'kind':<9} {'name':<22} {'tokens in/out':>13}  error")
    for s in run.spans:
        tokens = f"{s.input_tokens}/{s.output_tokens}" if s.kind == "llm" else ""
        print(f"{s.start_ms:>9.0f} {s.duration_ms:>8.0f}  {s.kind:<9} {s.name:<22} {tokens:>13}  {s.error or ''}")
    print(f"\nTotal {run.duration_ms / 1000:.1f}s | LLM calls {run.llm_calls} | "
          f"tokens in/out {run.input_tokens}/{run.output_tokens} | stop: {run.stop_reason}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("--model", default="qwen3.5:4b")
    parser.add_argument("--csv", default="data/cookie_cats.csv")
    parser.add_argument("--db", default="data/cookie_cats.db")
    parser.add_argument("--traces", default="traces")
    args = parser.parse_args()

    if not Path(args.db).exists():
        build_database(load_cookie_cats(args.csv), args.db)
        print(f"Built {args.db}")

    run = run_agent(args.question, load_experiment(args.db), OllamaClient(model=args.model))
    print_timeline(run)
    print()
    if run.memo:
        print(render_memo(args.question, run.memo, run.final_decision, run.guardrail_events))
        if run.memo_repairs:
            print(f"(memo rewritten {run.memo_repairs}x to remove unsupported numbers)")
    else:
        print(f"MEMO ERROR: {run.memo_error}")

    out = Path(args.traces) / f"{run.started_at[:19].replace(':', '')}-{run.trace_id}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"model": args.model, "db": args.db, **asdict(run)}, indent=2))
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
