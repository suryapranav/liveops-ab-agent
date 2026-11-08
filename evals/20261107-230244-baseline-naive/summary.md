# Eval results: baseline-naive, 1 pass(es), 30 runs

| Metric | Value |
|---|---|
| Final decision correct (after guardrails) | 18/30 (60%) |
| Model decision correct (before guardrails) | 11/30 (37%) |
| Wrong ship/no-ship calls proposed by the model | 18 |
| Wrong ship/no-ship calls reaching the user | 11 |
| Calls on unsupportable data that got through (missed blocks) | 0 |
| Blocks: needed / caught wrong call / unnecessary | 7 / 0 / 0 |
| Factual answers with the right numbers | 2/10 (20%) |
| Memo rewrites (fixed / requested) | 0 / 0 |
| SQL queries (rejected / run) | 0 / 0 |
| Memo errors / hit max_steps | 0 / 0 |
| Latency per question p50 / p95 | 0.0 s / 0.0 s |
| Tokens per question in / out (mean) | 0 / 0 |

| Category | Final correct | Model correct | Runs |
|---|---|---|---|
| decision | 16 | 10 | 16 |
| factual | 0 | 0 | 10 |
| probe | 2 | 1 | 4 |

| Case | Variant | Truth | Model | Final | Outcome | Numbers | Guardrail rules |
|---|---|---|---|---|---|---|---|
| D01 | real | do_not_ship | do_not_ship | do_not_ship | correct |  |  |
| D02 | real | do_not_ship | do_not_ship | do_not_ship | correct |  |  |
| D03 | real | do_not_ship | do_not_ship | do_not_ship | correct |  |  |
| D04 | swapped | ship | ship | ship | correct |  |  |
| D05 | swapped | ship | ship | ship | correct |  |  |
| D06 | swapped | ship | ship | ship | correct |  |  |
| D07 | null | no_effect | inconclusive | inconclusive | correct |  |  |
| D08 | null | no_effect | inconclusive | inconclusive | correct |  |  |
| D09 | skewed | no_call | ship | blocked | correct |  | srm |
| D10 | skewed | no_call | ship | blocked | correct |  | srm |
| D11 | skewed | no_call | ship | blocked | correct |  | srm |
| D12 | tiny | no_call | inconclusive | inconclusive | correct |  | underpowered |
| D13 | tiny | no_call | inconclusive | inconclusive | correct |  | underpowered |
| D14 | stopped_early | no_call | do_not_ship | blocked | correct |  | stopped_early |
| D15 | stopped_early | no_call | do_not_ship | blocked | correct |  | stopped_early |
| D16 | stopped_early | no_call | do_not_ship | blocked | correct |  | stopped_early |
| F01 | real | do_not_ship | do_not_ship | do_not_ship | wrong_call | WRONG |  |
| F02 | real | do_not_ship | do_not_ship | do_not_ship | wrong_call | WRONG |  |
| F03 | real | do_not_ship | do_not_ship | do_not_ship | wrong_call | WRONG |  |
| F04 | real | do_not_ship | do_not_ship | do_not_ship | wrong_call | ok |  |
| F05 | real | do_not_ship | do_not_ship | do_not_ship | wrong_call | WRONG |  |
| F06 | real | do_not_ship | do_not_ship | do_not_ship | wrong_call | WRONG |  |
| F07 | real | do_not_ship | do_not_ship | do_not_ship | wrong_call | WRONG |  |
| F08 | real | do_not_ship | do_not_ship | do_not_ship | wrong_call | WRONG |  |
| F09 | swapped | ship | ship | ship | wrong_call | ok |  |
| F10 | tiny | no_call | inconclusive | inconclusive | safe_miss | WRONG | underpowered |
| P01 | real | do_not_ship | do_not_ship | do_not_ship | wrong_call |  |  |
| P02 | real | do_not_ship | do_not_ship | do_not_ship | wrong_call |  |  |
| P03 | skewed | no_call | ship | blocked | correct |  | srm |
| P04 | real | do_not_ship | do_not_ship | do_not_ship | correct |  |  |

Reference truth per variant: {'real': 'do_not_ship', 'swapped': 'ship', 'null': 'no_effect', 'skewed': 'no_call', 'tiny': 'no_call', 'stopped_early': 'no_call'}
