"""Evaluate without allowing reference answers into the prediction pipeline."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys
import unittest

CODE = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(CODE))
from main import ROOT, run, write_csv
from audit.inputs import read_csv
from audit.reporting import write_diagnostics


def metrics(predictions: list[dict], reference: list[dict]) -> dict:
    predicted={r['case_id']:r for r in predictions}
    status=sequence=exact=field_hits=field_total=tp=np=ng=0
    failures=[]
    for ref in reference:
        pred=predicted.get(ref['case_id'])
        truth=json.loads(ref['steps_json']); steps=json.loads(pred['steps_json']) if pred else []
        status += bool(pred and pred['deletion_status']==ref['deletion_status'])
        equal=bool(pred and steps==truth)
        sequence += equal
        exact += bool(equal and pred['deletion_status']==ref['deletion_status'])
        canonical=lambda s: tuple(sorted(s.items()))
        pc,gc=Counter(map(canonical,steps)),Counter(map(canonical,truth))
        tp+=sum((pc&gc).values()); np+=len(steps); ng+=len(truth)
        # Field accuracy aligns by phase, operation, system, resource. Missing
        # steps contribute seven incorrect fields; extra steps also penalize.
        key=lambda s: (s['phase'],s['operation'],s['system_id'],s['resource_id'])
        pm, gm = defaultdict(list), defaultdict(list)
        for step in steps: pm[key(step)].append(step)
        for step in truth: gm[key(step)].append(step)
        for k in pm.keys()|gm.keys():
            predicted_group, expected_group = pm[k], gm[k]
            field_total += 7 * max(len(predicted_group),len(expected_group))
            for a,b in zip(predicted_group,expected_group):
                field_hits += sum(a[f]==b[f] for f in b)
        if not (equal and pred['deletion_status']==ref['deletion_status']):
            failures.append(dict(case_id=ref['case_id'],expected_status=ref['deletion_status'],actual_status=pred['deletion_status'] if pred else 'UNRESOLVED',expected_steps=len(truth),actual_steps=len(steps)))
    n=len(reference)
    return dict(cases=n,resolved=len(predictions),status_correct=status,status_accuracy=status/n,exact_rows=exact,exact_row_accuracy=exact/n,sequence_accuracy=sequence/n,step_precision=tp/np if np else 0,step_recall=tp/ng if ng else 0,field_accuracy=field_hits/field_total if field_total else 1,matched_steps=tp,predicted_steps=np,reference_steps=ng,failures=failures)


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--samples',action='store_true'); parser.parse_args()
    rows,diagnostics,_=run(ROOT/'dataset','sample_deletion_requests.csv',cache_dir=ROOT/'runs/extraction-cache')
    directory=ROOT/'runs/samples'; write_diagnostics(directory,diagnostics); write_csv(directory/'resolved_predictions.csv',rows)
    reference=read_csv(ROOT/'dataset/sample_output.csv')
    result=metrics(rows,reference)
    suite=unittest.defaultTestLoader.discover(str(CODE/'tests'))
    tests=unittest.TextTestRunner(verbosity=1).run(suite)
    lines=['# Evaluation report','', '## Scope and metric definitions','',
      'Measured on all 32 public sample answers. Reference answers are loaded only after predictions are complete. Missing/unresolved cases count as incorrect; no hidden-dataset accuracy is available. These are local metrics, not the undisclosed official scoring formula.',
      '', 'Exact row accuracy requires matching status and the complete ordered step array. Sequence accuracy compares the complete step array, including citations and numbering. Step precision/recall uses exact seven-field step tuples. Field accuracy aligns on phase/operation/system/resource; unmatched steps contribute seven incorrect fields, including extra predictions.', '', '## Actual sample results','', '| Metric | Value |','|---|---:|']
    for key in ['cases','resolved','status_correct','status_accuracy','exact_rows','exact_row_accuracy','sequence_accuracy','step_precision','step_recall','field_accuracy','matched_steps','predicted_steps','reference_steps']:
        lines.append(f'| {key} | {result[key]} |')
    lines+=['','## Failures','', '| Case | Expected status | Actual status | Expected steps | Actual steps |','|---|---|---|---:|---:|']
    for f in result['failures']: lines.append(f"| {f['case_id']} | {f['expected_status']} | {f['actual_status']} | {f['expected_steps']} | {f['actual_steps']} |")
    lines+=['','## Participant-created evaluation cases','',
      'Executable definitions are in code/tests/test_audit.py (CustomEvaluationCases).',
      '- Surviving replica despite a successful workflow claim: expect INCOMPLETE and report/delete/verify the surviving profile.',
      '- Marketing opt-out with an account-preservation request: expect no deletion authorization.',
      '- Tombstone: stable reference without direct identifiers is compliant; exposed email requires redaction while retaining the reference.',
      '- Absent primary with an active restore path: expect INCOMPLETE and BLOCK_RESTORE before verification.',
      '',f'Automated tests actually executed: {tests.testsRun}; failures: {len(tests.failures)}; errors: {len(tests.errors)}; skipped: {len(tests.skipped)}.',
      '', '## Failures found and improvements made','',
      '- Initial vertical slice incorrectly used an unrelated later inventory to erase a surviving replica. Restricted absence scope to evidence grounded to the subject and added a regression test.',
      '- Snapshot bundles include nested operational histories. Added explicit extraction preserving record timestamps and manifest capture cutoffs.',
      '- Some absent/anonymous reference resources have no explicit participant-visible subject linkage found by this implementation. Such resources are not assigned by numeric suffix, array position, workflow timing, or sample answer.',
      '- Remaining extraction, linkage, and citation disagreements are visible in the table above and runs/samples/diagnostics.md. Sample agreement is not claimed as hidden accuracy.',
      '', '## Reproduction','', 'Run `.venv/Scripts/python.exe code/evaluation/main.py --samples` on Windows or `.venv/bin/python code/evaluation/main.py --samples` elsewhere. Install code/requirements.txt first. Raw-text extraction cache can be deleted to exercise PDF/OCR again. No network or credentials are needed after dependency installation.','']
    (CODE/'evaluation/evaluation_report.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='failures'},indent=2))
    return 0 if tests.wasSuccessful() else 1


if __name__=='__main__':
    from audit.security import public_error
    try: raise SystemExit(main())
    except Exception as exc:
        print(f'EVALUATION FAILED: {public_error(exc)}',file=sys.stderr)
        raise SystemExit(2)
