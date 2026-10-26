"""Public output contract and provenance-preserving internal records."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import json

REQUEST_FIELDS = ['case_id', 'email', 'requested_at', 'reported_status', 'reported_at', 'audit_at', 'request_text']
OUTPUT_FIELDS = ['case_id', 'deletion_status', 'steps_json']
STEP_FIELDS = {'step_no', 'phase', 'system_id', 'resource_id', 'operation', 'state', 'evidence_id'}
OPERATIONS = {
    'FINDING': [('REPORT_REMAINING_RECORD', 'PRESENT'), ('REPORT_EXPOSED_PII', 'PRESENT'), ('REPORT_ACTIVE_DATA_FLOW', 'ACTIVE'), ('REPORT_RESTORE_RISK', 'ACTIVE')],
    'REMEDIATION': [('DISABLE_DATA_FLOW', 'DISABLED'), ('BLOCK_RESTORE', 'BLOCKED'), ('DELETE_RECORD', 'ABSENT'), ('REDACT_RECORD', 'REDACTED'), ('ANONYMIZE_RECORD', 'ANONYMIZED')],
    'VERIFICATION': [('VERIFY_RECORD_ABSENT', 'ABSENT'), ('VERIFY_RECORD_PRESENT', 'PRESENT'), ('VERIFY_RECORD_REDACTED', 'REDACTED'), ('VERIFY_RECORD_ANONYMIZED', 'ANONYMIZED'), ('VERIFY_DATA_FLOW_DISABLED', 'DISABLED'), ('VERIFY_RESTORE_BLOCKED', 'BLOCKED')],
}


class AuditError(ValueError):
    """A case cannot be resolved without inventing facts."""


def timestamp(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise AuditError(f'Timestamp has no timezone: {value!r}')
    return dt


@dataclass(frozen=True)
class Observation:
    evidence_id: str
    captured_at: str
    observed_at: str
    system: str
    resource: str
    category: str
    state: str
    attributes: dict[str, Any] = field(default_factory=dict)
    locator: str = ''
    scope: str = ''

    def eligible(self, cutoff: str) -> bool:
        return timestamp(self.captured_at) <= timestamp(cutoff) and timestamp(self.observed_at) <= timestamp(cutoff)


def step_key(step: dict[str, Any]) -> tuple:
    phase = step['phase']
    return (list(OPERATIONS).index(phase), [x[0] for x in OPERATIONS[phase]].index(step['operation']), step['system_id'], step['resource_id'])


def validate_output(rows: list[dict[str, str]], requests: list[dict[str, str]], evidence_times: dict[str, str], grounding: dict[str,list[Observation]] | None = None) -> None:
    if not isinstance(rows,list) or any(not isinstance(row,dict) or set(row)!=set(OUTPUT_FIELDS) or any(not isinstance(v,str) for v in row.values()) for row in rows):
        raise AuditError('Invalid output row schema')
    expected = sorted(r['case_id'] for r in requests)
    if len(set(expected)) != len(expected) or [r['case_id'] for r in rows] != expected:
        raise AuditError('Output case IDs must exactly match input IDs, uniquely and in sorted order')
    cutoffs = {r['case_id']: r['audit_at'] for r in requests}
    for row in rows:
        if not isinstance(row,dict) or set(row) != set(OUTPUT_FIELDS) or any(not isinstance(v,str) for v in row.values()) or row['deletion_status'] not in {'COMPLETE', 'INCOMPLETE', 'NOT_APPLICABLE'}:
            raise AuditError('Invalid output row schema or label')
        from .security import strict_json
        steps = strict_json(row['steps_json'])
        if not isinstance(steps, list):
            raise AuditError('steps_json must be an array')
        status = row['deletion_status']
        if status == 'NOT_APPLICABLE' and steps:
            raise AuditError('Non-deletion request has steps')
        if status != 'NOT_APPLICABLE' and not steps:
            raise AuditError('Deletion assessment has no evidence-backed coverage')
        for number, step in enumerate(steps, 1):
            if not isinstance(step, dict) or set(step) != STEP_FIELDS or type(step['step_no']) is not int or step['step_no'] != number:
                raise AuditError('Invalid step schema or numbering')
            if any(not isinstance(step[k], str) for k in STEP_FIELDS - {'step_no'}):
                raise AuditError('Step string field has a non-string value')
            if not step['system_id'] or not step['resource_id']:
                raise AuditError('Empty resource/system ID')
            if (step['operation'], step['state']) not in OPERATIONS.get(step['phase'], []):
                raise AuditError('Invalid phase/operation/state combination')
            if status == 'COMPLETE' and step['phase'] != 'VERIFICATION':
                raise AuditError('Complete case contains non-verification steps')
            citation_required = status == 'COMPLETE' or step['phase'] == 'FINDING'
            ev = step['evidence_id']
            if citation_required:
                if ev not in evidence_times or timestamp(evidence_times[ev]) > timestamp(cutoffs[row['case_id']]):
                    raise AuditError('Missing, unknown, or future citation')
                if grounding is not None and not any(o.evidence_id==ev and o.system==step['system_id'] and o.resource==step['resource_id'] and o.state==step['state'] and o.eligible(cutoffs[row['case_id']]) for o in grounding.get(row['case_id'],[])):
                    raise AuditError('Citation does not ground this resource/state at the cutoff')
            elif ev:
                raise AuditError('Future work must have an empty citation')
        if steps != sorted(steps, key=step_key):
            raise AuditError('Noncanonical step order')
        if status == 'INCOMPLETE' and {s['phase'] for s in steps} != set(OPERATIONS):
            raise AuditError('Incomplete case needs findings, remediation, and verification')
