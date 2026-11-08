"""Run every case (optionally several times) and score it."""
import json
import tempfile
from dataclasses import asdict
from pathlib import Path

from liveops_ab import load_cookie_cats
from liveops_agent import run_agent
from liveops_agent.tools import load_experiment

from .cases import CASES
from .reference import reference_truth
from .scoring import score
from .variants import build_variant_databases


def run_suite(csv_path, client, out_dir=None, repeats=1, only=None, progress=print):
    cases = [c for c in CASES if not only or c.id in only]
    db_dir = Path(tempfile.mkdtemp(prefix="liveops_eval_dbs_"))
    paths = build_variant_databases(load_cookie_cats(csv_path), db_dir)
    experiments = {name: load_experiment(path) for name, path in paths.items()}
    truths = {name: reference_truth(exp) for name, exp in experiments.items()}

    rows = []
    for repeat in range(1, repeats + 1):
        for i, case in enumerate(cases, 1):
            exp = experiments[case.variant]
            numbers = case.numbers(exp) if case.numbers else None
            run = run_agent(case.question, exp, client)
            row = {"repeat": repeat, **score(case, truths[case.variant], run, numbers),
                   "trace_id": run.trace_id}
            rows.append(row)
            if out_dir:
                trace_dir = Path(out_dir) / "traces"
                trace_dir.mkdir(parents=True, exist_ok=True)
                (trace_dir / f"r{repeat}-{case.id}.json").write_text(
                    json.dumps({"case": case.id, "repeat": repeat, **asdict(run)}, indent=1))
            progress(f"[{repeat}/{repeats} {i:>2}/{len(cases)}] {case.id} {case.variant:<13} "
                     f"model={row['model_decision']} final={row['final_decision']} -> {row['outcome']}"
                     f"{'' if row['numbers_ok'] is None else ' numbers=' + str(row['numbers_ok'])}"
                     f" ({row['duration_s']}s)")
    return rows, truths
