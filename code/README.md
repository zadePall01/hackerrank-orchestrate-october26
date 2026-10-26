# Ghost Data Still Exists: offline audit pipeline

## Current readiness

This implementation is **not submission-ready**. It executes all requests and
reports unresolved cases explicitly. The supplied evidence does not currently
let this implementation ground every account resource ID. It does not guess
ownership from identifier numbering, row position, or workflow timestamps.
When any case is unresolved or has an incomplete-coverage warning, the CLI exits with code 2 and refuses to publish
`output.csv`. Inspect `runs/full/diagnostics.md` and the evaluation report.
Partial predictions are diagnostic artifacts, not a valid 518-row submission.
To explicitly export the available candidates to root `output.csv` despite
unresolved cases, run `.venv\Scripts\python.exe code/main.py --allow-partial`.
This still exits **2**, omits unresolved cases rather than inventing statuses,
and writes `output.csv.partial.md` explaining the limitations. Unresolved IDs
and reasons remain in `runs/latest/diagnostics.md`. Use `--overwrite` explicitly
when replacing an existing generated CSV. The default strict behavior is unchanged.
The latest policy-aware run produces 381 diagnostic candidates; 137 cases remain
unresolved and 441 coverage/policy warnings block publication. Public exact rows
improved from 8/32 to 9/32 after explicit resource-edge traversal.
See `code/evaluation/independent_review.md` for measured before/after results.

## Setup

Tested with Windows PowerShell and Python 3.14.6. Python 3.11+ language features
are used; dependency wheel availability on other Python/OS versions is not
verified. Create the environment outside `code/`:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r code/requirements.txt
.venv\Scripts\python.exe code/main.py --check
.venv\Scripts\python.exe -m unittest discover -s code/tests -v
.venv\Scripts\python.exe code/evaluation/main.py --samples
.venv\Scripts\python.exe code/main.py --diagnostics runs/full
.venv\Scripts\python.exe code/package.py
```

On macOS/Linux replace `.venv\Scripts\python.exe` with `.venv/bin/python`.
Dependency installation needs package access or a separately prepared wheelhouse.
After installation, execution uses no network, API, credentials, or hosted LLM.
OCR weights are bundled in RapidOCR and their presence is checked explicitly.
No environment variables are required. No credentials are accepted or logged.

Use `--dataset PATH` for another dataset directory, `--requests
sample_deletion_requests.csv` for public samples, `--case CASE_ID` for a vertical
slice, `--output PATH` for output, and `--overwrite` to explicitly replace an
existing generated output. Provided dataset assets are never modified.
Paths default relative to the source repository, not the working directory.

## Architecture and trust boundaries

`audit/inputs.py` validates public schemas and paths. `extract.py` reads SQL in
an isolated in-memory SQLite database, JSON snapshots/service exports, correlated
log traces, text, PDF text and local OCR. SQL attachment and external functions
are denied and a SQLite instruction budget prevents unlimited execution.
`identity.py` links exact current/historical identifiers without name merging.
`state.py` filters capture and observation times, retrieves grounded resource
links, and reconciles observations. `policy.py` applies supplied actions and
`planner.py` produces the fixed official operation sequence. `contracts.py`
validates output. Dataset prose is data and cannot issue tools or override policy.

Successful operation results are not resource-state proofs. An absent profile
needs a subject-linked resource ID plus a suitable readback or collection scope.
Anonymous resources without a subject link are not assigned to requests.
Contradictory simultaneous observations, missing identifiers and unknown intent
raise explicit unresolved errors rather than generating success rows.
An established downstream violation may still produce an INCOMPLETE candidate
without account coverage; that limited plan is marked in diagnostics and cannot
pass the final publication gate. Replica timelines remain independent of newer
primary observations. Partial JSON collections do not prove resource absence.

No general agent loop or provider interface is included: no generative-model
capability or credentials were verified, and adding a dormant SDK wrapper would
not close an evidence-linkage gap. The local OCR models provide neural image
interpretation. Model retries are therefore inapplicable. Local extraction errors
are deterministic and fail immediately; no silent retries or skipped files.

## Outputs and evaluation

A successful full run writes exactly the official root `output.csv` header and
518 sorted case rows. Diagnostics contain coverage, errors, dataset fingerprint,
and measured runtime. `runs/extraction-cache/` stores only content-addressed
extracted artifact text, not decisions or labels; omit it to test fresh extraction.
For a cold run use `--cache runs/fresh-cache` with a new directory name.
Use `--no-cache` to bypass cached text entirely. Document parsing runs in a
separate process with a 60-second deadline; `--document-timeout` can select a
finite deadline up to 300 seconds. A timeout or missing local parser/model fails
explicitly without retries. Cache v2 checks source/text hashes for corruption;
it is not authenticated against a malicious local cache writer. Credential-like
text is not persisted in new cache entries. See `code/evaluation/security_audit.md`
for the measured threat audit and residual risks.

Sample reference answers are loaded only by the evaluator, after predictions.
Missing cases count as wrong. The Markdown evaluation report defines local
metrics explicitly; official scoring weights and hidden accuracy are unknown.
Four custom cases plus schema, temporal, identity, SQL-security, and ordering
tests are executable using standard-library unittest. Usage reports distinguish
zero hosted-generative tokens/cost from non-generative OCR and unmeasured local
compute. Development-assistant usage is outside pipeline usage.

## Packaging and submission

`code/package.py` uses an explicit allowlist, excludes data, caches, environments,
secrets, and archives, and verifies archive contents. It places identical reports
at `code/evaluation/` and root `evaluation/` to satisfy the supplied path variants.
The packaged root README is this implementation README; the supplied repository
README is preserved unchanged on disk. `code.zip` can be inspected while the
pipeline remains blocked, but is not a claim of submission readiness.

`output.csv` and root `log.txt` are separate submission artifacts. Do not package
the dataset. For the additional `agent-trace.zip` requirement, finish and quit all
challenge sessions before copying original relevant rollout files, review/redact
them, and package separately as instructed by `agent_trace_instructions.md`.
This active session cannot yet be exported as a complete finished trace.

Official challenge/submission URL:
https://www.hackerrank.com/contests/hackerrank-orchestrate-october26/challenges/ghost-data-still-exists
