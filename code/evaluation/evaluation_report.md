# Evaluation report

## Scope and metric definitions

Measured on all 32 public sample answers. Reference answers are loaded only after predictions are complete. Missing/unresolved cases count as incorrect; no hidden-dataset accuracy is available. These are local metrics, not the undisclosed official scoring formula.

Exact row accuracy requires matching status and the complete ordered step array. Sequence accuracy compares the complete step array, including citations and numbering. Step precision/recall uses exact seven-field step tuples. Field accuracy aligns on phase/operation/system/resource; unmatched steps contribute seven incorrect fields, including extra predictions.

## Actual sample results

| Metric | Value |
|---|---:|
| cases | 32 |
| resolved | 23 |
| status_correct | 23 |
| status_accuracy | 0.71875 |
| exact_rows | 9 |
| exact_row_accuracy | 0.28125 |
| sequence_accuracy | 0.28125 |
| step_precision | 0.7702702702702703 |
| step_recall | 0.5906735751295337 |
| field_accuracy | 0.7012987012987013 |
| matched_steps | 114 |
| predicted_steps | 148 |
| reference_steps | 193 |

## Failures

| Case | Expected status | Actual status | Expected steps | Actual steps |
|---|---|---|---:|---:|
| case_01 | COMPLETE | UNRESOLVED | 1 | 0 |
| case_02 | COMPLETE | UNRESOLVED | 1 | 0 |
| case_03 | COMPLETE | COMPLETE | 3 | 2 |
| case_04 | COMPLETE | UNRESOLVED | 2 | 0 |
| case_07 | INCOMPLETE | INCOMPLETE | 4 | 6 |
| case_08 | INCOMPLETE | INCOMPLETE | 4 | 3 |
| case_09 | INCOMPLETE | INCOMPLETE | 5 | 3 |
| case_10 | INCOMPLETE | INCOMPLETE | 4 | 3 |
| case_17 | INCOMPLETE | INCOMPLETE | 5 | 7 |
| case_18 | INCOMPLETE | INCOMPLETE | 14 | 12 |
| case_20 | INCOMPLETE | INCOMPLETE | 8 | 6 |
| case_21 | COMPLETE | UNRESOLVED | 3 | 0 |
| case_22 | INCOMPLETE | INCOMPLETE | 8 | 7 |
| case_23 | INCOMPLETE | INCOMPLETE | 8 | 6 |
| case_24 | INCOMPLETE | INCOMPLETE | 7 | 6 |
| case_25 | COMPLETE | UNRESOLVED | 3 | 0 |
| case_26 | COMPLETE | UNRESOLVED | 6 | 0 |
| case_27 | COMPLETE | UNRESOLVED | 6 | 0 |
| case_28 | COMPLETE | UNRESOLVED | 6 | 0 |
| case_29 | INCOMPLETE | INCOMPLETE | 14 | 12 |
| case_30 | INCOMPLETE | INCOMPLETE | 14 | 12 |
| case_31 | COMPLETE | UNRESOLVED | 3 | 0 |
| case_32 | INCOMPLETE | INCOMPLETE | 5 | 4 |

## Participant-created evaluation cases

Executable definitions are in code/tests/test_audit.py (CustomEvaluationCases).
- Surviving replica despite a successful workflow claim: expect INCOMPLETE and report/delete/verify the surviving profile.
- Marketing opt-out with an account-preservation request: expect no deletion authorization.
- Tombstone: stable reference without direct identifiers is compliant; exposed email requires redaction while retaining the reference.
- Absent primary with an active restore path: expect INCOMPLETE and BLOCK_RESTORE before verification.

Automated tests actually executed: 99; failures: 0; errors: 0; skipped: 0.

## Failures found and improvements made

- Initial vertical slice incorrectly used an unrelated later inventory to erase a surviving replica. Restricted absence scope to evidence grounded to the subject and added a regression test.
- Snapshot bundles include nested operational histories. Added explicit extraction preserving record timestamps and manifest capture cutoffs.
- Some absent/anonymous reference resources have no explicit participant-visible subject linkage found by this implementation. Such resources are not assigned by numeric suffix, array position, workflow timing, or sample answer.
- Remaining extraction, linkage, and citation disagreements are visible in the table above and runs/samples/diagnostics.md. Sample agreement is not claimed as hidden accuracy.

## Reproduction

Run `.venv/Scripts/python.exe code/evaluation/main.py --samples` on Windows or `.venv/bin/python code/evaluation/main.py --samples` elsewhere. Install code/requirements.txt first. Raw-text extraction cache can be deleted to exercise PDF/OCR again. No network or credentials are needed after dependency installation.
