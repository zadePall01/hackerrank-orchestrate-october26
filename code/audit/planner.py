"""Deterministic conversion of assessed resources into the official step sequence."""
import json
from .contracts import Observation, OPERATIONS, step_key
from .policy import Policy


def plan(case_id: str, observations: list[Observation], policy: Policy, audit_at: str | None = None) -> dict[str, str]:
    assessed = [(o, *policy.assess(o,audit_at)) for o in observations]
    incomplete = any(remedy for _, _, _, remedy in assessed)
    steps = []
    def add(phase, operation, state, obs, evidence=''):
        steps.append(dict(step_no=0, phase=phase, system_id=obs.system, resource_id=obs.resource, operation=operation, state=state, evidence_id=evidence))
    for obs, verification, target, remedy in assessed:
        if remedy:
            finding = {'DISABLE_DATA_FLOW': 'REPORT_ACTIVE_DATA_FLOW', 'BLOCK_RESTORE': 'REPORT_RESTORE_RISK', 'DELETE_RECORD': 'REPORT_REMAINING_RECORD', 'REDACT_RECORD': 'REPORT_EXPOSED_PII', 'ANONYMIZE_RECORD': 'REPORT_EXPOSED_PII'}[remedy]
            add('FINDING', finding, 'ACTIVE' if remedy in {'DISABLE_DATA_FLOW', 'BLOCK_RESTORE'} else 'PRESENT', obs, obs.evidence_id)
            add('REMEDIATION', remedy, dict(OPERATIONS['REMEDIATION'])[remedy], obs)
        add('VERIFICATION', verification, target, obs, '' if incomplete else obs.evidence_id)
    steps.sort(key=step_key)
    for number, step in enumerate(steps, 1): step['step_no'] = number
    return dict(case_id=case_id, deletion_status='INCOMPLETE' if incomplete else 'COMPLETE', steps_json=json.dumps(steps, ensure_ascii=False, separators=(',', ':')))
