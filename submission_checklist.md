# Submission verification: BLOCKED

Implemented resource-edge traversal, scoped multilingual negation, cutoff-based policy applicability and correlated export owner_key retrieval. All eight previously exact public answers remain exact; case_06 adds the ninth.

| Official requirement | Final artifact / verification evidence | Status |
|---|---|---|
| Runnable Python and setup | code/main.py, code/README.md, code/requirements.txt | Verified with existing pinned dependencies |
| All public inputs and cutoff | 94 manifested evidence files; dataset fingerprint in runs/closure_verification/results.json | Read; full semantic completeness unproved |
| Exactly 518 sorted official output rows | All 518 processed; 381 diagnostic candidates, 137 errors, 441 warnings | FAIL: root output.csv absent; no guessed rows |
| Exact output schema and steps | Strict enum, numbering, phase/operation, evidence/time validation on candidates | Tests pass; complete submission unavailable |
| Evaluation report and custom cases | code/evaluation/evaluation_report.md; both required path variants inside archive | Present, actual public metrics |
| Final-run token/cost report | code/evaluation/usage_report.md | Honest attempted run; no output-producing final run exists |
| Source archive | code.zip: 35 files, 82952 bytes | CRC, allowlist, source equality and required paths pass |
| No dataset/caches/nested archives/secrets | Allowlist and high-confidence secret-pattern scan | Pass within stated scan scope; no perfect-security claim |
| Exact archive execution | Fresh extracted source/data/cache; reused Python 3.14.6 dependencies | Entry point exits 2 after 136.314s; expected grounding block |
| Tests | Archive evaluation command executes all 97 tests | Pass, no failures/errors/skips |
| Dependencies | Isolated pip check in staged environment | Pass |
| Genuine chat transcript | Root log.txt | Appended; not uploaded |
| Raw structured trace | trace_export_instructions.md, original local rollout | Pending session close and privacy review; no fabricated export |
| Interview explanation | code/evaluation/interview_guide.md | Prepared rehearsal; actual interview pending |

Exact run command: `.venv\Scripts\python.exe code/main.py`.
Evaluation: `.venv\Scripts\python.exe code/evaluation/main.py --samples`.
Archive verification: `.venv\Scripts\python.exe runs/closure_verification/verify.py` (already ran; preserves stage and refuses overwrite).

Public sample results: statuses 23/32 (71.875%), exact rows/sequence 9/32 (28.125%), exact-step precision 77.0270%, recall 59.0674%, field accuracy 70.1299%. Hidden accuracy unknown. Stricter applicability checking reduces candidate coverage versus the prior 415; this is disclosed, not presented as an accuracy gain.

Cold exact-archive run: 11 OCR invocations, zero cache hits; its 381 candidate rows equal the cached root run. Fresh dependency installation and other operating systems were not tested. Complete 518-row output remains blocked by ownership/policy evidence gaps. Existing organizer-repository clarification issue has no maintainer answer visible; no external message was posted.

Archive SHA-256: `7af4c50646235430c91bcb30eefe54ca6b595b2758c0c9ba06c8cfa0e7c097a2`.
Full filenames/sizes: runs/closure_verification/archive_manifest.md.
Machine results and captured commands/stdout/stderr: runs/closure_verification/.
Implementation/failure report: code/evaluation/closure_review.md.
Original supplied README, AGENTS, problem statement and dataset were preserved. Prior source/archive snapshots are under runs/closure_work/before/. No upload or submission occurred.

## Explicit partial-export update

At the user's request, root output.csv now contains 381 diagnostic candidate rows. output.csv.partial.md marks it NOT SUBMISSION-READY; 137 unresolved cases are omitted and 441 warnings remain in runs/latest/diagnostics.md. The --allow-partial CLI option still exits 2; default strict behavior is unchanged. All 99 tests passed after this change. The previously verified code.zip predates this opt-in feature and was not rebuilt in this turn. No complete 518-row output or final raw trace is claimed.
