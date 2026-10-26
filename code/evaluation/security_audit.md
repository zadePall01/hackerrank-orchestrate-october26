# Adversarial and reliability audit

## Scope, baseline and acceptance

This audit maps threats to the supplied Ghost Data Still Exists specification:
untrusted requests and evidence must not authorize tool actions, override policy,
fabricate state, leak sensitive information, or damage supplied assets. It does
not claim perfect security or hidden-dataset accuracy.

The pre-audit code/archive are preserved at `runs/security_audit/before/`.
Baseline and final experiments are at
`runs/independent_audit/experiments/security_baseline/` and
`runs/independent_audit/experiments/security_release/`.
Environment: Windows 11, Python 3.14.6; pinned pypdf 6.21.2, RapidOCR 3.10.0,
ONNX Runtime 1.31.0 and Pillow 13.0.0. No new dependencies were installed.

Commands actually run include:

```powershell
.venv\Scripts\python.exe code/evaluation/audit_run.py --label security_baseline
.venv\Scripts\python.exe -m unittest discover -s code/tests -p test_security_audit.py -v
.venv\Scripts\python.exe code/evaluation/audit_run.py --label security_core
.venv\Scripts\python.exe code/evaluation/audit_run.py --label security_workers
.venv\Scripts\python.exe code/evaluation/audit_run.py --label security_final
.venv\Scripts\python.exe code/evaluation/audit_run.py --label security_verified
.venv\Scripts\python.exe code/evaluation/audit_run.py --label security_acceptance
.venv\Scripts\python.exe code/evaluation/audit_run.py --label security_release
```

Baseline: 43 tests passed. The first 12 hostile tests reproduced seven failures
and one uncontrolled encoding error. A saved-source replay of those tests plus
two packaging tests reproduced nine failures and one error in 14 tests; see
`runs/security_audit/before_failures.txt`. The current suite passes **78 tests**,
including **35 new security/reliability tests**, with no skips in the acceptance
run. Tests use fictional fixtures, synthetic secret sentinels, and explicit
fault injection; they do not use real credentials or treat mocks as predictions.

Public sample outcomes are unchanged: 23/32 correct statuses, 8/32 exact rows,
76.1905% exact-step precision, 58.0311% recall, 69.5527% field accuracy, and 25%
sequence accuracy. All previously emitted sample and full-dataset candidate
rows compared equal after the core mitigations. Full behavior remains 415
candidates, 103 unresolved cases and 240 account-coverage warnings. These are
coverage figures, not full-dataset accuracy. Final publication remains blocked.

## Actual attack surface and trust boundaries

1. **Request text:** legitimate deletion authorization must be distinguished
   from quotations, informational requests and attempts to dictate labels.
2. **CSV inputs and policy:** strict schemas; the supplied policy is the task's
   authoritative policy data. Prose inside evidence cannot change it.
3. **Manifest and evidence paths:** read-only dataset access, including resolved
   symlink paths. Paths cannot escape the dataset through manifest references.
4. **JSON, logs and SQL:** these describe observations and claims; they cannot
   supply executable Python or commands. Identity-bearing fields must be scoped.
5. **PDF/PNG native parsing:** parser errors, decompression/size abuse, missing
   dependencies and hangs are relevant even without a hosted LLM.
6. **Local cache:** an optimization and corruption boundary, not an authenticated
   evidence source. Credential-like text is not persisted in new cache entries.
7. **Output/diagnostics/package writes:** only generated artifacts may be
   replaced, and interrupted writes must preserve previous complete files.
8. **No live remediation tools:** DELETE_RECORD and other operations are output
   descriptions. The application cannot delete accounts, email people, deploy
   resources, or call a hosted model API.

Top-level official files and installed source/packages are trusted inputs to
this audit. An attacker who can rewrite policy files, application code, or both
a cache entry and its integrity hash is outside what content validation alone
can authenticate. No signing authority is supplied by the challenge.

## Reproduced problems, mitigations and verification

Tests named below are in `code/tests/test_security_audit.py`, unless another
test file is stated. "Verified" means the stated test/experiment ran, not that
all variants of the risk have been eliminated.

| Risk / pre-fix behavior | Proportional mitigation | Test evidence | Residual risk | Verified |
|---|---|---|---|---|
| CLI could overwrite its supplied request CSV using --output and --overwrite | Protect existing dataset assets, repository source/instructions/log, and symlink destinations; retain valid new custom output paths | test_cli_cannot_overwrite_supplied_request_even_with_overwrite; original CLI integration still passes | Check/use filesystem races and privileged concurrent writers are not eliminated | Yes |
| Instructions in an arbitrary evidence field could falsely link another person's resource | Ownership indexes inspect semantic identity fields; instruction fields cannot establish ownership | test_injected_instruction_field_does_not_establish_ownership | Forged facts in legitimate semantic fields cannot be authenticated without external evidence | Yes |
| Reused trace IDs inherited the previous person's email | Reset trace context at a new request-start event | test_trace_reuse_does_not_inherit_other_subject | Logs lacking correlation or request boundaries can still be ambiguous | Yes |
| Direct label instruction could attempt to bypass authorization/policy | Bounded intent interpretation and deterministic policy/planner; no instruction execution | test_direct_label_instruction_is_not_authorization; test_authorized_request_cannot_override_observed_violation | Lexical intent interpretation is incomplete, particularly novel multilingual phrasing | Yes |
| Retrieved document requested file/tool actions | Artifact text is data; no eval, shell commands or arbitrary action tools | test_data_instructions_do_not_execute_tools; original injection test | Native parser vulnerabilities are a separate risk | Yes |
| Duplicate JSON keys silently selected the last value; NaN was accepted | Strict JSON parser rejects duplicate keys, non-finite values and excessive nesting; applied to artifact JSON, structured logs, embedded SQL records and output validation | test_duplicate_json_keys_rejected; test_nonfinite_json_rejected; test_duplicate_output_json_keys_fail; test_deep_json_budget | Large but permitted inputs can still consume significant CPU/memory | Yes |
| Corrupt CSV encoding leaked an uncontrolled exception; empty requests looked runnable | Controlled UTF-8 failure, BOM support, nonempty requests, duplicate/header/row validation | test_invalid_encoding_is_controlled; test_bom_unicode_input_is_valid; test_bom_log_is_valid; test_empty_requests_fail_explicitly; test_duplicate_requests_fail | Non-UTF encodings are rejected, not guessed | Yes |
| Workflow SUCCESS could be treated as a generic present lookup | Observed lookup-result vocabulary is checked; malformed structured logs fail explicitly | test_workflow_success_label_is_not_lookup_state; test_malformed_structured_log_fails | Distinguishing an observational claim from actual state remains semantic work | Yes |
| An existing evidence ID could be borrowed for an invented resource | Production validation requires a selected eligible observation with matching evidence ID, resource, system and state | test_known_evidence_id_for_wrong_resource_is_rejected; official sample/full reruns | A wrong extraction or identity match can still produce a wrong observation; this is not an authenticity proof | Yes |
| Invalid labels/fields and spreadsheet formula IDs | Strict output object/enum schemas and safe opaque identifier syntax; no normalization of accepted IDs | test_invalid_labels_and_missing_fields_rejected; test_output_identifier_cannot_inject_csv_formula; original schema tests | Identifier limits are engineering constraints, not new official schema claims | Yes |
| Raw parser/validation exceptions could echo a secret-like value | Public error boundary suppresses third-party exception bodies; known credential/email patterns redacted; evaluator/packager CLI exceptions also sanitized | test_exception_does_not_echo_secret; test_diagnostics_redact_secret_sentinel | Pattern redaction is not complete DLP; arbitrary unlabeled secrets may be unrecognizable | Yes |
| Extracted credential-like text could enter a new cache file | Recognized credential-like text bypasses caching; existing v2 entries with such text are invalidated without replay | test_credential_like_document_text_is_not_cached | Source input and worker memory still contain source text; old arbitrary files are not scanned globally | Yes |
| Native PDF/OCR could hang with no enforceable deadline | One child process per document, default 60-second timeout (configurable up to 300), zero automatic retries, controlled failure | test_document_timeout_is_one_attempt_and_no_success; real worker timeout observed; all supplied documents later completed | Workers retain the user's OS privileges; no process memory quota or whole-run wall-clock limit | Yes, scoped |
| Missing local models/parsers could cause a fabricated fallback | Missing bundled model files/parser failures abort; no downloads, substitutes or success fallback | test_unavailable_parser_or_models_fail (fault injection); supplied real models executed | Fault injection checks handling; it is not exhaustive testing of native dependency failures | Yes, scoped |
| Worker inherited unnecessary credentials | Worker environment contains only startup/native-runtime paths and UTF-8 settings | test_no_credential_env_in_worker | Same-user OS access and DLL search/supply-chain risks remain | Yes |
| Cache corruption/truncation could alter evidence text | Versioned source/text hashes, strict envelope parsing, atomic entries; regenerate from original when corrupt; --no-cache available | test_corrupted_cache_is_reextracted | Hashes detect corruption, not malicious recomputation by a cache writer; use trusted cache or --no-cache | Yes, scoped |
| Accidental loss of output/archive on interrupted replacement | Unique temporary files, verification then atomic replacement, cleanup on failure | test_output_failure_preserves_previous_file; test_packaging_failure_preserves_previous_archive | Disk loss, filesystem-specific durability and multi-file diagnostic transactions remain outside the guarantee | Yes |
| Broad archive allowlist could include secrets.txt | Explicit source/report member rules; unlisted text/config files excluded; symlink sources rejected | test_unlisted_text_file_is_not_packaged; final archive inspection | Trusted source files still need review; no claim of comprehensive secret scanning | Yes |
| SQL could attach files or load native extensions | In-memory DB, SQLite authorizer, restricted functions/PRAGMA, instruction and elapsed-time budgets | test_sql_cannot_load_extension; original test_sql_attachment_rejected | Native SQLite bugs and resource use within allowed bounds remain possible | Yes |
| Embedded SQL JSON could name a different resource from its table row | Strict embedded JSON and row/resource consistency check | test_sql_embedded_resource_must_match_row | Valid-looking but forged source facts cannot be authenticated | Yes |
| Resource exhaustion or runaway retries | File 64 MiB, dataset 512 MiB, CSV 100k rows, JSON depth 64/node 500k limits; PDF 100 pages, image 20M pixels, extracted text 2M chars; finite passes; no retries | test_file_budget; test_deep_json_budget; test_nonfinite_timeout_is_rejected; timeout test | Bounds are not a full resource sandbox; expensive valid-size artifacts and large retrieval workloads remain possible | Partly: boundaries tested; not exhaustive load testing |
| Hosted-model credentials, 429s and provider outages | Not applicable: no provider interface, SDK calls, credentials or hosted model is used | Source inspection; all fixtures and full runs use zero hosted calls | Reassess if a provider is introduced later | N/A |
| Unauthorized live deletion/remediation | Not applicable: remediation operations are serialized plans only | Source inspection; no action connector or executor exists | Generated plans still need semantic review before any future executor uses them | N/A |

## Reliability observations and retained limitations

The first document-worker evaluation timed out on a valid screenshot at the
60-second deadline and correctly stopped without success. Two isolated manual
follow-ups on that same screenshot completed in approximately 5.54 and 4.81
seconds. The runtime cause of the first delay was not established; no causal
explanation or automatic retry is claimed. The next artifact run completed all
supplied documents, and cached before/after predictions were identical.
The SQLite elapsed-time guard is separately covered by
test_sql_deadline_interrupts_work using a controlled clock and real recursive SQL.

One initial write guard rejected an existing valid custom-dataset integration
fixture because its new output lived alongside fixture inputs. The guard was
narrowed to prevent replacement of existing supplied assets while allowing new
custom output locations. The original integration test passes unchanged.

Worker parsing uses capture pipes, no shell, a minimal environment and local
bundled OCR weights. That is process separation, **not** an OS sandbox or an
internet firewall. Native library security and peak memory use are not fully
verified. SQL is separately limited, and the bounded orchestration has no
autonomous retry/agent loop. Legitimate resource evidence and policy application
remain imperfect: the pre-existing 103 unresolved cases and 240 coverage
warnings still prevent final output.csv publication.

## Reproduction and operation

Run the security test command above and the complete suite with
`.venv\Scripts\python.exe -m unittest discover -s code/tests -v`.
For an independently re-extracted run use
`.venv\Scripts\python.exe code/main.py --no-cache --diagnostics runs/security-cold`.
`--document-timeout SECONDS` accepts finite values greater than zero and at most
300; the default is 60. These engineering budgets comfortably exceed the
supplied artifact sizes but are not official challenge runtime limits.

Do not use a cache controlled by an untrusted writer. Keep the supplied dataset
and application source read-only to the runtime where the execution environment
supports it. Review generated plans before connecting any future live executor.
No perfect-security, complete-evidence, or final-submission claim is made.
