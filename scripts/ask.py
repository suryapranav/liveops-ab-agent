"""Ask the agent one question about the Cookie Cats experiment.

Usage:
  python scripts/ask.py "Should we ship gate_40?"
  python scripts/ask.py "Should we ship gate_40?" --model qwen3.5:4b

Builds data/cookie_cats.db from data/cookie_cats.csv on first use, prints
the memo and a summary of tool calls, and saves the full run to runs/.
"""
import argparse
import json
import time
from dataclasses import asdict
from pathlib import Path

from liveops_ab import load_cookie_cats
from liveops_ab.db import build_database
from liveops_agent import OllamaClient, load_experiment, render_memo, run_agent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("--model", default="qwen3.5:4b")
    parser.add_argument("--csv", default="data/cookie_cats.csv")
    parser.add_argument("--db", default="data/cookie_cats.db")
    args = parser.parse_args()

    if not Path(args.db).exists():
        build_database(load_cookie_cats(args.csv), args.db)
        print(f"Built {args.db}")

    experiment = load_experiment(args.db)
    started = time.perf_counter()
    run = run_agent(args.question, experiment, OllamaClient(model=args.model))
    seconds = time.perf_counter() - started

    print("\nTool calls:")
    for i, call in enumerate(run.tool_calls, 1):
        print(f"  {i}. {call['name']}({json.dumps(call['arguments'])})")
    print(f"\nStop reason: {run.stop_reason} | LLM calls: {run.llm_calls} | "
          f"tokens in/out: {run.input_tokens}/{run.output_tokens} | {seconds:.1f}s\n")
    print(render_memo(args.question, run.memo) if run.memo else f"MEMO ERROR: {run.memo_error}")

    out = Path("runs") / f"{time.strftime('%Y%m%d-%H%M%S')}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"model": args.model, "seconds": seconds, **asdict(run)}, indent=2))
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
