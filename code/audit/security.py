"""Local input budgets, safe diagnostics and atomic writes; not an OS sandbox."""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import tempfile
from .contracts import AuditError

MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024
MAX_ROWS = 100_000
MAX_JSON_DEPTH = 64
MAX_JSON_NODES = 500_000


def identifier(value: str) -> None:
    # Accept ordinary opaque IDs without requiring dataset-specific numbering.
    # Reject control/markup/formula injection and excessively long identifiers.
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.:-]{0,127}',value):
        raise AuditError('Invalid identifier syntax or length')
    if has_credentials(value): raise AuditError('Credential-like identifier is not supported')


def check_file(path: Path) -> None:
    if path.stat().st_size > MAX_FILE_BYTES: raise AuditError('Input file exceeds configured size budget')


def strict_json(text: str):
    def pairs(items):
        result = {}
        for key,value in items:
            if key in result: raise AuditError('Duplicate JSON object key')
            result[key] = value
        return result
    def constant(value): raise AuditError('Non-finite JSON number is not supported')
    try:
        data=json.loads(text,object_pairs_hook=pairs,parse_constant=constant)
    except (json.JSONDecodeError,RecursionError) as exc:
        raise AuditError('Malformed or excessively nested JSON') from exc
    pending=[(data,0)];count=0
    while pending:
        value,depth=pending.pop();count+=1
        if depth>MAX_JSON_DEPTH or count>MAX_JSON_NODES: raise AuditError('JSON structure exceeds configured budget')
        if isinstance(value,dict): pending.extend((v,depth+1) for v in value.values())
        elif isinstance(value,list): pending.extend((v,depth+1) for v in value)
    return data


def redact_credentials(message: str) -> str:
    message=re.sub(r'-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?-----END [^-]*PRIVATE KEY-----','[REDACTED]',message)
    message=re.sub(r'(?i)\bBearer\s+\S+','Bearer [REDACTED]',message)
    message=re.sub(r'\bsk-[A-Za-z0-9_-]{12,}|\bAKIA[A-Z0-9]{16}\b','[REDACTED]',message)
    message=re.sub(r'''(?ix)\b(api[_ -]?key|access[_ -]?token|authorization|password|secret|token|cookie)["']?\s*[:=]\s*(?:"[^"]*"|'[^']*'|[^\s,;]+)''',r'\1=[REDACTED]',message)
    return message


def has_credentials(message: str) -> bool:
    return redact_credentials(message)!=message


def public_error(exc: BaseException) -> str:
    """Never print arbitrary third-party exception content or raw credentials."""
    if not isinstance(exc,AuditError): return f'Operation failed ({type(exc).__name__}); input or dependency may be unavailable'
    message=redact_credentials(str(exc))
    message=re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}','[REDACTED EMAIL]',message)
    return ' '.join(message.split())[:500]


def guard_destination(path: Path, dataset: Path, repository: Path) -> None:
    resolved=path.resolve()
    protected=[(repository/'code').resolve(),(repository/'.git').resolve()]
    if any(resolved==root or resolved.is_relative_to(root) for root in protected):
        raise AuditError('Write destination overlaps protected inputs or source files')
    data_root=dataset.resolve()
    if (resolved==data_root or resolved.is_relative_to(data_root)) and resolved.exists():
        raise AuditError('Write destination overlaps an existing dataset asset')
    if resolved in {(repository/name).resolve() for name in ('AGENTS.md','CLAUDE.md','README.md','problem_statement.md','agent_trace_instructions.md','log.txt')}:
        raise AuditError('Write destination is a protected repository asset')
    if path.is_symlink(): raise AuditError('Symlink write destinations are not supported')


def atomic_text(path: Path, text: str) -> None:
    if path.is_symlink(): raise AuditError('Symlink write destinations are not supported')
    path.parent.mkdir(parents=True,exist_ok=True)
    handle,name=tempfile.mkstemp(prefix='.audit-',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(handle,'w',encoding='utf-8',newline='\n') as stream: stream.write(text)
        os.replace(name,path)
    finally:
        if os.path.exists(name): os.unlink(name)
