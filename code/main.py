"""CLI for the offline deletion audit. No sample answers enter predictions."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
import time
import importlib.metadata
import io

from audit.contracts import AuditError, OUTPUT_FIELDS, validate_output
from audit.extract import Extractor
from audit.identity import Identities
from audit.inputs import load_inputs, fingerprint
from audit.intent import authorizes_deletion
from audit.planner import plan
from audit.policy import Policy
from audit.reporting import usage_report, write_diagnostics
from audit.state import StateIndex
from audit.security import public_error, guard_destination, atomic_text

ROOT = Path(__file__).resolve().parents[1]


def run(dataset: Path, request_file: str, case_ids: set[str] | None = None, cache_dir: Path | None = None, document_timeout: float = 60) -> tuple[list[dict], dict, dict]:
    started = time.monotonic()
    if cache_dir is not None: guard_destination(cache_dir,dataset,ROOT)
    inputs = load_inputs(dataset, request_file)
    requests = inputs['requests']
    if case_ids:
        requests = [r for r in requests if r['case_id'] in case_ids]
        if {r['case_id'] for r in requests} != case_ids: raise AuditError('Unknown requested case ID')
    extractor = Extractor(cache_dir,document_timeout)
    extractor.run(dataset, inputs['evidence_files.csv'])
    extractor.catalog_artifacts(inputs['evidence_files.csv'], inputs['system_activity.csv'])
    identities = Identities(inputs['user_identities.csv'], inputs['user_audit_log.csv'])
    policy = Policy(inputs['deletion_rules.csv'])
    index = StateIndex(extractor, identities, inputs['system_activity.csv'], policy)
    rows, errors, warnings, grounding = [], [], [], {}
    for request in sorted(requests, key=lambda r: r['case_id']):
        try:
            if not authorizes_deletion(request['request_text']):
                row = dict(case_id=request['case_id'], deletion_status='NOT_APPLICABLE', steps_json='[]')
                grounding[request['case_id']]=[]
            else:
                observations = index.resolve(request)
                row = plan(request['case_id'], observations, policy,request['audit_at'])
                grounding[request['case_id']]=observations
                unknown=[(o,policy.applicability(o,request['audit_at'])) for o in observations if policy.applicability(o,request['audit_at']).status=='UNKNOWN']
                if unknown:
                    known_violation=any((o.category in {'DATA_FLOW','BACKUP_ARCHIVE'} and o.state=='ACTIVE') or (policy.applicability(o,request['audit_at']).status=='APPLICABLE' and policy.assess(o,request['audit_at'])[2] is not None) for o in observations)
                    if row['deletion_status']=='COMPLETE' or not known_violation:raise AuditError('Insufficient policy-applicability evidence to establish this deletion assessment')
                    for obs,condition in unknown:
                        warnings.append(dict(case_id=request['case_id'],warning=f'Policy applicability unresolved for {obs.system}/{obs.resource}: {condition.reason}; candidate template is not an authorized remediation plan'))
                if not index.has_account_coverage(observations):
                    if row['deletion_status'] == 'COMPLETE':
                        raise AuditError('Insufficient account coverage to establish COMPLETE; no account resource ID/state grounded')
                    warnings.append(dict(case_id=request['case_id'],warning='Grounded violation establishes INCOMPLETE, but account coverage is missing; plan covers discovered resources only'))
            rows.append(row)
        except AuditError as exc:
            errors.append(dict(case_id=request['case_id'], error=public_error(exc)))
    evidence_times = {r['file_id']: r['captured_at'] for r in inputs['evidence_files.csv']}
    evidence_times.update({r['activity_id']: r['event_time'] for r in inputs['system_activity.csv']})
    evidence_times.update({r['audit_id']: r['event_time'] for r in inputs['user_audit_log.csv']})
    resolved_ids = {r['case_id'] for r in rows}
    validate_output(rows, [r for r in requests if r['case_id'] in resolved_ids], evidence_times,grounding)
    digest = fingerprint(dataset, inputs)
    diagnostics = dict(requests=len(requests), resolved=len(rows), errors=errors, warnings=warnings, coverage=extractor.coverage,
                       dataset_sha256=digest, elapsed_seconds=time.monotonic()-started,
                       observations=len(extractor.observations), generative_model_calls=0,
                       ocr_calls=extractor.ocr_calls, document_cache_hits=extractor.document_cache_hits,
                       python_version=sys.version, selected_case_ids=sorted(case_ids) if case_ids else None,
                       dependency_versions={name: importlib.metadata.version(name) for name in ('pypdf','rapidocr','onnxruntime','pillow')})
    return rows, diagnostics, dict(requests=requests, evidence_times=evidence_times,grounding=grounding)


def write_csv(path: Path, rows: list[dict]) -> None:
    stream=io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=OUTPUT_FIELDS, lineterminator='\n')
    writer.writeheader(); writer.writerows(rows)
    atomic_text(path,stream.getvalue())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=ROOT/'dataset')
    parser.add_argument('--requests', default='deletion_requests.csv')
    parser.add_argument('--output', type=Path, default=ROOT/'output.csv')
    parser.add_argument('--diagnostics', type=Path, default=ROOT/'runs/latest')
    parser.add_argument('--case', action='append')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--overwrite', action='store_true')
    parser.add_argument('--allow-partial', action='store_true',
                        help='Export diagnostic candidate rows despite unresolved cases; exit 2 and not submission-ready')
    parser.add_argument('--cache', type=Path, default=ROOT/'runs/extraction-cache')
    parser.add_argument('--no-cache',action='store_true')
    parser.add_argument('--document-timeout',type=float,default=60)
    args = parser.parse_args()
    try:
        for destination in (args.output,args.diagnostics,*(() if args.no_cache else (args.cache,))): guard_destination(destination,args.dataset,ROOT)
        if args.output.exists() and not args.overwrite and not args.check:
            raise AuditError('Output exists; use --overwrite explicitly')
        if args.check:
            data = load_inputs(args.dataset, args.requests)
            from pypdf import PdfReader
            from rapidocr import RapidOCR
            import onnxruntime
            print(f'Preflight passed: {len(data["requests"])} requests; {len(data["evidence_files.csv"])} manifest files; PDF/OCR imports available')
            return 0
        rows, diagnostics, context = run(args.dataset, args.requests, set(args.case or []) or None, None if args.no_cache else args.cache,args.document_timeout)
        write_diagnostics(args.diagnostics, diagnostics)
        published = not diagnostics['errors'] and not diagnostics.get('warnings')
        if published:
            validate_output(rows, context['requests'], context['evidence_times'],context['grounding'])
            if args.requests == 'deletion_requests.csv' and not args.case and len(rows) != 518:
                raise AuditError('Official full run must contain 518 rows')
            write_csv(args.output, rows)
        else:
            write_csv(args.diagnostics/'resolved_predictions.csv', rows)
            if args.allow_partial:
                notice = args.output.with_suffix(args.output.suffix + '.partial.md')
                guard_destination(notice, args.dataset, ROOT)
                atomic_text(notice, f'# Partial diagnostic export - NOT SUBMISSION-READY\n\n'
                            f'{len(rows)} candidate rows exported from {diagnostics["requests"]} requests.\n'
                            f'{len(diagnostics["errors"])} unresolved cases omitted; '
                            f'{len(diagnostics.get("warnings", []))} warnings remain.\n'
                            f'Candidate plans can have unproved policy conditions or incomplete coverage.\n'
                            f'No fallback statuses or resource IDs were invented.\n'
                            f'Unresolved case IDs, reasons and warnings: {args.diagnostics / "diagnostics.md"}.\n')
                write_csv(args.output, rows)
        if args.requests == 'deletion_requests.csv' and not args.case:
            output_hash = hashlib.sha256(args.output.read_bytes()).hexdigest() if published else ''
            usage_report(ROOT/'code/evaluation/usage_report.md', diagnostics['requests'], diagnostics['elapsed_seconds'], published, diagnostics['dataset_sha256'], output_hash, diagnostics['ocr_calls'], diagnostics['document_cache_hits'])
        print(json.dumps({k: diagnostics[k] for k in ('requests','resolved','elapsed_seconds','observations')}, indent=2))
        if not published:
            if args.allow_partial:
                print(f'PARTIAL DIAGNOSTIC EXPORT: {args.output}; {len(rows)} rows. NOT SUBMISSION-READY.', file=sys.stderr)
            print(f'UNRESOLVED: {len(diagnostics["errors"])} cases; {len(diagnostics.get("warnings", []))} coverage warnings. Final output not published. See {args.diagnostics / "diagnostics.md"}', file=sys.stderr)
            return 2
        print(f'Validated output: {args.output}')
        return 0
    except (AuditError, OSError, ImportError, ValueError) as exc:
        print(f'AUDIT FAILED: {public_error(exc)}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
