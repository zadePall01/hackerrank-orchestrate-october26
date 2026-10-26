# Public sample failure comparison

Missing/unresolved predictions count as incorrect. Exact means matching status and the full ordered step array. Missing/extra semantic steps compare phase, operation, system, resource, state and evidence, excluding numbering; exact-row metrics still include numbering.

| Case | Reference status | Before | After | Before exact | After exact | Missing semantic steps after | Extra semantic steps after |
|---|---|---|---|---|---|---:|---:|
| case_01 | COMPLETE | UNRESOLVED | UNRESOLVED | False | False | 1 | 0 |
| case_02 | COMPLETE | UNRESOLVED | UNRESOLVED | False | False | 1 | 0 |
| case_03 | COMPLETE | COMPLETE | COMPLETE | False | False | 1 | 0 |
| case_04 | COMPLETE | UNRESOLVED | UNRESOLVED | False | False | 2 | 0 |
| case_05 | INCOMPLETE | INCOMPLETE | INCOMPLETE | True | True | 0 | 0 |
| case_06 | INCOMPLETE | UNRESOLVED | INCOMPLETE | False | False | 1 | 0 |
| case_07 | INCOMPLETE | UNRESOLVED | INCOMPLETE | False | False | 1 | 3 |
| case_08 | INCOMPLETE | UNRESOLVED | INCOMPLETE | False | False | 1 | 0 |
| case_09 | INCOMPLETE | UNRESOLVED | INCOMPLETE | False | False | 2 | 0 |
| case_10 | INCOMPLETE | UNRESOLVED | INCOMPLETE | False | False | 1 | 0 |
| case_11 | INCOMPLETE | INCOMPLETE | INCOMPLETE | True | True | 0 | 0 |
| case_12 | INCOMPLETE | INCOMPLETE | INCOMPLETE | True | True | 0 | 0 |
| case_13 | INCOMPLETE | INCOMPLETE | INCOMPLETE | True | True | 0 | 0 |
| case_14 | INCOMPLETE | INCOMPLETE | INCOMPLETE | True | True | 0 | 0 |
| case_15 | INCOMPLETE | INCOMPLETE | INCOMPLETE | True | True | 0 | 0 |
| case_16 | INCOMPLETE | INCOMPLETE | INCOMPLETE | True | True | 0 | 0 |
| case_17 | INCOMPLETE | INCOMPLETE | INCOMPLETE | False | False | 0 | 2 |
| case_18 | INCOMPLETE | UNRESOLVED | INCOMPLETE | False | False | 2 | 0 |
| case_19 | INCOMPLETE | INCOMPLETE | INCOMPLETE | True | True | 0 | 0 |
| case_20 | INCOMPLETE | UNRESOLVED | INCOMPLETE | False | False | 2 | 0 |
| case_21 | COMPLETE | UNRESOLVED | UNRESOLVED | False | False | 3 | 0 |
| case_22 | INCOMPLETE | UNRESOLVED | INCOMPLETE | False | False | 1 | 0 |
| case_23 | INCOMPLETE | UNRESOLVED | INCOMPLETE | False | False | 2 | 0 |
| case_24 | INCOMPLETE | INCOMPLETE | INCOMPLETE | False | False | 1 | 0 |
| case_25 | COMPLETE | UNRESOLVED | UNRESOLVED | False | False | 3 | 0 |
| case_26 | COMPLETE | UNRESOLVED | UNRESOLVED | False | False | 6 | 0 |
| case_27 | COMPLETE | UNRESOLVED | UNRESOLVED | False | False | 6 | 0 |
| case_28 | COMPLETE | UNRESOLVED | UNRESOLVED | False | False | 6 | 0 |
| case_29 | INCOMPLETE | UNRESOLVED | INCOMPLETE | False | False | 2 | 0 |
| case_30 | INCOMPLETE | UNRESOLVED | INCOMPLETE | False | False | 2 | 0 |
| case_31 | COMPLETE | UNRESOLVED | UNRESOLVED | False | False | 3 | 0 |
| case_32 | INCOMPLETE | UNRESOLVED | INCOMPLETE | False | False | 1 | 0 |
