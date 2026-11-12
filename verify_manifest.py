"""Verify tracked release files while allowing local Git and Python metadata."""
from pathlib import Path
import csv,hashlib,os
root=Path(__file__).resolve().parent
with (root/'manifest_sha256.csv').open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
actual=set()
for base,dirs,files in os.walk(root):
    here=Path(base)
    dirs[:]=[d for d in dirs if d!='__pycache__' and not (here==root and d in {'.git','.venv','venv'})]
    for name in files:
        p=here/name
        if p==root/'manifest_sha256.csv' or p.suffix in {'.pyc','.pyo'}:continue
        actual.add(p.relative_to(root).as_posix())
if actual!={r['file'] for r in rows}:raise SystemExit('Manifest file membership differs')
for r in rows:
    p=(root/r['file']).resolve()
    if not p.is_relative_to(root) or p.stat().st_size!=int(r['bytes']) or hashlib.sha256(p.read_bytes()).hexdigest()!=r['sha256']:
        raise SystemExit('Integrity check failed: '+r['file'])
print('Verified',len(rows),'release files')
