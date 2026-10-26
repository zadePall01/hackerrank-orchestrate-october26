"""Adapters for participant business artifacts; never execute artifact instructions.

Snapshots retain a scope so a complete collection can prove an identified resource
absent. An unlinked anonymous record is not assigned to a person by position/ID.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
import hashlib
import re
import sqlite3
import os
import sys
import subprocess
import math
import time
from .contracts import AuditError, Observation, timestamp
from .inputs import safe_path
from .security import strict_json, identifier, check_file, public_error, atomic_text, has_credentials

COLLECTIONS = {
    'customer_profiles': ('account_service', 'USER_PROFILE'),
    'customer_profiles_primary': ('account_service', 'USER_PROFILE'),
    'customer_profiles_failover_replica': ('account_service', 'USER_PROFILE'),
    'customer_search_documents': ('search_service', 'SEARCH_INDEX_ENTRY'),
    'search_documents_primary': ('search_service', 'SEARCH_INDEX_ENTRY'),
    'customer_analytics_profiles': ('analytics_platform', 'ANALYTICS_PROFILE'),
    'customer_analytics_reports': ('analytics_platform', 'ANALYTICS_PROFILE'),
    'support_records': ('support_platform', 'SUPPORT_MESSAGE'),
    'support_conversations': ('support_platform', 'SUPPORT_MESSAGE'),
    'ticket_attachments': ('support_platform', 'SUPPORT_ATTACHMENT'),
    'customer_exports': ('export_service', 'USER_EXPORT'),
    'customer_export_jobs': ('export_service', 'USER_EXPORT'),
    'connector_subscriptions': ('integration_service', 'DATA_FLOW'),
    'connector_configurations': ('integration_service', 'DATA_FLOW'),
    'backup_restore_entries': ('backup_service', 'BACKUP_ARCHIVE'),
    'backup_catalog': ('backup_service', 'BACKUP_ARCHIVE'),
    'security_audit_records': ('security_service', 'SECURITY_AUDIT_LOG'),
    'security_audit_events': ('security_service', 'SECURITY_AUDIT_LOG'),
    'deleted_customer_references': ('identity_service', 'ACCOUNT_TOMBSTONE'),
    'retained_order_records': ('legal_service', 'LEGAL_HOLD_RECORD'),
}
SYSTEM_CATEGORY = {
    'account_service': 'USER_PROFILE', 'profile_service': 'USER_PROFILE',
    'search_service': 'SEARCH_INDEX_ENTRY', 'analytics_platform': 'ANALYTICS_PROFILE',
    'integration_service': 'DATA_FLOW', 'backup_service': 'BACKUP_ARCHIVE',
    'export_service': 'USER_EXPORT', 'support_platform': 'SUPPORT_MESSAGE',
    'support_replica': 'SECONDARY_IDENTIFIER', 'security_service': 'SECURITY_AUDIT_LOG',
    'identity_service': 'ACCOUNT_TOMBSTONE', 'marketing_platform': 'MARKETING_PROFILE',
    'object_storage': 'SUPPORT_ATTACHMENT', 'email_delivery_service': 'EMAIL_DELIVERY_LOG',
    'cache_service': 'CACHE_ENTRY',
}
DIRECT_FIELDS = {'name', 'full_name', 'display_name', 'email', 'phone', 'email_hash', 'requester_name', 'requester_email', 'requester_phone', 'customer_email', 'owner_email', 'owner_phone'}
NULLS = {'', 'null', 'none', 'nil', '[redacted]', 'redacted', 'no direct identifier'}


def present(value: Any) -> bool:
    return value is not None and str(value).strip().casefold() not in NULLS


def observed_bool(value: Any) -> bool:
    """Parse observed flags without turning arbitrary strings into True."""
    if isinstance(value, bool): return value
    if str(value).casefold() in {'true','1'}: return True
    if str(value).casefold() in {'false','0'}: return False
    raise AuditError(f'Invalid observed boolean: {value!r}')


def flatten(record: dict) -> dict:
    result = dict(record)
    for key in ('document', 'profile'):
        if isinstance(record.get(key), dict): result.update(record[key])
    return result


def infer_state(category: str, record: dict) -> str:
    explicit = str(record.get('result', '')).upper()
    if explicit in {'NOT_FOUND', 'ABSENT', 'DELETED'} or record.get('status_code') == 404 or str(record.get('rows', '')) == '0':
        return 'ABSENT'
    if category == 'DATA_FLOW':
        enabled = record.get('enabled')
        if enabled is None and explicit not in {'ACTIVE', 'DISABLED'}: raise AuditError('Connector has no observed enabled state')
        return ('ACTIVE' if observed_bool(enabled) else 'DISABLED') if enabled is not None else explicit
    if category == 'BACKUP_ARCHIVE':
        allowed = record.get('restore_allowed')
        if allowed is None and explicit not in {'ACTIVE', 'BLOCKED'}: raise AuditError('Backup has no observed restore policy')
        return ('ACTIVE' if observed_bool(allowed) else 'BLOCKED') if allowed is not None else explicit
    if category in {'SUPPORT_MESSAGE', 'EMAIL_DELIVERY_LOG', 'ACCOUNT_TOMBSTONE', 'ANALYTICS_PROFILE', 'PRODUCT_TELEMETRY'}:
        identifiable = any(present(record.get(k)) for k in DIRECT_FIELDS)
        if category in {'ANALYTICS_PROFILE', 'PRODUCT_TELEMETRY'}:
            identifiable |= any(present(record.get(k)) for k in ('user_id', 'customer_reference', 'subject_reference'))
        # Free-form messages may retain direct identifiers despite null columns.
        message = str(record.get('message_text', record.get('message_excerpt', '')))
        identifiable |= bool(re.search(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|\+\d[\d ()-]{6,}\d', message))
        if 'direct_identifiers' in record:
            try: identifiable |= int(record['direct_identifiers']) > 0
            except (TypeError,ValueError) as exc: raise AuditError('Invalid identifier scan count') from exc
        if explicit == 'IDENTIFIABLE': identifiable = True
        # A compliance label must never conceal directly observed identifiers.
        return 'PRESENT' if identifiable else ('ANONYMIZED' if category in {'ANALYTICS_PROFILE', 'PRODUCT_TELEMETRY'} else 'REDACTED')
    return 'PRESENT'


@dataclass
class Scope:
    evidence_id: str
    captured_at: str
    observed_at: str
    system: str
    category: str
    resources: set[str]
    name: str
    complete: bool = False


class Extractor:
    def __init__(self, cache_dir: Path | None = None, document_timeout: float = 60):
        if not math.isfinite(document_timeout) or not 0<document_timeout<=300: raise AuditError('Document timeout must be between 0 and 300 seconds')
        self.observations: list[Observation] = []
        self.scopes: list[Scope] = []
        self.coverage: list[dict] = []
        self.texts: dict[str, str] = {}
        self._ocr = None
        self.cache_dir = cache_dir
        self.ocr_calls = 0
        self.document_cache_hits = 0
        self.document_timeout = document_timeout

    def emit(self, manifest: dict, system: str, category: str, record: dict, observed: str | None = None, locator: str = '', scope: str = '') -> None:
        record = flatten(record)
        resource = record.get('resource_id')
        if not resource: raise AuditError(f'{manifest["file_id"]}: record missing resource_id')
        identifier(resource);identifier(system);identifier(manifest['file_id'])
        if category not in set(SYSTEM_CATEGORY.values())|{'PRODUCT_TELEMETRY','LEGAL_HOLD_RECORD'}: raise AuditError('Unknown observed record category')
        if 'record_type' in record and 'result' in record and record['result'] not in {'FOUND','PRESENT','NOT_FOUND','ABSENT','IDENTIFIABLE','REDACTED','ANONYMIZED','ACTIVE','DISABLED','BLOCKED'}:
            raise AuditError('Unsupported observed lookup result; workflow claims are not state proof')
        system = 'account_service' if system == 'profile_service' else system
        observed = observed or record.get('recorded_at') or record.get('observed_at') or manifest['captured_at']
        timestamp(observed);timestamp(manifest['captured_at'])
        self.observations.append(Observation(manifest['file_id'], manifest['captured_at'], observed, system, resource, category, infer_state(category, record), record, locator, scope))

    def collection(self, manifest: dict, system: str, collection: str, rows: list, observed: str, complete: bool = False) -> None:
        if collection not in COLLECTIONS: raise AuditError(f'Unknown collection: {collection}')
        _, category = COLLECTIONS[collection]
        scope = f'{manifest["file_id"]}:{system}:{collection}'
        self.scopes.append(Scope(manifest['file_id'], manifest['captured_at'], observed, system, category, {r['resource_id'] for r in rows}, scope, complete))
        for n, row in enumerate(rows): self.emit(manifest, system, category, row, observed, f'{collection}[{n}]', scope)

    def json_file(self, manifest: dict, path: Path) -> None:
        check_file(path)
        data = strict_json(path.read_text(encoding='utf-8-sig'))
        if not isinstance(data,dict): raise AuditError('JSON artifact root must be an object')
        if 'snapshots' in data:
            for snapshot in data['snapshots']:
                if snapshot['collection'] == 'operational_record_history':
                    for n, record in enumerate(snapshot['records']):
                        self.emit(manifest, record['system'], record['record_type'], record, record['recorded_at'], f'operational_record_history[{n}]')
                else:
                    self.collection(manifest, snapshot['data_store'], snapshot['collection'], snapshot['records'], snapshot['captured_at'])
        elif 'service_exports' in data:
            types = {'profile_lookups': 'USER_PROFILE', 'profiles': 'ANALYTICS_PROFILE', 'restore_entries': 'BACKUP_ARCHIVE', 'exports': 'USER_EXPORT', 'connectors': 'DATA_FLOW', 'index_queries': 'SEARCH_INDEX_ENTRY', 'audit_records': 'SECURITY_AUDIT_LOG', 'tickets': 'SUPPORT_MESSAGE'}
            for system, groups in data['service_exports'].items():
                for kind, records in groups.items():
                    if kind not in types: raise AuditError(f'Unknown service export {kind}')
                    for n, record in enumerate(records):
                        record = dict(record)
                        if kind == 'index_queries':
                            hits = record['hits']
                            if hits['total'] == 0: record['result'] = 'NOT_FOUND'
                            elif hits['documents']: record.update(hits['documents'][0])
                        self.emit(manifest, system, types[kind], record, locator=f'{system}/{kind}[{n}]')
        elif 'records' in data:
            for n, record in enumerate(data['records']):
                if 'record_type' in record:
                    self.emit(manifest, record['system'], record['record_type'], record, locator=f'records[{n}]')
                else:
                    collection = data.get('collection')
                    aliases = {'customer_analytics_profiles': 'customer_analytics_reports', 'customer_exports': 'customer_export_jobs'}
                    collection = aliases.get(collection, collection)
                    if collection not in COLLECTIONS: raise AuditError(f'Unknown JSON collection {collection}')
                    system, category = COLLECTIONS[collection]
                    self.emit(manifest, system, category, record, locator=f'records[{n}]')
        else: raise AuditError(f'Unsupported JSON structure in {path.name}')

    def sql_file(self, manifest: dict, path: Path) -> None:
        # In-memory SQLite with an authorizer: artifact SQL cannot touch disk,
        # attach databases, load extensions, or run arbitrary application code.
        db = sqlite3.connect(':memory:')
        db.row_factory = sqlite3.Row
        denied = {sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH}
        def authorize(action, a, b, database, trigger):
            if action in denied or (action == sqlite3.SQLITE_FUNCTION and b not in {'json_valid'}): return sqlite3.SQLITE_DENY
            if action == sqlite3.SQLITE_PRAGMA and a != 'foreign_keys': return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        db.set_authorizer(authorize)
        ticks = 0
        started = time.monotonic()
        def progress():
            nonlocal ticks
            ticks += 1
            return int(ticks > 10000 or time.monotonic()-started>10)
        db.set_progress_handler(progress, 1000)
        try:
            db.executescript(path.read_text(encoding='utf-8-sig'))
            tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            for table in tables:
                if table == 'snapshot_scope': continue
                if not re.fullmatch(r'[a-z_]+', table): raise AuditError('Unsafe SQL table name')
                rows = [dict(row) for row in db.execute(f'SELECT * FROM "{table}"')]
                if table in COLLECTIONS:
                    system, category = COLLECTIONS[table]
                    # These files are full SQLite table snapshots. JSON record
                    # bundles carry no equivalent completeness assertion.
                    self.collection(manifest, system, table, rows, manifest['captured_at'], complete=True)
                elif table.startswith('customer_data_'):
                    for n, row in enumerate(rows):
                        collection = row['collection_name']
                        if collection not in COLLECTIONS: raise AuditError(f'Unknown replica collection {collection}')
                        record=strict_json(row['record_json'])
                        if not isinstance(record,dict) or record.get('resource_id')!=row['resource_id']: raise AuditError('SQL row and embedded resource ID disagree')
                        self.emit(manifest, row['origin_system'], COLLECTIONS[collection][1], record, manifest['captured_at'], f'{table}[{n}]', table)
                else: raise AuditError(f'Unsupported SQL table {table}')
        finally: db.close()

    def log_file(self, manifest: dict, path: Path) -> None:
        contexts: dict[str, dict] = {}
        for n, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
            observed = line[:20]
            text = line.replace('\\"', '"')
            record = {}
            for match in re.finditer(r'(\w+)=(?:"([^"]*)"|([^\s|]+))', text):
                record[match[1]] = match[2] if match[2] is not None else match[3]
            if line[20:].lstrip().startswith('{'):
                decoded=strict_json(line[line.index('{'):])
                if not isinstance(decoded,dict): raise AuditError('Structured log event must be an object')
                record.update(decoded)
            bracket = re.search(r'\[\w+\] \[([^]]+)\] \[([^]]+)\] ([a-z_]+):', line)
            if bracket: record.update(service=bracket[1], trace_id=bracket[2], event=bracket[3])
            pipe = line.split(' | ')
            if len(pipe) >= 6: record.update(service=pipe[2], trace_id=pipe[3], event=pipe[4])
            syslog = re.search(r'<\d+>1 \S+ (\S+) (\S+) - -', line)
            if syslog: record.update(service=syslog[1], trace_id=syslog[2])
            if 'function' in record: record['service'] = record['function']; record['trace_id'] = record.get('requestId', '')
            trace = record.get('trace_id', '')
            if trace:
                if record.get('event','').endswith('_started'): contexts[trace] = {}
                prior = contexts.setdefault(trace, {})
                prior.update(record); record = dict(prior)
            event = record.get('event', '')
            if event.endswith('_started'): continue
            system = record.get('system', record.get('service', ''))
            category = record.get('record_type', SYSTEM_CATEGORY.get(system))
            if not category or not record.get('resource_id'): continue
            if event == 'record_lookup': pass
            elif event in {'profile_lookup_completed', 'contact_query_completed', 'contact_lookup_completed', 'index_query_completed', 'audit_record_read_completed', 'analytics_profile_read_completed', 'support_ticket_read_completed', 'export_metadata_read_completed', 'connector_config_read_completed', 'restore_policy_read_completed'}:
                if event in {'contact_query_completed','contact_lookup_completed'}: category = 'SECONDARY_IDENTIFIER'
            elif event in {'message_pii_scan', 'attachment_pii_scan', 'analytics_identity_scan'}:
                record['email'] = record.get('matched_value', record.get('matched_identifier', ''))
                if event == 'attachment_pii_scan': category = 'SUPPORT_ATTACHMENT'
            elif event in {'connector_heartbeat', 'connector_config_loaded'}:
                if 'enabled' not in record: continue
            elif event in {'restore_candidate_evaluated', 'restore_authorization_completed'}:
                if 'restore_allowed' not in record:
                    decision = str(record.get('decision', '')).casefold()
                    if decision in {'deny', 'denied', 'block', 'blocked'}:
                        record['restore_allowed'] = False
                    elif decision in {'allow', 'allowed', 'permit', 'permitted'}:
                        record['restore_allowed'] = True
                    elif 'allowed' in record:
                        record['restore_allowed'] = record['allowed']
                    elif str(record.get('deletion_block', '')).casefold() == 'true':
                        record['restore_allowed'] = False
                    elif str(record.get('eligible', '')).casefold() == 'true' and str(record.get('deletion_block', '')).casefold() == 'false':
                        record['restore_allowed'] = True
                    else:
                        raise AuditError('Restore readback has no explicit authorization decision')
            elif event == 'analytics_profile_read': pass
            elif event == 'message_read': pass
            elif event == 'export_download_check_completed':
                if str(record.get('available', record.get('download_available', 'true'))).casefold() == 'false': record['result'] = 'NOT_FOUND'
            else: continue
            if system == 'support_replica': system = 'support_platform'
            if event == 'index_query_completed' and record.get('result') == 'miss': record['result'] = 'NOT_FOUND'
            # Identifiers from scan output are actual observations, not look-up keys.
            if event == 'analytics_identity_scan' and not record.get('email'):
                for key in ('email_hash', 'matched_hash', 'hash'):
                    if present(record.get(key)): record['email_hash'] = record[key]
            self.emit(manifest, system, category, record, observed, f'line {n}')

    def text_file(self, manifest: dict, path: Path) -> None:
        for n, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
            parts = line.removeprefix('- ').split(' | ')
            if len(parts) == 6:
                observed, system, resource, category, result, subject = parts
                self.emit(manifest, system, category, dict(resource_id=resource, result=result, subject_reference=subject), observed, f'line {n}')

    def document(self, manifest: dict, path: Path) -> None:
        source_hash=hashlib.sha256(path.read_bytes()).hexdigest()
        cache = None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            cache = self.cache_dir / (source_hash + '.v2.json')
        text=None
        if cache and cache.is_symlink(): raise AuditError('Symlink cache entries are not supported')
        if cache and cache.exists():
            try:
                check_file(cache)
                entry=strict_json(cache.read_text(encoding='utf-8'))
                value=entry['text']
                if isinstance(value,str) and has_credentials(value):
                    atomic_text(cache,'{"version":0,"reason":"credential-like text; cache disabled"}')
                elif entry['version']==2 and entry['source_sha256']==source_hash and isinstance(value,str) and entry['text_sha256']==hashlib.sha256(value.encode()).hexdigest():
                    text=value;self.document_cache_hits+=1
            except (AuditError,ValueError,KeyError,TypeError): pass
        if text is None:
            # Native PDF/OCR parsing is killable rather than an unbounded thread.
            # Child receives only environment entries needed to start Python/native DLLs.
            env={k:v for k,v in os.environ.items() if k.upper() in {'PATH','SYSTEMROOT','WINDIR','TEMP','TMP','LOCALAPPDATA'}}
            env.update(PYTHONIOENCODING='utf-8',PYTHONUTF8='1')
            try:
                process=subprocess.run([sys.executable,str(Path(__file__).with_name('document_worker.py')),str(path.resolve())],capture_output=True,text=True,encoding='utf-8',timeout=self.document_timeout,env=env,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            except subprocess.TimeoutExpired as exc: raise AuditError('Document extraction timed out; no retry or success fallback') from exc
            except OSError as exc: raise AuditError('Document worker could not start') from exc
            if process.returncode!=0: raise AuditError('Document extraction failed; parser or local models unavailable')
            if len(process.stdout)>4_000_000: raise AuditError('Document worker response exceeds budget')
            payload=strict_json(process.stdout)
            if not isinstance(payload,dict) or set(payload)!={'text','ocr_calls'} or not isinstance(payload['text'],str) or type(payload['ocr_calls']) is not int or payload['ocr_calls'] not in {0,1}: raise AuditError('Invalid document worker response')
            text=payload['text'];self.ocr_calls+=payload['ocr_calls']
            if cache and not has_credentials(text):
                atomic_text(cache,json.dumps(dict(version=2,source_sha256=source_hash,text_sha256=hashlib.sha256(text.encode()).hexdigest(),text=text),ensure_ascii=True))
        if not text.strip(): raise AuditError(f'No extracted text: {path.name}')
        if len(text)>2_000_000: raise AuditError('Extracted text exceeds budget')
        self.texts[manifest['file_id']] = text
        self.artifact_text(manifest, text, path.suffix)

    def artifact_text(self, manifest: dict, text: str, suffix: str) -> None:
        """Extract explicit business references; UI navigation labels are not facts."""
        emails = re.findall(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', text)
        users = re.findall(r'\buser_\d+\b', text)
        refs = list(dict.fromkeys(re.findall(r'\b(?:account|analytics|data_flow|backup|export|support|marketing|tombstone|audit_record|search)_\d+\b', text)))
        types = {'account': ('account_service','USER_PROFILE'), 'analytics': ('analytics_platform','ANALYTICS_PROFILE'), 'data_flow': ('integration_service','DATA_FLOW'), 'backup': ('backup_service','BACKUP_ARCHIVE'), 'export': ('export_service','USER_EXPORT'), 'support': ('support_platform','SUPPORT_MESSAGE'), 'marketing': ('marketing_platform','MARKETING_PROFILE'), 'tombstone': ('identity_service','ACCOUNT_TOMBSTONE'), 'audit_record': ('security_service','SECURITY_AUDIT_LOG'), 'search': ('search_service','SEARCH_INDEX_ENTRY')}
        # Focused artifact primary resource. Related sidebar/table records require
        # their own grounded links and are not all attributed to the primary user.
        if not refs: return
        primary = refs[0]
        if 'Raw document' in text:
            match = re.search(r'Raw document\s*[·-]?\s*(search_\d+)', text)
            if match: primary = match[1]
        if 'Raw event' in text:
            match = re.search(r'(audit_record_\d+)[^\n]*Raw event', text)
            if match: primary = match[1]
        prefix = primary.rsplit('_', 1)[0]
        system, category = types[prefix]
        if suffix == '.pdf' and category == 'SUPPORT_MESSAGE': category = 'SUPPORT_ATTACHMENT'
        if suffix == '.pdf' and category == 'USER_EXPORT': return
        attrs: dict[str, Any] = dict(resource_id=primary)
        if emails: attrs['email'] = emails[0]
        if users: attrs['subject_reference'] = users[0]
        if category=='SUPPORT_ATTACHMENT' and len(set(emails))==1 and 'Customer request' in text and re.search(r'\buploader\s+customer\b',text,re.I):
            attrs['subject_only']=True
        if category=='SUPPORT_MESSAGE':
            tickets=re.findall(r'\bCS-\d+\b',text)
            if tickets:attrs['ticket_id']=tickets[0]
        if category == 'DATA_FLOW': attrs['enabled'] = 'Continuous' in text or 'events delivered' in text
        if category == 'BACKUP_ARCHIVE':
            # An archive listing alone does not establish restore authorization.
            return
        if category == 'ACCOUNT_TOMBSTONE': attrs['account_status'] = 'DELETED'
        self.emit(manifest, system, category, attrs, locator='primary resource in extracted business artifact')

    def run(self, dataset: Path, manifest: list[dict]) -> None:
        for item in manifest:
            path = safe_path(dataset, item['file_path'])
            check_file(path)
            before = len(self.observations)
            suffix = path.suffix
            adapter = {'.json': self.json_file, '.sql': self.sql_file, '.log': self.log_file, '.txt': self.text_file, '.pdf': self.document, '.png': self.document}.get(suffix)
            if adapter is None: raise AuditError(f'Unsupported evidence extension {suffix}')
            try: adapter(item, path)
            except Exception as exc: raise AuditError(f'Extraction failed for {item["file_id"]}: {public_error(exc)}') from exc
            self.coverage.append(dict(file_id=item['file_id'], format=suffix, observations=len(self.observations)-before, text_extracted=item['file_id'] in self.texts))

    def catalog_artifacts(self, manifest: list[dict], activity: list[dict]) -> None:
        """Map displayed business labels to IDs only through explicit catalog links."""
        by_id = {r['file_id']: r for r in manifest}
        for event in activity:
            if event['event_type'] != 'LINK_RESOURCE_IDENTITY': continue
            label_match = re.search(r'\(([^)]+)\)', event['details'])
            if not label_match: continue
            label = label_match[1]
            for evidence_id, text in self.texts.items():
                if label not in text: continue
                system = event['target_system']
                category = SYSTEM_CATEGORY.get(system)
                attrs = dict(resource_id=event['resource_id'], catalog_reference=label)
                if system == 'object_storage' and 'objects' in text.casefold() and re.search(r'\b\d+(?:\.\d+)?\s*(?:KB|MB)\b', text):
                    attrs['object_name'] = label
                    if re.search(r'belongs only to.*no other subject is linked',event['details'],re.I):attrs['subject_only']=True
                elif system == 'identity_service' and 'Customer Reference' in text and label.startswith('user_'):
                    attrs['subject_reference'] = label
                elif system == 'export_service' and 'statement' in text.casefold():
                    attrs['statement_reference'] = label
                else: continue
                # Availability requires BOTH the artifact and catalog link.
                item = dict(by_id[evidence_id])
                item['captured_at'] = max(item['captured_at'], event['event_time'])
                self.emit(item, system, category, attrs, locator=f'artifact label linked by {event["activity_id"]}')
