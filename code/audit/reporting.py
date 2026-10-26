"""Reproducible diagnostics and honest inference usage reporting."""
from pathlib import Path
import json
from .security import public_error, atomic_text
from .contracts import AuditError


def write_diagnostics(directory: Path, payload: dict) -> None:
    payload=dict(payload)
    payload['errors']=[dict(row,error=public_error(AuditError(row['error']))) for row in payload['errors']]
    payload['warnings']=[dict(row,warning=public_error(AuditError(row['warning']))) for row in payload.get('warnings',[])]
    directory.mkdir(parents=True, exist_ok=True)
    atomic_text(directory/'run.json',json.dumps(payload, indent=2, ensure_ascii=False))
    lines = ['# Audit run diagnostics', '', f"Requests: {payload['requests']}", f"Resolved: {payload['resolved']}", f"Unresolved: {len(payload['errors'])}", f"Dataset SHA-256: `{payload['dataset_sha256']}`", '', '## Unresolved cases', '']
    for item in payload['errors']: lines.append(f"- {item['case_id']}: {item['error']}")
    lines += ['', '## Coverage warnings', '']
    for item in payload.get('warnings', []): lines.append(f"- {item['case_id']}: {item['warning']}")
    lines += ['', '## Evidence extraction', '', '| Evidence | Format | Observations | Text extracted |', '|---|---|---:|---|']
    for r in payload['coverage']: lines.append(f"| {r['file_id']} | {r['format']} | {r['observations']} | {r['text_extracted']} |")
    atomic_text(directory/'diagnostics.md','\n'.join(lines)+'\n')


def usage_report(path: Path, count: int, elapsed: float, published: bool, fingerprint: str, output_hash: str = '', ocr_calls: int = 0, cache_hits: int = 0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'''# Final full-dataset run usage

Run requests: {count}. Elapsed seconds: {elapsed:.3f}.
Final output published: {published}. Output SHA-256: {output_hash or 'not produced'}.
Dataset fingerprint: `{fingerprint}`.

| Provider / model | Calls | Input tokens | Output tokens | Total tokens | Tokens/request | Estimated cost USD | Cost/request USD |
|---|---:|---:|---:|---:|---:|---:|---:|
| No generative model used | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Overall generative inference | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

PDF extraction uses pypdf. Local OCR uses the RapidOCR package's bundled
PP-OCRv6 detection/recognition and mobile orientation models through ONNX Runtime.
These are local non-generative models: token counts do not apply. Actual local
OCR invocations in this run: {ocr_calls}. Each invokes bundled detection,
orientation, and recognition networks; recognition batches vary with image text.
Document extraction cache hits: {cache_hits}. These are not hosted model API
calls. No credentials, inference service, or runtime network access is
used. Local compute and electricity costs are not measured and are not included
in the zero hosted-inference cost. Development-assistant usage is separate from
the submitted pipeline run and is not represented as pipeline inference.

An unpublished output means this run did not satisfy the submission contract;
see diagnostics rather than interpreting failure as a successful full run.
''', encoding='utf-8')
