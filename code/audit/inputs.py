"""Strict dataset loading. Prediction code never loads sample answers."""
from __future__ import annotations
import csv
import hashlib
from pathlib import Path
from .contracts import AuditError, REQUEST_FIELDS, timestamp
from .security import check_file, identifier, MAX_ROWS, MAX_TOTAL_BYTES

SCHEMAS = {
    'user_identities.csv': 'user_id,name,email,phone,email_hash,updated_at',
    'user_audit_log.csv': 'audit_id,user_id,event_time,field_name,old_value,new_value',
    'system_activity.csv': 'activity_id,event_time,event_type,source_system,target_system,resource_id,reported_result,details',
    'deletion_rules.csv': 'rule_id,data_category,condition,required_action',
    'evidence_files.csv': 'file_id,file_path,origin,captured_at',
}


def read_csv(path: Path, fields: list[str] | None = None) -> list[dict[str, str]]:
    check_file(path)
    try:
        with path.open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream)
            headers=reader.fieldnames
            if not headers or len(headers)!=len(set(headers)): raise AuditError('Missing or duplicate CSV column names')
            if fields is not None and headers != fields: raise AuditError('Unexpected CSV header')
            rows=[]
            for row in reader:
                if len(rows)>=MAX_ROWS: raise AuditError('CSV exceeds configured row budget')
                rows.append(row)
    except (UnicodeError,csv.Error) as exc:
        raise AuditError('CSV is not valid UTF-8 or has invalid field structure') from exc
    if any(None in row or any(v is None for v in row.values()) for row in rows):
        raise AuditError(f'{path.name}: malformed CSV row')
    return rows


def safe_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise AuditError(f'Missing or unsafe evidence path: {relative}')
    return path


def load_inputs(root: Path, request_file: str) -> dict[str, list[dict[str, str]]]:
    result = {name: read_csv(safe_path(root,name), schema.split(',')) for name, schema in SCHEMAS.items()}
    result['requests'] = read_csv(safe_path(root, request_file), REQUEST_FIELDS)
    if not result['requests']: raise AuditError('Request input is empty')
    for name, rows in result.items():
        id_field = 'case_id' if name == 'requests' else SCHEMAS[name].split(',')[0]
        ids = [r[id_field] for r in rows]
        for value in ids: identifier(value)
        if len(ids) != len(set(ids)) or any(not x for x in ids):
            raise AuditError(f'{name}: empty/duplicate IDs')
        for row in rows:
            for key in ('requested_at', 'reported_at', 'audit_at', 'updated_at', 'event_time', 'captured_at'):
                if key in row:
                    timestamp(row[key])
    for r in result['requests']:
        if r['reported_status'] not in {'COMPLETE', 'PARTIALLY_COMPLETE', 'NOT_STARTED'}:
            raise AuditError('Unknown reported status')
    for row in result['evidence_files.csv']:
        check_file(safe_path(root, row['file_path']))
    sources=[safe_path(root,name) for name in SCHEMAS] + [safe_path(root,request_file)] + [safe_path(root,r['file_path']) for r in result['evidence_files.csv']]
    if sum(path.stat().st_size for path in sources)>MAX_TOTAL_BYTES: raise AuditError('Dataset exceeds configured size budget')
    citation_ids=[r['file_id'] for r in result['evidence_files.csv']]+[r['activity_id'] for r in result['system_activity.csv']]+[r['audit_id'] for r in result['user_audit_log.csv']]
    if len(citation_ids)!=len(set(citation_ids)): raise AuditError('Citation IDs collide across sources')
    return result


def fingerprint(root: Path, inputs: dict) -> str:
    digest = hashlib.sha256()
    for name in sorted(SCHEMAS):
        digest.update(name.encode()); digest.update((root / name).read_bytes())
    for row in inputs['evidence_files.csv']:
        digest.update(row['file_path'].encode()); digest.update(safe_path(root, row['file_path']).read_bytes())
    import json
    digest.update(json.dumps(inputs['requests'], sort_keys=True).encode())
    return digest.hexdigest()
