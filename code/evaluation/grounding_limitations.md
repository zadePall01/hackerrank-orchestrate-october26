# Grounding limitations and missing information

The pipeline does not read organizer-only files or sample labels to make
predictions. No additional resource/subject mapping file was found among the
supplied participant files. All 94 manifest targets exist.

## Concrete public-sample examples

- `case_01`: the request resolves to its current identity, but no eligible
  evidence explicitly associates that subject with `account_001`. The activity
  row for `account_001` contains its resource ID and deletion claim, without a
  subject identifier. The SQL snapshot can show that a resource is absent, but
  cannot by itself establish who owned an absent row.
- `case_21`: the reference expects verification of `analytics_5335`. Its eligible
  service-export record has null identifying fields; the anonymization activity
  names the resource without identifying the person. Matching anonymous records
  by row position, numerical patterns, or nearby workflow time would be a guess.
- `case_03`: direct account and security evidence is discovered, but the
  reference additionally expects an anonymized analytics resource whose subject
  link this implementation cannot establish. Therefore even resolved-case
  coverage is not a guarantee of complete canonical step coverage.

These observations identify a limitation of this implementation's grounded
retrieval, not proof that no possible interpretation of the supplied data could
resolve a case. Additional participant-visible catalog links, historical
resource ownership records, or official clarification of permitted linkage
inference would resolve the uncertainty. No fictitious mapping filename or
official fallback status is assumed.

## Explicit limitations

- PDF text and all PNGs are extracted, but only supported semantic references
  become observations. General UI-table parsing and OCR confidence validation
  are not complete; artifact text extraction is not equivalent to fact coverage.
- No generative model interprets arbitrary language or novel artifact layouts.
  Unknown intent and schemas fail explicitly.
- Physical replica scopes are retained, but general distributed-state conflict
  reconciliation and source/downstream dependency modeling remain limited.
- Exact canonical ordering follows the challenge statement; the repository's
  dependency-order instruction can conflict with that fixed order.
- Full-dataset correctness cannot be measured without hidden labels. Partial
  predictions and the source archive are not a valid final submission.

Inspect `evaluation_report.md`, `usage_report.md`, and the generated diagnostics
for measured results. Do not replace unresolved cases with COMPLETE, INCOMPLETE,
NOT_APPLICABLE, or invented identifiers merely to reach the required row count.
