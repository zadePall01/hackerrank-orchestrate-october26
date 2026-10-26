# Independent engineering evaluation

## Result and scope

Task behavior improved on measured public cases, but the submission remains
incomplete. No hidden evaluation labels are available. Full-dataset figures below
measure execution, candidate coverage, schema consistency and explicit failures,
**not accuracy**. The specification supplies scoring criteria but no weights or
scoring formula. Local metrics are not claimed as the official grader formula.

The unchanged 32-case public reference set was used for every experiment. This
is repeated development-set evaluation, not an independent held-out estimate.
The inference pipeline never reads sample_output.csv. No model calls or prompt
changes were introduced. All improvements are preprocessing, algorithm,
validation or evaluation fixes; there are no hosted-model errors to attribute.

## Baseline and environment

Working directory: repository root. Windows 11 build 26200; Python 3.14.6
64-bit. Installed versions: pypdf 6.21.2, RapidOCR 3.10.0, ONNX Runtime 1.31.0,
Pillow 13.0.0. No credentials or network access are required for these runs.
All comparison runs used the same content-addressed document-text cache.
Consequently these timings exclude fresh OCR and are not cold-start benchmarks.

Exact commands executed:

```powershell
.venv\Scripts\python.exe code/evaluation/main.py --samples
.venv\Scripts\python.exe code/main.py --diagnostics runs/independent_audit/baseline_full --cache runs/extraction-cache
.venv\Scripts\python.exe code/evaluation/audit_run.py --label baseline
.venv\Scripts\python.exe code/evaluation/audit_run.py --label restore_fix
.venv\Scripts\python.exe code/evaluation/audit_run.py --label replica_fix
.venv\Scripts\python.exe code/evaluation/audit_run.py --label coverage_fix
.venv\Scripts\python.exe code/evaluation/audit_run.py --label contradiction_fix
.venv\Scripts\python.exe code/evaluation/audit_run.py --label intent_fix
.venv\Scripts\python.exe code/evaluation/audit_run.py --label final
.venv\Scripts\python.exe code/evaluation/audit_run.py --label scope_fix
.venv\Scripts\python.exe code/evaluation/main.py --samples
.venv\Scripts\python.exe code/main.py --diagnostics runs/full --cache runs/extraction-cache
```

`final` was the initial combined checkpoint; `scope_fix` is the last prediction
change and is the final comparison below. Each experiment stores summary.json,
tests.txt, sample/full diagnostics and partial predictions under
`runs/independent_audit/experiments/<label>/`. The harness refuses to overwrite an
existing experiment; use a new label for reproduction on the current source.

Input fingerprint for all full runs:
`b5863ab0d24ea781de41b22f487ce4470579abd3e0b01ed7de1736a06251d863`.

Rollback snapshot: `runs/independent_audit/before/code/`; previous archive:
`runs/independent_audit/before/code.zip`. These were copied before prediction
changes. Restore into a separate checkout to rerun the old code with the same
dataset and environment. They are intentionally excluded from the source ZIP.

## Measured public-sample comparison

Missing/unresolved cases count as incorrect. Exact step matching includes all
seven fields, including step_no; field alignment preserves duplicate steps.

| Metric | Before | After |
|---|---:|---:|
| Correct deletion statuses | 11/32 | 23/32 |
| Status accuracy | 34.375% | 71.875% |
| Exact rows | 8/32 | 8/32 |
| Exact sequence accuracy | 25.00% | 25.00% |
| Exact step precision | 94.2857% | 76.1905% |
| Exact step recall | 34.1969% | 58.0311% |
| Field accuracy | 34.7253% | 69.5527% |
| Exact matched steps | 66/193 | 112/193 |
| Predicted steps | 70 | 147 |
| Reference resource recall proxy | 30.6306% | 54.0541% |
| Reference treatment recall proxy | 35.2332% | 73.5751% |
| Reference citation recall proxy | 25.3333% | 57.3333% |

Resource recall compares unique system/resource pairs. Treatment recall compares
phase/operation/system/resource/state tuples. Citation recall additionally
requires the reference evidence ID on expected evidence-backed steps. These are
transparent local proxies for discovery, policy and citation criteria. There
are no standalone reference identity-resolution labels, so no independent
identity accuracy score is invented.

**Regression:** aggregate exact-step precision decreased. Newly emitted rows
often omit an ungrounded account check, causing missing steps and shifted
verification numbering. Exact row accuracy did not improve. None of the 11
previously emitted sample rows changed; the original eight exact rows remain
exact. See sample_failure_comparison.md for all case-level outcomes.

## Full-dataset behavioral comparison

| Check | Before | After |
|---|---:|---:|
| Requests accounted for | 518 | 518 |
| Schema-valid candidate rows | 175 | 415 |
| Unresolved cases | 343 | 103 |
| Candidates with account-coverage warnings | 0 | 240 |
| Evidence files extracted | 94 | 94 |
| Observations extracted | 2,904 | 2,904 |
| Full schema-valid final submission | No | No |
| Generative model calls / tokens / hosted cost | 0 / 0 / USD 0 | 0 / 0 / USD 0 |
| Warm full-run seconds, one experiment | 0.5384 | 0.5057 |

Timings are single measurements with normal variation; no speed improvement is
claimed. No hosted inference cost is incurred; local compute is unmeasured.
The CLI exits 2 and does not publish output.csv when unresolved cases or
coverage warnings remain. All candidate rows pass schema, ordering, citation
existence and citation-cutoff validation; this does not prove semantic coverage.

## Controlled changes and attribution

| Checkpoint | Change | Correct sample statuses | Exact rows | Full candidates |
|---|---|---:|---:|---:|
| baseline | Original code | 11 | 8 | 175 |
| restore_fix | Parse deny/allow and reject missing restore decision | 11 | 8 | 175 |
| replica_fix | Reconcile each physical store independently | 11 | 8 | 175 |
| coverage_fix | Preserve grounded INCOMPLETE findings without inventing an account | 23 | 8 | 415 |
| contradiction_fix | Observed identifiers/flags override compliance labels; strict booleans | 23 | 8 | 415 |
| intent_fix | Distinguish questions, quotations and scoped retention exceptions | 23 | 8 | 415 |
| final | Duplicate-aware field metrics and primitive-step validation | 23 | 8 | 415 |
| scope_fix | Partial JSON collections cannot establish absence | 23 | 8 | 415 |

The coverage change is the only experiment that changed the public aggregate
scores. The safety fixes improve their reproduced regression cases; the supplied
sample scores do not demonstrate an additional accuracy benefit from them.
No extra generative model calls or multi-agent architecture was justified.

## Reproducible failure table

Tests below are in code/tests/test_independent_review.py. Run them with:
`.venv\Scripts\python.exe -m unittest discover -s code/tests -p test_independent_review.py -v`.

| ID / category | Reproducible input or test | Expected behavior | Baseline observation | Root cause / fix |
|---|---|---|---|---|
| F01 preprocessing | RestoreReviewTests: decision=deny, policy=privacy_deletion | BLOCKED | ACTIVE | Missing decision mapping; parse explicit authorization |
| F02 preprocessing | RestoreReviewTests: restore event without decision | Explicit error | Default ACTIVE | Invented default allow removed |
| F03 state algorithm | ReplicaReviewTests: old replica PRESENT, newer primary ABSENT | Keep replica violation | ABSENT | Single global latest timestamp; separate store timelines |
| F04 coverage algorithm | CoverageReviewTests: grounded search record, no account ID | INCOMPLETE candidate with coverage warning | Entire case rejected | Account gate moved to completeness/publication checks |
| F05 state interpretation | ContradictionReviewTests: REDACTED plus actual email | Exposed PII | REDACTED | Compliance label trusted before contents; actual identifiers now win |
| F06 state interpretation | ContradictionReviewTests: ANONYMIZED plus actual user_id | Still identifiable | ANONYMIZED | Same precedence error fixed |
| F07 validation | ContradictionReviewTests: enabled=maybe | Explicit error | ACTIVE | Arbitrary string treated as enabled; strict boolean parser |
| F08 extraction | ContradictionReviewTests: phone in message, null email column | Exposed PII | REDACTED | Free text scanned only for email; international-phone detection added |
| F09 intent | IntentReviewTests: How do I delete my account? | No authorization | Authorized | Keyword match ignored informational scope; procedural question rule |
| F10 intent | IntentReviewTests: copy of message saying "delete my account" | No authorization | Authorized | Quoted content treated as consent; quotes excluded |
| F11 intent | IntentReviewTests: Do not delete invoices; delete account | Authorize account deletion | Rejected | Global negation override; clause-scoped intent |
| F12 evaluator | EvaluatorReviewTests: duplicate predicted verification | Penalize extra seven fields | Duplicate overwritten; 6/7 field score | Dictionary alignment lost multiplicity; list groups preserve duplicates |
| F13 serialization | EvaluatorReviewTests: steps_json=[123] | AuditError | Unhandled TypeError | Validate object type before field set |
| F14 absence inference | ReplicaReviewTests: partial empty JSON collection plus related ticket | Preserve known account observation | Invented ABSENT | Added explicit completeness flag; partial JSON cannot prove absence |
| F15 retrieval, unresolved | Public case_01; identity exists but no linked absent-account ID found | Canonical verification names account_001 | Unresolved | Need grounded ownership evidence; no numeric or row-position guess |
| F16 retrieval, unresolved | Public case_03 anonymous analytics resource | Reference includes analytics_9406 verification | Missing analytics verification | Subject link not established; remains open |
| F17 scope, unresolved | Public case_17 | Reference has a smaller verification set | Extra historical-account/tombstone checks | Repeated-request resource scope needs stronger evidence; no special-case exclusion |
| F18 evidence, unresolved | Public case_24 | Reference includes retained audit verification | Missing audit check | Eligible subject linkage not established; no future-evidence citation invented |

## Tests and remaining limits

Original suite: 27 passed before changes. Final suite: **43 passed**, no failures,
errors or skips in the recorded run. The 16 new tests were also run against the
saved old source in an isolated temporary directory; failures are recorded in
`runs/independent_audit/baseline_adversarial.txt`. These are regression tests used
to guide fixes, not a blind held-out benchmark.

Remaining full failures: 101 insufficient account-coverage cases, one case with
no subject-linked observation, and one catalog-linked backup without eligible
resource-state evidence. Another 240 candidate plans have incomplete account
coverage. Raw OCR text coverage is not semantic fact coverage; UI table parsing,
retention-condition interpretation and arbitrary multilingual intent remain
limited. Strict validation cannot establish omitted resources or citation meaning.

## Next highest-impact improvement

Establish resource ownership and lifecycle scope from participant-visible
historical catalog/readback evidence, particularly absent accounts and anonymous
analytics resources. Then measure exact-row and sequence accuracy on the same
regression set. Additional filename, numbering, positional or timing-based
ownership guesses are not accepted substitutes. If no grounded link is present,
obtain official clarification rather than encoding the reference answers.
