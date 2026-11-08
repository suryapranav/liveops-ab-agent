"""Run the eval suite.

  python scripts/run_evals.py                       # qwen3.5:4b via Ollama, 1 pass (~15 min)
  python scripts/run_evals.py --repeats 3           # consistency across 3 passes
  python scripts/run_evals.py --only D01,F03        # a few cases
  python scripts/run_evals.py --baseline naive      # scripted naive analyst, no Ollama (seconds)

Writes evals/<label>/results.jsonl, summary.md and one trace per run.
"""
import argparse
import json
import time
from pathlib import Path

from liveops_agent import OllamaClient
from liveops_evals.baselines import NaiveClient
from liveops_evals.runner import run_suite
from liveops_evals.summary import markdown


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="qwen3.5:4b")
    parser.add_argument("--baseline", choices=["naive"])
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--only", help="comma-separated case ids")
    parser.add_argument("--csv", default="data/cookie_cats.csv")
    args = parser.parse_args()

    if args.baseline:
        client, label = NaiveClient(), f"baseline-{args.baseline}"
    else:
        client, label = OllamaClient(model=args.model), args.model.replace(":", "-")
    out_dir = Path("evals") / f"{time.strftime('%Y%m%d-%H%M%S')}-{label}"
    only = set(args.only.split(",")) if args.only else None

    rows, truths = run_suite(args.csv, client, out_dir, args.repeats, only)

    (out_dir / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    title = f"Eval results: {label}, {args.repeats} pass(es), {len(rows)} runs"
    report = markdown(rows, title) + f"\nReference truth per variant: {truths}\n"
    (out_dir / "summary.md").write_text(report)
    print("\n" + report + f"\nSaved {out_dir}")


if __name__ == "__main__":
    main()
