# Closure review: measured changes and remaining blockers

Official criteria are status correctness, identity resolution, discovered records/risks, evidence, policy decisions and complete ordered steps. No weights are supplied.

## Controlled checkpoints

| Checkpoint | Correct statuses | Exact rows | Full candidates | Errors | Warnings |
|---|---:|---:|---:|---:|---:|
| skeptical_review | 23/32 | 8/32 | 415 | 103 | 240 |
| closure_resource_edge | 23/32 | 9/32 | 415 | 103 | 240 |
| closure_scoped_negation | 23/32 | 9/32 | 415 | 103 | 240 |
| closure_policy_verified | 23/32 | 9/32 | 381 | 137 | 441 |
| closure_owner_key | 23/32 | 9/32 | 381 | 137 | 441 |

97 unit/integration/regression/adversarial tests actually passed. Exact step precision 77.0270%, recall 59.0674%, field accuracy 70.1299%, sequence accuracy 28.125%. These are local public-sample metrics, not hidden accuracy.

## Implemented fixes

- Follow explicit stored source_resource_id edges using cutoff-valid unambiguous system routing; complete SQL scope can establish absence only after resource ownership is grounded. Traversal is bounded and replica state remains independent. Public case_06 is now exact.
- Preserve Japanese combining distinctions; apply multilingual negation within clauses, including mixed retention/deletion requests.
- Evaluate supplied policy predicates at audit_at: retention/holds, exclusive attachment ownership, shared ticket context, attributable analytics, deleted-account stable references and restore controls. Unknown facts prevent publication. No inactive-rule fallback deletion is invented.
- Recognize owner_key in correlated export readbacks. Regression tests cover correct ownership and cross-subject isolation. No observed aggregate score change is attributed to this addition.

## Reproducible remaining failures

| Input | Expected / observed | Root cause and next action |
|---|---|---|
| Public case_01 | Reference COMPLETE; unresolved | account_001 has no parsed subject-linked observation; deletion-worker claim alone is insufficient. Need participant-visible ownership link. |
| Public case_21 | Reference COMPLETE; unresolved | analytics_5335 has null identifying fields; anonymization activity names no subject. Need historical ownership. |
| Public cases_18/20 | Expected retained security checks absent | Exact IDs audit_record_6645/audit_record_5569 not located in text, parsed SQL/JSON/logs or extracted PDF/image text. Need official source clarification. |
| Full conditional-policy cases | 137 unresolved; 441 warnings across candidates | Some supplied retention/exclusivity facts are absent; no valid official UNKNOWN output label. Need applicable facts or official interpretation. |

The stricter policy gate reduces diagnostic candidate coverage from 415 to 381. This is a disclosed coverage regression from identifying previously unchecked assumptions; it is not an accuracy improvement claim. Root output.csv remains missing. No fake success rows were emitted.

## Investigation boundary

A 90-minute budget and 120-minute hard stop were recorded in runs/closure_work/investigation_budget.json. The user subsequently shortened remaining work to two minutes. The investigation was stopped early; no claim that 90 minutes elapsed is made. All 94 manifested evidence files were parsed; a 2,904-observation field inventory found three explicit source_resource_id edges and six owner_key occurrences. No further complete-case ownership links were established. Source snapshots and the prior archive are preserved under runs/closure_work/before/.

The organizer repository has an open participant clarification request at https://github.com/interviewstreet/hackerrank-orchestrate-october26/issues/24 . No maintainer answer was visible when checked. Participant comments are not official rules and were not used for predictions. No external message was posted.

## Reproduce

Run `.venv\Scripts\python.exe code/evaluation/main.py --samples`, then `.venv\Scripts\python.exe code/main.py --diagnostics runs/closure_final`. The latter exits 2 honestly. `code/package.py --overwrite` builds the review archive. Exact extracted-archive verification is recorded separately in runs/closure_verification/results.json.

## Raw trace

The supplied agent_trace_instructions.md says to finish and quit the session before copying its original structured files. This session remains live; no final raw trace can honestly be claimed. Use trace_export_instructions.md after quitting. log.txt is the separate development transcript.
