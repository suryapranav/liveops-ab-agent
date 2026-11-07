# LiveOps A/B Agent

An LLM agent that analyses mobile-game A/B experiments and writes decision
memos, built around **guardrails, observability and evals**. Data: the
Cookie Cats A/B test (~90k players; progression gate at level 30 vs 40;
1-day and 7-day retention).

## Status

| Step | What | State |
|---|---|---|
| 1 | Deterministic analysis toolkit + tests | **Done** |
| 2 | Agent (tools + read-only SQL) that writes a decision memo | **Built**: unit-tested; 2 live runs on `qwen3.5:4b` (below) |
| 3 | Guardrails enforced in code | **Built**: unit-tested; 3 live runs (below) |
| 4 | Per-question traces (tool inputs, outputs, latency, tokens) | Not started |
| 5 | ~30-question eval set incl. broken experiments | Not started |

## Step 1: analysis toolkit (`liveops_ab/`)

Plain Python (numpy + the standard library's `statistics.NormalDist`), so
every formula is visible in the source rather than hidden in a library call.

| Module | What it does | How it is verified |
|---|---|---|
| `srm.py` | Sample-ratio-mismatch check (chi-square, 1 df) | Matches `scipy.stats.chisquare`; skewed splits detected |
| `proportions.py` | Two-proportion z-test (pooled SE) + CI (unpooled SE) | p-value matches scipy's 2x2 chi-square; hand-computed example; 95% CI coverage ≈ 95% by simulation |
| `bootstrap.py` | Percentile bootstrap CI for the difference | Binomial shortcut matches literal user resampling; agrees with normal CI at large n |
| `power.py` | Required n, achieved power, MDE | Required n gives 80% power **in simulation**; MDE inverts power exactly |
| `peeking.py` | A/A simulation of repeated significance checks | 1 look ≈ 5% FPR; 5 looks ≈ 14% (Armitage et al., 1969) |
| `data.py` | CSV loading + validation; arm counts | Rejects duplicates, unknown/missing arms, non-boolean retention, post-treatment metrics |

Sanity check on the tests themselves: five deliberately planted bugs
(wrong SE, one-sided p-values, ignoring interim looks, sign flip) were each
caught by at least two failing tests.

### Design decisions

- **`sum_gamerounds` is post-treatment.** Gate position changes how much
  people play, so segmenting by it compares different populations per arm.
  `arm_counts` refuses it.
- **SRM threshold is 0.001.** SRM is a data-integrity alarm run on every
  test, so it is deliberately strict. It is a parameter.
- **Control = `gate_30`, treatment = `gate_40`, diff = treatment − control.**

## Step 2: the agent (`liveops_agent/`)

Model: `qwen3.5:4b`, running locally in Ollama (thinking off, temperature 0, fixed seed).

| File | What it does |
|---|---|
| `liveops_ab/db.py` | Builds SQLite from the CSV: `players` + one row of pre-registered `experiment` metadata (primary metric, alpha, target effect, planned split). Agent gets a **read-only** connection (`mode=ro`), enforced by SQLite. |
| `liveops_agent/tools.py` | 5 tools: `experiment_overview`, `sample_ratio_check`, `compare_arms`, `power_check`, `run_sql` (max 50 rows). The model names a metric; tools read counts themselves and call step-1 code, so the model never feeds numbers into the statistics. Tool errors go back to the model as data. |
| `liveops_agent/llm.py` | `OllamaClient` (plain `urllib` POST to `/api/chat`) and `ScriptedClient`, a fake model for tests. |
| `liveops_agent/agent.py` | The loop: model → tool calls → results → … until it answers or hits `max_steps`; then one schema-constrained call for the memo. Counts LLM calls and tokens. |
| `liveops_agent/memo.py` | Memo JSON schema (`decision`, `answer`, `key_numbers` with claimed source tool, `risks`), validation, Markdown rendering. |

Tests use the scripted fake model and a fake Ollama HTTP server, so they run without
Ollama. Six planted bugs were checked against them; five were caught. The survivor
(fetching all SQL rows before truncating) returns identical output and only costs memory.

```bash
ollama pull qwen3.5:4b
python scripts/ask.py "Should we ship gate_40?"
```

### First live runs (2 questions, MacBook Air, transcripts in `runs/`)

| Question | Tools called | Decision | Correct? | Time | Tokens in/out |
|---|---|---|---|---|---|
| Should we ship gate_40? | overview, SRM, compare 7-day, power 7-day | `do_not_ship` | Yes, but skipped 1-day retention, and called the 1 pp power target a "target effect" the result failed to meet | 37.8 s | 4936 / 489 |
| What is 1-day retention in each arm? | compare 1-day | `do_not_ship` | Numbers right; decision label wrong (should be `not_applicable`) | 18.7 s | 2202 / 290 |

In both memos, every number appears in a tool output. Two runs are anecdotes, not
an eval; step 5 measures this properly.

## Step 3: guardrails (`liveops_agent/guardrails.py`)

All enforced in code; none rely on the model following the prompt.

| Guardrail | Rule | Enforced by |
|---|---|---|
| Read-only SQL | One SELECT/WITH statement, no comments | string check |
| | Only SELECT / read / function actions (no PRAGMA, ATTACH, recursive CTEs) | SQLite authorizer |
| | No writes | `mode=ro` connection |
| | Max 50 rows, 2 s time budget | `fetchmany`, SQLite progress handler |
| | `sum_gamerounds` may be aggregated, never used to filter, group or sort | string check |
| Number provenance | Each `key_numbers` value must exactly match an output of the tool it cites (sign included); every number in the memo text must match some tool output (rounding allowed, sign ignored, no unit conversions) | regex + comparison; **one** rewrite request, then `blocked` |
| No winner on bad data | `ship` / `do_not_ship` → `blocked` if: SRM (p < 0.001), arm below `planned_users_per_arm` (stopped early), power < 80% on the primary metric, or SRM / compare / power on the primary metric were never successfully called | code recomputes SRM and power from the database, not from the transcript |

`inconclusive` and `not_applicable` answers are never blocked for data problems,
but the problems are attached as warnings. The model's own decision is kept
next to the final one, so evals can measure both.

Known limits: the text check allows the numbers 1, 7, 30 and 40 without a
source (they appear in "day 7", "gate 30"), so an invented 7 would pass. The
SQL string check is deliberately strict: a semicolon inside a string literal
is rejected.

### Live runs with guardrails (`qwen3.5:4b`)

| Question | Model said | Final | What happened |
|---|---|---|---|
| Should we ship gate_40? | `do_not_ship` | `blocked` | Memo said "82 basis points" (its own conversion of −0.82 pp). Asked to fix it, the model returned an identical memo. A correct decision, blocked: the cost of a strict rule. |
| What is 1-day retention in each arm? | `do_not_ship` | `blocked` | Factual question mislabelled as a decision, with no SRM/power check. Correctly blocked. |
| Does gate_40 work better for players with > 30 rounds? | `not_applicable` | `not_applicable` | Model refused to segment by `sum_gamerounds` (did not try SQL). But it invented a key number `sum_gamerounds = 0`, which **passed** the check: a bug. |

Fix after these runs: key numbers must now be exact copies, and a value exactly
half a unit away (0 vs alpha = 0.05) no longer counts as rounding. Rewrite requests now quote
the offending phrase and say not to convert units. Re-checking all five saved
transcripts with the fixed code flags exactly the "82" and the invented 0.
These fixes have not yet been re-run live.

Replaying the two live step-2 transcripts through these checks: run 1's
`do_not_ship` stands; run 2's `do_not_ship` on a factual question is now
`blocked` (SRM and power never checked). Eleven planted bugs in the guardrails
were each caught by the tests.

## Run it

```bash
pip install -e ".[dev]"   # makes `liveops_ab` importable from anywhere
pytest
# download cookie_cats.csv from Kaggle into data/, then:
python scripts/analyze_cookie_cats.py data/cookie_cats.csv
```

## Results (step 1, toolkit only, no agent yet)

From `python scripts/analyze_cookie_cats.py data/cookie_cats.csv`
(all values in `results/step1_results.json`). 90,189 players.

| Check | gate_30 (control) | gate_40 (treatment) | Difference, 95% CI | p |
|---|---|---|---|---|
| Arm size | 44,700 | 45,489 | SRM chi2 = 6.90 | 0.0086 |
| 1-day retention | 44.82% | 44.23% | −0.59 pp [−1.24, +0.06] | 0.074 |
| 7-day retention | 19.02% | 18.20% | −0.82 pp [−1.33, −0.31] | 0.0016 |

- Bootstrap CIs (10,000 resamples) agree with the normal CIs to within 0.02 pp.
- Smallest lift detectable at 80% power with these sample sizes: 0.93 pp (1-day), 0.74 pp (7-day).
- A/A peeking simulation at this sample size: 5.0% false positives with one
  final look vs 13.8% (±0.3%) when checking 5 times and stopping early.
- **Open question for the guardrail:** the SRM p-value (0.0086) passes the
  0.001 threshold but would fail at 0.01, so the threshold choice decides
  whether this experiment is trusted at all.
