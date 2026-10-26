"""Supplied actions plus explicit applicability, without inventing fallback policy."""
from dataclasses import dataclass
import re
from .contracts import AuditError, Observation, timestamp


@dataclass(frozen=True)
class Applicability:
    status: str  # APPLICABLE, COMPLIANT, UNKNOWN, INAPPLICABLE (internal only)
    reason: str


class Policy:
    def __init__(self, rows: list[dict]):
        self.rules = {r['data_category']: r for r in rows}
        if len(self.rules) != len(rows): raise AuditError('Ambiguous category rules')
        if any(r['required_action'] not in {'DELETE', 'REDACT', 'ANONYMIZE', 'RETAIN'} for r in rows):
            raise AuditError('Unsupported policy action')

    def applicability(self, observation: Observation, audit_at: str | None = None) -> Applicability:
        category,attrs,state=observation.category,observation.attributes,observation.state
        cutoff=timestamp(audit_at or observation.observed_at)
        def result(status,reason):return Applicability(status,reason)
        def flag(*names):
            for name in names:
                if name in attrs:
                    value=attrs[name]
                    if value is None:continue
                    if isinstance(value,bool):return value
                    if str(value).casefold() in {'true','1','active'}:return True
                    if str(value).casefold() in {'false','0','inactive','released'}:return False
                    raise AuditError('Invalid policy applicability flag')
            return None
        if category=='DATA_FLOW':return result('APPLICABLE','Active copying must be disabled')
        if category not in self.rules:raise AuditError('No supplied rule for observed category')
        rule=self.rules[category]
        if rule['condition'].strip().casefold()=='always':return result('APPLICABLE','Unconditional supplied rule')
        if category in {'SECURITY_AUDIT_LOG','LEGAL_HOLD_RECORD'}:
            active=flag('within_retention','retention_active') if category=='SECURITY_AUDIT_LOG' else flag('hold_active','legal_hold_active','legal_hold_status')
            if active is False:return result('INAPPLICABLE','Supplied retention or legal hold is inactive; no fallback action is supplied')
            end=next((attrs[k] for k in ('retention_until','retained_until','hold_until') if attrs.get(k)),None)
            start=next((attrs[k] for k in ('retention_from','hold_from','hold_starts_at') if attrs.get(k)),None)
            try:
                end_time=timestamp(end) if end is not None else None
                start_time=timestamp(start) if start is not None else None
            except (TypeError,ValueError) as exc:raise AuditError('Invalid policy applicability interval') from exc
            if start_time is not None and start_time>cutoff:return result('INAPPLICABLE','Supplied retention/hold has not started at audit cutoff')
            if end_time is not None and end_time<cutoff:return result('INAPPLICABLE','Supplied retention/hold has ended at audit cutoff; no fallback action is supplied')
            if end_time==cutoff:return result('UNKNOWN','Inclusive/exclusive retention endpoint is not specified')
            if active is True or end is not None:return result('APPLICABLE','Retention/hold active at audit cutoff')
            return result('UNKNOWN','No supplied retention end or active-hold/retention marker')
        if category in {'ANALYTICS_PROFILE','PRODUCT_TELEMETRY'}:
            if state=='ANONYMIZED':return result('COMPLIANT','Record already irreversibly unlinked')
            if state=='PRESENT':return result('APPLICABLE','Observed attributable record')
            return result('UNKNOWN','Attributability/final record state is not established')
        if category=='SUPPORT_MESSAGE':
            shared=flag('shared_context','retention_required')
            if shared is False:return result('INAPPLICABLE','Shared retained conversation context explicitly absent; no fallback rule')
            context=str(attrs.get('message_text',attrs.get('message_excerpt','')))
            if shared is True or attrs.get('ticket_id') or re.search(r'\b(order|delivery|agent|ticket|refund|support|conversation)\b',context,re.I):return result('APPLICABLE','Shared ticket/order/conversation context observed')
            return result('UNKNOWN','Shared conversation context has not been established')
        if category=='SUPPORT_ATTACHMENT':
            exclusive=flag('subject_only','belongs_only_to_subject')
            if exclusive is False:return result('INAPPLICABLE','Attachment explicitly belongs to multiple subjects; no fallback rule')
            if exclusive is True or attrs.get('subject_count')==1:return result('APPLICABLE','Exclusive subject ownership established')
            return result('UNKNOWN','Exclusive subject ownership of attachment is unproven')
        if category=='EMAIL_DELIVERY_LOG':
            if state=='REDACTED':return result('COMPLIANT','No prohibited email remains')
            if any(attrs.get(k) for k in ('email','recipient_email','recipient','to')):return result('APPLICABLE','User email is present in delivery record')
            return result('UNKNOWN','Email-content condition is not established')
        if category=='ACCOUNT_TOMBSTONE':
            status=attrs.get('account_status')
            if status is not None and str(status).upper()!='DELETED':return result('INAPPLICABLE','Account is not in deleted state')
            reference=next((attrs[k] for k in ('subject_reference','user_id','customer_reference') if attrs.get(k)),None)
            if str(status).upper()=='DELETED' and reference and '@' not in str(reference):return result('APPLICABLE','Deleted account and stable reference established')
            return result('UNKNOWN','Deleted-account state or stable reference is unproven')
        if category=='BACKUP_ARCHIVE':
            blockable=flag('can_block_restore','restore_access_blockable')
            if blockable is False:return result('INAPPLICABLE','Restore blocking explicitly unsupported; no fallback rule')
            if blockable is True or 'restore_allowed' in attrs or state=='BLOCKED':return result('APPLICABLE','Restore authorization control is observable')
            return result('UNKNOWN','Restore-blocking capability is not established')
        return result('UNKNOWN','Unsupported conditional policy predicate')

    def assess(self, observation: Observation, audit_at: str | None = None) -> tuple[str, str, str | None]:
        """Return required verification operation/state and optional remediation."""
        category, state = observation.category, observation.state
        condition=self.applicability(observation,audit_at)
        if condition.status=='INAPPLICABLE':raise AuditError('Policy condition not met: '+condition.reason)
        # UNKNOWN permits an explicitly flagged candidate template only. Main
        # refuses COMPLETE/publication until all applicability facts are proved.
        if category == 'DATA_FLOW':
            return 'VERIFY_DATA_FLOW_DISABLED', 'DISABLED', None if state == 'DISABLED' else 'DISABLE_DATA_FLOW'
        if category == 'BACKUP_ARCHIVE':
            return 'VERIFY_RESTORE_BLOCKED', 'BLOCKED', None if state == 'BLOCKED' else 'BLOCK_RESTORE'
        if category not in self.rules:
            raise AuditError(f'No policy for category {category}')
        action = self.rules[category]['required_action']
        operation, target, remediation = {
            'DELETE': ('VERIFY_RECORD_ABSENT', 'ABSENT', 'DELETE_RECORD'),
            'REDACT': ('VERIFY_RECORD_REDACTED', 'REDACTED', 'REDACT_RECORD'),
            'ANONYMIZE': ('VERIFY_RECORD_ANONYMIZED', 'ANONYMIZED', 'ANONYMIZE_RECORD'),
            'RETAIN': ('VERIFY_RECORD_PRESENT', 'PRESENT', None),
        }[action]
        if action == 'RETAIN' and state == 'ABSENT':
            raise AuditError('Required retained resource is absent; contract has no restoration operation')
        return operation, target, None if state == target else remediation
