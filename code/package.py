"""Create a reviewable source archive without datasets, caches, or secrets."""
from __future__ import annotations
import argparse
from pathlib import Path
import zipfile
import os
import tempfile
from audit.security import guard_destination

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_SUFFIXES = {'.py', '.md', '.txt'}


def package(destination: Path) -> list[str]:
    if destination.suffix!='.zip': raise ValueError('Archive destination must end in .zip')
    guard_destination(destination,ROOT/'dataset',ROOT)
    code = ROOT/'code'
    required = [code/'README.md', code/'main.py', code/'requirements.txt', code/'evaluation/evaluation_report.md', code/'evaluation/usage_report.md']
    for path in required:
        if not path.is_file() or not path.stat().st_size: raise ValueError(f'Missing required archive source: {path.relative_to(ROOT)}')
    members = {'README.md': code/'README.md'}
    for path in sorted(code.rglob('*')):
        relative=path.relative_to(code)
        eligible=(relative.as_posix() in {'README.md','main.py','package.py','requirements.txt'} or (relative.parts[0] in {'audit','evaluation','tests'} and path.suffix=='.py') or (relative.parts[0]=='evaluation' and path.name in {'evaluation_report.md','usage_report.md','grounding_limitations.md','implementation_status.md','full_dataset_diagnostics.md','independent_review.md','sample_failure_comparison.md','security_audit.md','closure_review.md','interview_guide.md'}))
        if path.is_symlink(): raise ValueError('Symlink archive sources are not supported')
        if path.is_file() and eligible and not any(p in {'__pycache__','.venv','venv','node_modules','.git'} for p in relative.parts):
            members[path.relative_to(ROOT).as_posix()] = path
    for name in ('evaluation_report.md','usage_report.md'):
        members['evaluation/'+name] = code/'evaluation'/name
    destination.parent.mkdir(parents=True,exist_ok=True)
    handle,temporary=tempfile.mkstemp(prefix='.audit-package-',suffix='.tmp',dir=destination.parent)
    os.close(handle)
    try:
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, path in sorted(members.items()):
                info=zipfile.ZipInfo(name,(2026,1,1,0,0,0)); info.compress_type=zipfile.ZIP_DEFLATED
                info.external_attr=0o644 << 16
                archive.writestr(info,path.read_bytes())
        with zipfile.ZipFile(temporary) as archive:
            if archive.testzip(): raise ValueError('Corrupt archive')
            names=archive.namelist()
            if set(names)!=set(members): raise ValueError('Archive member mismatch')
            for name in names:
                if Path(name).suffix not in ALLOWED_SUFFIXES or name.startswith(('dataset/','runs/')): raise ValueError('Forbidden archive member')
        os.replace(temporary,destination)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)
    return names


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'code.zip'); parser.add_argument('--overwrite',action='store_true')
    args=parser.parse_args()
    if args.output.exists() and not args.overwrite: parser.error('Archive exists; use --overwrite explicitly')
    names=package(args.output)
    print(f'Verified {len(names)} files in {args.output}')
    if not (ROOT/'output.csv').exists() or (ROOT/'output.csv.partial.md').exists():
        print('NOT SUBMISSION-READY: final complete output.csv has not been published')
    return 0


if __name__=='__main__':
    import sys
    from audit.security import public_error
    try: raise SystemExit(main())
    except Exception as exc:
        print(f'PACKAGING FAILED: {public_error(exc)}',file=sys.stderr)
        raise SystemExit(2)
