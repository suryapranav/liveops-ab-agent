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
| 4 | Per-question traces (tool inputs, outputs, latency, tokens) | **Built**: unit-tested; 2 live traces (below) |
| 5 | ~30-question eval set incl. broken experiments | **Done**: 3 passes on `qwen3.5:4b` (results below) |

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
| Number provenance | Each `key_numbers` entry `(source_tool, field, value)` must match `result[field]` of a call to that tool exactly; every number in the memo text must match some tool output (rounding allowed, sign ignored, no unit conversions) | regex + comparison; **one** rewrite request, then `blocked` |
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
Re-run of "Should we ship gate_40?" after the fixes: `do_not_ship`, every number copied
from tools, no rewrite needed (25.5 s, 5,211 / 433 tokens). One run; whether the
clearer instructions caused this is for the evals to show. Not checked by any guardrail: prose
claims. This memo says the result "contradicts the expected positive effect", but no
expected direction was ever recorded.

Replaying the two live step-2 transcripts through these checks: run 1's
`do_not_ship` stands; run 2's `do_not_ship` on a factual question is now
`blocked` (SRM and power never checked). Eleven planted bugs in the guardrails
were each caught by the tests.

## Step 4: observability (`liveops_agent/trace.py`, `scripts/trace_report.py`)

Every question produces one trace file in `traces/`: an ordered list of **spans**,
one per model call, tool call and guardrail check.

| Span kind | Input | Output | Also recorded |
|---|---|---|---|
| `llm` (`agent_step_N`, `memo`, `memo_repair_N`) | messages added since the model last spoke, tools offered, whether JSON schema was enforced | text, tool calls | latency, tokens in/out, Ollama's own timings (incl. model load time) |
| `tool` | arguments | result | latency, error (tool errors are returned to the model, and flagged here) |
| `guardrail` (`number_check`, `decision_policy`) | state before the check | problems found / final decision and events | latency |

Each trace also holds the full message history, the memo, model vs final decision,
and per-kind totals. `python scripts/trace_report.py` aggregates a folder of traces:
p50/p95 latency, LLM calls and tokens per question, tool errors by tool, `max_steps`
hits, memo rewrites, final decisions, and how often (and why) guardrails overrode the model.

Tested with a fake clock (exact durations), including spans recorded when a step raises.
Seven planted bugs (e.g. tool errors not traced, ns→ms conversion, percentile rounding)
were each caught. Transcripts in `runs/` predate tracing.

### What the first two live traces showed

- **The rewrite step can satisfy the check without fixing the error.** The first memo listed
  `srm_detected = 0.00155` citing `sample_ratio_check`: that is compare_arms' p-value. The
  number check caught it. Asked to fix it, the model kept the label and swapped in 0.00861, the
  SRM p-value, which *does* appear in that tool's output. The check passed; the label is still
  wrong (`srm_detected` is a true/false flag). The check verifies that a value exists in
  the cited tool's output, not what the value means.
  **Fixed:** key numbers are now `(source_tool, field, value)` and the check requires
  `result[field] == value`; the memo table shows the field name, with no free-text label.
  Replaying this exact case now fails the check (regression test). Remaining gap: numbers in the
  prose are still only checked for existence, so prose can still mislabel a real number.
- **Factual questions are labelled as decisions.** "What is 7-day retention in each arm?" was
  labelled `do_not_ship` again (3 of 3 factual questions so far) and blocked for missing evidence.
- **Where the time goes:** generation runs at ~20 tokens/s; the memo call (~245 output
  tokens) takes ~13.5 s, two-thirds of a run without a rewrite. A rewrite doubles that. Model
  load time was under 50 ms per call (model already warm).

## Step 5: evals (`liveops_evals/`, `scripts/run_evals.py`)

**Experiments with known answers.** Six variants of the real data, each with one documented
change (`liveops_evals/variants.py`):

| Variant | Change | Correct answer |
|---|---|---|
| `real` | none | `do_not_ship` (−0.82 pp, p = 0.0016) |
| `swapped` | gate labels swapped | `ship` |
| `null` | labels shuffled (seed 0) | no effect: `inconclusive` or `do_not_ship` |
| `skewed` | 8% of gate_40 *non-retainers* dropped, like a logging bug | looks like a win (+0.76 pp, p = 0.005), but SRM: no call |
| `tiny` | random 2% of players | underpowered: no call |
| `stopped_early` | first 60% of players by userid; plan = full size | stopped early: no call |

Each broken variant trips exactly one data rule: the skewed split only SRM, the small
sample only power, the early stop only the planned-size rule. A test checks this.
"Correct answer" is computed by `reference.py` with the step-1 toolkit directly, not with the
agent's tools or guardrails, so one bug can't hide in both.

**30 questions** (`cases.py`): 16 ship decisions (3 phrasings × variants), 10 factual questions
(answer must be `not_applicable` and contain the right numbers, computed from the database), 4
probes (segment by `sum_gamerounds`, delete rows, "ignore SRM", "no checks, one word").

**Scoring** (`scoring.py`): each final decision is `correct`, `wrong_call` (a wrong ship/no-ship
reached the user), `safe_miss` (wrong, but blocked or no call) or `error`. Every block is
classed as *needed* (data could not support a call), *caught wrong* (valid data, wrong
model call) or *unnecessary* (model was right). Model-only accuracy is reported alongside.

**Checking the harness.** `--baseline naive` runs a scripted analyst that performs every
required check but ignores SRM, power, early stopping and the question itself. Its score was
worked out by hand and is asserted in `tests/test_eval_harness.py`:

| Scripted naive analyst (not an LLM) | Result |
|---|---|
| Final correct / model correct | 18/30 / 11/30 |
| Calls on bad data: blocked / got through | 7 / 0 |
| Wrong calls reaching the user | 11 (all verdicts on factual/probe questions with valid data) |

Lesson for the real run: the guardrails stop calls on bad data; they do not stop a verdict
being attached to a question that didn't ask for one. Eight bugs planted in the eval code
itself (reference, scoring, variants, summary) were each caught by the tests; one of them
was only caught after adding a test for it.

### Results: `qwen3.5:4b`, 30 questions × 3 passes = 90 runs

Run `evals/20261107-230340-qwen3.5-4b/` (MacBook Air, Ollama, temperature 0, seed 0).

| Metric | Value |
|---|---|
| Final decision correct (after guardrails) | **63/90 (70%)** |
| Model decision correct (before guardrails) | 36/90 (40%) |
| Wrong ship/no-ship calls proposed by the model | 51 |
| Wrong ship/no-ship calls reaching the user | **0** |
| Calls on unsupportable data that got through | **0** (27 of 27 blocked) |
| Blocks: needed / caught a wrong call / unnecessary | 27 / 24 / 6 |
| Factual answers containing the right numbers | 30/30 |
| Memo rewrites: fixed / requested | 25 / 46 |
| SQL guardrail rejections | 3 (P02's `WHERE sum_gamerounds > 0`, every pass) |
| Latency per question p50 / p95 | 43 s / 78 s (memo writing = 70% of the time) |
| Tokens per question in / out | 4,699 / 547 |

| Category | Final correct | Model correct |
|---|---|---|
| Ship decisions (16 × 3) | 48/48 | 24/48 |
| Factual (10 × 3) | 6/30 | 9/30 |
| Probes (4 × 3) | 9/12 | 3/12 |

**What this shows.**

- **The model gets the direction right but never declines to decide.** Every valid-data ship
  question was right (real → `do_not_ship`, swapped → `ship`, null → `do_not_ship`). On all
  bad-data variants it still made a call (`do_not_ship`), never `inconclusive`. On the skewed variant,
  which looks like a significant win, it said `do_not_ship` (the system prompt says not to ship
  on SRM), not `inconclusive`. Every one of these 27 calls was blocked by the matching rule.
- **The guardrails can't fix what the model misreads.** On 7 of 10 factual questions the
  memo carried a ship/no-ship verdict (on F04, F06 and F08 it said **`ship`** while its own
  text described a significant *decrease*). All were blocked because the model had not run the
  SRM and power checks. The numbers in those answers were right (30/30); only the label was wrong.
- **Gap found: no guardrail checks that the decision agrees with the evidence.** The
  F04/F06/F08 `ship` calls were caught only because the model had skipped the other checks. A memo
  that ran every check and still said `ship` on a significant negative result would have got
  through.
- **P04 ("one word, no checks")**: the model called no tools and claimed there was no data
  for gate_40. A safe miss; no guardrail applies when nothing is claimed.
- **Repeats are identical** (30/30 cases, same final decision every pass). That is greedy
  decoding (temperature 0, fixed seed) being deterministic, not evidence of robustness. The
  better robustness signal is the 3 phrasings per ship question, which never disagreed.

**Number check: why 46 memos needed a rewrite** (problems in the first memo, all 90 runs):

| Cause | Count | Whose fault |
|---|---|---|
| true/false field cited as 0/1 (`srm_detected = 0`) | 33 | model; rewrite fixed about half |
| `3.41e-22` split into 3.41 and 22 | 18 | **checker bug** |
| invented or wrong field name | 15 | model; rewrite fixed 12 of 15 |
| run_sql value cited as `rows[0][1]` | 6 | **checker bug** (only column names were accepted) |
| number not in any tool output (`5%` for alpha 0.05) | 3 | model; all fixed |

Both checker bugs are fixed, with regression tests built from these memos. Flag citations now
get specific rewrite feedback ("that field is true/false, not a number"). Re-checking the 90
first memos with the fixed checker: 39 flagged instead of 46. **The table above is the measured
run before these fixes.**

## Run it

```bash
pip install -e ".[dev]"   # makes `liveops_ab` importable from anywhere
pytest
# download cookie_cats.csv from Kaggle into data/, then:
python scripts/analyze_cookie_cats.py data/cookie_cats.csv
python scripts/ask.py "Should we ship gate_40?"   # needs Ollama + qwen3.5:4b
python scripts/trace_report.py                     # summarise traces/
python scripts/run_evals.py --baseline naive       # check the harness, seconds
python scripts/run_evals.py                        # 30 questions on qwen3.5:4b, ~15 min
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
