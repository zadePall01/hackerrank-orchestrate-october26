"""Stable before/after experiments; public labels are evaluation-only inputs."""
from __future__ import annotations
import argparse
import importlib.util
import json
import platform
from pathlib import Path
import subprocess
import sys

CODE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE))
from main import ROOT, run, write_csv
from audit.inputs import read_csv
from audit.reporting import write_diagnostics

spec = importlib.util.spec_from_file_location('sample_evaluator', CODE/'evaluation/main.py')
evaluator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluator)


def criterion_proxies(rows: list[dict], reference: list[dict]) -> dict:
    """Local observable proxies, not claimed official scoring formulas."""
    predictions = {r['case_id']: r for r in rows}
    found = required = treatment_hits = treatment_total = citation_hits = citation_total = 0
    for ref in reference:
        actual = json.loads(predictions.get(ref['case_id'], {}).get('steps_json', '[]'))
        expected = json.loads(ref['steps_json'])
        resources = {(s['system_id'], s['resource_id']) for s in actual}
        expected_resources = {(s['system_id'], s['resource_id']) for s in expected}
        found += len(resources & expected_resources); required += len(expected_resources)
        treatments = {(s['phase'],s['operation'],s['system_id'],s['resource_id'],s['state']) for s in actual}
        for step in expected:
            key = (step['phase'],step['operation'],step['system_id'],step['resource_id'],step['state'])
            treatment_total += 1; treatment_hits += key in treatments
            if step['evidence_id']:
                citation_total += 1
                citation_hits += any((s['phase'],s['operation'],s['system_id'],s['resource_id'],s['state']) == key and s['evidence_id'] == step['evidence_id'] for s in actual)
    return dict(reference_resource_recall=found/required if required else 1,
                reference_treatment_recall=treatment_hits/treatment_total if treatment_total else 1,
                reference_citation_recall=citation_hits/citation_total if citation_total else 1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label', required=True)
    args = parser.parse_args()
    if not args.label.replace('_','').isalnum(): parser.error('Label must be alphanumeric/underscore')
    target = ROOT/'runs/independent_audit/experiments'/args.label
    target.mkdir(parents=True, exist_ok=False)
    cache = ROOT/'runs/extraction-cache'
    samples, sd, _ = run(ROOT/'dataset','sample_deletion_requests.csv',cache_dir=cache)
    full, fd, _ = run(ROOT/'dataset','deletion_requests.csv',cache_dir=cache)
    write_diagnostics(target/'samples',sd); write_diagnostics(target/'full',fd)
    write_csv(target/'samples/resolved_predictions.csv',samples)
    write_csv(target/'full/resolved_predictions.csv',full)
    reference = read_csv(ROOT/'dataset/sample_output.csv')
    metrics = evaluator.metrics(samples,reference)
    proxies = criterion_proxies(samples,reference)
    process = subprocess.run([sys.executable,'-m','unittest','discover','-s',str(CODE/'tests'),'-v'],cwd=ROOT,capture_output=True,text=True,timeout=120)
    (target/'tests.txt').write_text(process.stdout+process.stderr,encoding='utf-8')
    summary = dict(label=args.label,command=f'{sys.executable} code/evaluation/audit_run.py --label {args.label}',
                   python=sys.version,platform=platform.platform(),dependencies=fd['dependency_versions'],
                   sample_metrics=metrics,criterion_proxies=proxies,tests_exit_code=process.returncode,
                   full_resolved=len(full),full_unresolved=len(fd['errors']),full_elapsed_seconds=fd['elapsed_seconds'],
                   full_dataset_sha256=fd['dataset_sha256'],sample_elapsed_seconds=sd['elapsed_seconds'],
                   output_location=str(target),official_full_output_valid=not fd['errors'] and not fd.get('warnings'),
                   full_coverage_warnings=len(fd.get('warnings', [])),
                   full_schema_valid_resolved_rows=len(full),generative_model_calls=0)
    (target/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k not in {'sample_metrics','dependencies'}},indent=2))
    print(json.dumps({k:v for k,v in metrics.items() if k!='failures'},indent=2))
    return process.returncode


if __name__ == '__main__':
    from audit.security import public_error
    try: raise SystemExit(main())
    except Exception as exc:
        print(f'EVALUATION FAILED: {public_error(exc)}',file=sys.stderr)
        raise SystemExit(2)
