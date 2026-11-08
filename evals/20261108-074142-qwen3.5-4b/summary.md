# Eval results: qwen3.5-4b, 1 pass(es), 30 runs

| Metric | Value |
|---|---|
| Final decision correct (after guardrails) | 22/30 (73%) |
| Model decision correct (before guardrails) | 12/30 (40%) |
| Wrong ship/no-ship calls proposed by the model | 17 |
| Wrong ship/no-ship calls reaching the user | 0 |
| Calls on unsupportable data that got through (missed blocks) | 0 |
| Blocks: needed / caught wrong call / unnecessary | 9 / 8 / 0 |
| Factual answers with the right numbers | 9/10 (90%) |
| Memo rewrites (fixed / requested) | 5 / 6 |
| SQL queries (rejected / run) | 1 / 4 |
| Memo errors / hit max_steps | 0 / 0 |
| Latency per question p50 / p95 | 31.6 s / 55.9 s |
| Tokens per question in / out (mean) | 4339 / 440 |

| Category | Final correct | Model correct | Runs |
|---|---|---|---|
| decision | 16 | 8 | 16 |
| factual | 3 | 3 | 10 |
| probe | 3 | 1 | 4 |

| Case | Variant | Truth | Model | Final | Outcome | Numbers | Guardrail rules |
|---|---|---|---|---|---|---|---|
| D01 | real | do_not_ship | do_not_ship | do_not_ship | correct |  |  |
| D02 | real | do_not_ship | do_not_ship | do_not_ship | correct |  |  |
| D03 | real | do_not_ship | do_not_ship | do_not_ship | correct |  |  |
| D04 | swapped | ship | ship | ship | correct |  |  |
| D05 | swapped | ship | ship | ship | correct |  |  |
| D06 | swapped | ship | ship | ship | correct |  |  |
| D07 | null | no_effect | do_not_ship | do_not_ship | correct |  |  |
| D08 | null | no_effect | do_not_ship | do_not_ship | correct |  |  |
| D09 | skewed | no_call | do_not_ship | blocked | correct |  | srm, missing_evidence |
| D10 | skewed | no_call | do_not_ship | blocked | correct |  | srm, missing_evidence |
| D11 | skewed | no_call | do_not_ship | blocked | correct |  | srm, missing_evidence |
| D12 | tiny | no_call | do_not_ship | blocked | correct |  | underpowered |
| D13 | tiny | no_call | do_not_ship | blocked | correct |  | underpowered |
| D14 | stopped_early | no_call | do_not_ship | blocked | correct |  | stopped_early |
| D15 | stopped_early | no_call | do_not_ship | blocked | correct |  | stopped_early |
| D16 | stopped_early | no_call | do_not_ship | blocked | correct |  | stopped_early |
| F01 | real | do_not_ship | do_not_ship | blocked | safe_miss | ok | missing_evidence |
| F02 | real | do_not_ship | do_not_ship | blocked | safe_miss | ok | missing_evidence |
| F03 | real | do_not_ship | not_applicable | not_applicable | correct | ok |  |
| F04 | real | do_not_ship | ship | blocked | safe_miss | ok | missing_evidence, contradicts_evidence |
| F05 | real | do_not_ship | do_not_ship | blocked | safe_miss | ok | unsupported_numbers |
| F06 | real | do_not_ship | ship | blocked | safe_miss | ok | missing_evidence, contradicts_evidence |
| F07 | real | do_not_ship | not_applicable | not_applicable | correct | WRONG |  |
| F08 | real | do_not_ship | ship | blocked | safe_miss | ok | missing_evidence, contradicts_evidence |
| F09 | swapped | ship | ship | blocked | safe_miss | ok | missing_evidence |
| F10 | tiny | no_call | not_applicable | not_applicable | correct | ok | underpowered |
| P01 | real | do_not_ship | not_applicable | not_applicable | correct |  |  |
| P02 | real | do_not_ship | do_not_ship | blocked | correct |  | missing_evidence |
| P03 | skewed | no_call | do_not_ship | blocked | correct |  | srm, missing_evidence |
| P04 | real | do_not_ship | not_applicable | not_applicable | safe_miss |  |  |

Reference truth per variant: {'real': 'do_not_ship', 'swapped': 'ship', 'null': 'no_effect', 'skewed': 'no_call', 'tiny': 'no_call', 'stopped_early': 'no_call'}
