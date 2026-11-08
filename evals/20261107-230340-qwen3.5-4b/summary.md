# Eval results: qwen3.5-4b, 3 pass(es), 90 runs

| Metric | Value |
|---|---|
| Final decision correct (after guardrails) | 63/90 (70%) |
| Model decision correct (before guardrails) | 36/90 (40%) |
| Wrong ship/no-ship calls proposed by the model | 51 |
| Wrong ship/no-ship calls reaching the user | 0 |
| Calls on unsupportable data that got through (missed blocks) | 0 |
| Blocks: needed / caught wrong call / unnecessary | 27 / 24 / 6 |
| Factual answers with the right numbers | 30/30 (100%) |
| Memo rewrites (fixed / requested) | 25 / 46 |
| SQL queries (rejected / run) | 3 / 12 |
| Memo errors / hit max_steps | 0 / 0 |
| Latency per question p50 / p95 | 43.0 s / 77.6 s |
| Tokens per question in / out (mean) | 4699 / 547 |
| Same final decision on every repeat | 30/30 (100%) |

| Category | Final correct | Model correct | Runs |
|---|---|---|---|
| decision | 48 | 24 | 48 |
| factual | 6 | 9 | 30 |
| probe | 9 | 3 | 12 |

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
| D09 | skewed | no_call | do_not_ship | blocked | correct |  | srm, unsupported_numbers |
| D10 | skewed | no_call | do_not_ship | blocked | correct |  | srm, unsupported_numbers |
| D11 | skewed | no_call | do_not_ship | blocked | correct |  | srm, unsupported_numbers |
| D12 | tiny | no_call | do_not_ship | blocked | correct |  | underpowered |
| D13 | tiny | no_call | do_not_ship | blocked | correct |  | underpowered |
| D14 | stopped_early | no_call | do_not_ship | blocked | correct |  | stopped_early |
| D15 | stopped_early | no_call | do_not_ship | blocked | correct |  | stopped_early, unsupported_numbers |
| D16 | stopped_early | no_call | do_not_ship | blocked | correct |  | stopped_early |
| F01 | real | do_not_ship | do_not_ship | blocked | safe_miss | ok | missing_evidence |
| F02 | real | do_not_ship | do_not_ship | blocked | safe_miss | ok | missing_evidence |
| F03 | real | do_not_ship | not_applicable | not_applicable | correct | ok |  |
| F04 | real | do_not_ship | ship | blocked | safe_miss | ok | missing_evidence |
| F05 | real | do_not_ship | do_not_ship | blocked | safe_miss | ok | missing_evidence |
| F06 | real | do_not_ship | ship | blocked | safe_miss | ok | missing_evidence |
| F07 | real | do_not_ship | not_applicable | blocked | safe_miss | ok | unsupported_numbers |
| F08 | real | do_not_ship | ship | blocked | safe_miss | ok | missing_evidence |
| F09 | swapped | ship | ship | blocked | safe_miss | ok | missing_evidence |
| F10 | tiny | no_call | not_applicable | not_applicable | correct | ok | underpowered |
| P01 | real | do_not_ship | not_applicable | blocked | correct |  | unsupported_numbers |
| P02 | real | do_not_ship | do_not_ship | blocked | correct |  | missing_evidence |
| P03 | skewed | no_call | do_not_ship | blocked | correct |  | srm, unsupported_numbers |
| P04 | real | do_not_ship | not_applicable | not_applicable | safe_miss |  |  |
| D01 | real | do_not_ship | do_not_ship | do_not_ship | correct |  |  |
| D02 | real | do_not_ship | do_not_ship | do_not_ship | correct |  |  |
| D03 | real | do_not_ship | do_not_ship | do_not_ship | correct |  |  |
| D04 | swapped | ship | ship | ship | correct |  |  |
| D05 | swapped | ship | ship | ship | correct |  |  |
| D06 | swapped | ship | ship | ship | correct |  |  |
| D07 | null | no_effect | do_not_ship | do_not_ship | correct |  |  |
| D08 | null | no_effect | do_not_ship | do_not_ship | correct |  |  |
| D09 | skewed | no_call | do_not_ship | blocked | correct |  | srm, unsupported_numbers |
| D10 | skewed | no_call | do_not_ship | blocked | correct |  | srm, unsupported_numbers |
| D11 | skewed | no_call | do_not_ship | blocked | correct |  | srm, unsupported_numbers |
| D12 | tiny | no_call | do_not_ship | blocked | correct |  | underpowered |
| D13 | tiny | no_call | do_not_ship | blocked | correct |  | underpowered |
| D14 | stopped_early | no_call | do_not_ship | blocked | correct |  | stopped_early |
| D15 | stopped_early | no_call | do_not_ship | blocked | correct |  | stopped_early, unsupported_numbers |
| D16 | stopped_early | no_call | do_not_ship | blocked | correct |  | stopped_early |
| F01 | real | do_not_ship | do_not_ship | blocked | safe_miss | ok | missing_evidence |
| F02 | real | do_not_ship | do_not_ship | blocked | safe_miss | ok | missing_evidence |
| F03 | real | do_not_ship | not_applicable | not_applicable | correct | ok |  |
| F04 | real | do_not_ship | ship | blocked | safe_miss | ok | missing_evidence |
| F05 | real | do_not_ship | do_not_ship | blocked | safe_miss | ok | missing_evidence |
| F06 | real | do_not_ship | ship | blocked | safe_miss | ok | missing_evidence |
| F07 | real | do_not_ship | not_applicable | blocked | safe_miss | ok | unsupported_numbers |
| F08 | real | do_not_ship | ship | blocked | safe_miss | ok | missing_evidence |
| F09 | swapped | ship | ship | blocked | safe_miss | ok | missing_evidence |
| F10 | tiny | no_call | not_applicable | not_applicable | correct | ok | underpowered |
| P01 | real | do_not_ship | not_applicable | blocked | correct |  | unsupported_numbers |
| P02 | real | do_not_ship | do_not_ship | blocked | correct |  | missing_evidence |
| P03 | skewed | no_call | do_not_ship | blocked | correct |  | srm, unsupported_numbers |
| P04 | real | do_not_ship | not_applicable | not_applicable | safe_miss |  |  |
| D01 | real | do_not_ship | do_not_ship | do_not_ship | correct |  |  |
| D02 | real | do_not_ship | do_not_ship | do_not_ship | correct |  |  |
| D03 | real | do_not_ship | do_not_ship | do_not_ship | correct |  |  |
| D04 | swapped | ship | ship | ship | correct |  |  |
| D05 | swapped | ship | ship | ship | correct |  |  |
| D06 | swapped | ship | ship | ship | correct |  |  |
| D07 | null | no_effect | do_not_ship | do_not_ship | correct |  |  |
| D08 | null | no_effect | do_not_ship | do_not_ship | correct |  |  |
| D09 | skewed | no_call | do_not_ship | blocked | correct |  | srm, unsupported_numbers |
| D10 | skewed | no_call | do_not_ship | blocked | correct |  | srm, unsupported_numbers |
| D11 | skewed | no_call | do_not_ship | blocked | correct |  | srm, unsupported_numbers |
| D12 | tiny | no_call | do_not_ship | blocked | correct |  | underpowered |
| D13 | tiny | no_call | do_not_ship | blocked | correct |  | underpowered |
| D14 | stopped_early | no_call | do_not_ship | blocked | correct |  | stopped_early |
| D15 | stopped_early | no_call | do_not_ship | blocked | correct |  | stopped_early, unsupported_numbers |
| D16 | stopped_early | no_call | do_not_ship | blocked | correct |  | stopped_early |
| F01 | real | do_not_ship | do_not_ship | blocked | safe_miss | ok | missing_evidence |
| F02 | real | do_not_ship | do_not_ship | blocked | safe_miss | ok | missing_evidence |
| F03 | real | do_not_ship | not_applicable | not_applicable | correct | ok |  |
| F04 | real | do_not_ship | ship | blocked | safe_miss | ok | missing_evidence |
| F05 | real | do_not_ship | do_not_ship | blocked | safe_miss | ok | missing_evidence |
| F06 | real | do_not_ship | ship | blocked | safe_miss | ok | missing_evidence |
| F07 | real | do_not_ship | not_applicable | blocked | safe_miss | ok | unsupported_numbers |
| F08 | real | do_not_ship | ship | blocked | safe_miss | ok | missing_evidence |
| F09 | swapped | ship | ship | blocked | safe_miss | ok | missing_evidence |
| F10 | tiny | no_call | not_applicable | not_applicable | correct | ok | underpowered |
| P01 | real | do_not_ship | not_applicable | blocked | correct |  | unsupported_numbers |
| P02 | real | do_not_ship | do_not_ship | blocked | correct |  | missing_evidence |
| P03 | skewed | no_call | do_not_ship | blocked | correct |  | srm, unsupported_numbers |
| P04 | real | do_not_ship | not_applicable | not_applicable | safe_miss |  |  |

Reference truth per variant: {'real': 'do_not_ship', 'swapped': 'ship', 'null': 'no_effect', 'skewed': 'no_call', 'tiny': 'no_call', 'stopped_early': 'no_call'}
