"""Run the step-1 toolkit on the Cookie Cats CSV and print every result.

Usage: python scripts/analyze_cookie_cats.py data/cookie_cats.csv
Writes the same numbers to results/step1_results.json, so the README can
quote measured values instead of hand-copied ones.
"""
import dataclasses
import json
import sys
from pathlib import Path

from liveops_ab import (CONTROL, OUTCOME_METRICS, TREATMENT, arm_counts,
                        bootstrap_diff_ci, load_cookie_cats,
                        minimum_detectable_effect, simulate_aa_peeking,
                        srm_check, two_proportion_ztest)


def main(csv_path):
    df = load_cookie_cats(csv_path)
    results = {"csv": str(csv_path), "n_users": len(df)}

    n_control = int((df["version"] == CONTROL).sum())
    n_treatment = int((df["version"] == TREATMENT).sum())
    srm = srm_check(n_control, n_treatment)
    results["srm"] = dataclasses.asdict(srm)
    print(f"Users: {CONTROL}={n_control:,}  {TREATMENT}={n_treatment:,}")
    print(f"SRM: chi2={srm.chi2:.3f}  p={srm.p_value:.4g}  "
          f"(alpha={srm.alpha})  detected={srm.srm_detected}")

    for metric in OUTCOME_METRICS:
        counts = arm_counts(df, metric)
        x_a, n_a = counts[CONTROL]
        x_b, n_b = counts[TREATMENT]
        test = two_proportion_ztest(x_a, n_a, x_b, n_b)
        boot = bootstrap_diff_ci(x_a, n_a, x_b, n_b, seed=0)
        mde = minimum_detectable_effect(n_a, n_b, test.p_a)
        results[metric] = {
            "ztest": dataclasses.asdict(test),
            "bootstrap": dataclasses.asdict(boot),
            "mde_abs_at_80pct_power": mde,
        }
        print(f"\n{metric}: {CONTROL}={test.p_a:.4%}  {TREATMENT}={test.p_b:.4%}")
        print(f"  diff={test.diff:+.4%} ({test.relative_lift:+.2%} relative)  "
              f"z={test.z:.3f}  p={test.p_value:.4g}")
        print(f"  95% CI (normal):    [{test.ci_low:+.4%}, {test.ci_high:+.4%}]")
        print(f"  95% CI (bootstrap): [{boot.ci_low:+.4%}, {boot.ci_high:+.4%}]")
        print(f"  MDE at 80% power:   {mde:.4%} absolute")

    peek = simulate_aa_peeking(p=0.45, n_per_arm=n_control, n_looks=5, seed=0)
    results["aa_peeking"] = dataclasses.asdict(peek)
    print(f"\nA/A peeking ({peek.n_looks} looks, {peek.n_sims:,} sims): "
          f"final-look FPR={peek.fpr_final_look:.3f}  "
          f"any-look FPR={peek.fpr_any_look:.3f} (+/- {peek.mc_standard_error:.3f})")

    out = Path("results/step1_results.json")
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(results, indent=2))
    print(f"\nWrote {out}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
