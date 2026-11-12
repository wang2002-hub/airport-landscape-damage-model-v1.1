"""Regenerate SHA256 manifests after adding or replacing files in the v1.1 repository.

Usage (from any folder):
    python -B regenerate_manifests.py REPO [--components NAME ...]

REPO          path to airport-landscape-damage-model-v1.1
--components  component folders whose own manifest_sha256.csv should be rewritten
              (columns path,sha256); their manifest_sha256 and files fields in
              components.json are updated to match. The root manifest_sha256.csv (file,bytes,sha256)
              is always rewritten. Run verify_manifest.py afterwards.
Existing file order is kept and new files are appended, with the release's column
format and CRLF line endings, so running this on an unchanged repository reproduces
the existing manifests byte for byte. Deleted files are dropped.
"""
import argparse, csv, hashlib, json, os
from pathlib import Path

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def ordered(rows, manifest):
    # Keep the order of files already listed; append new files in sorted order.
    old = []
    if manifest.exists():
        with manifest.open(encoding='utf-8', newline='') as f: old = [r[0] for r in csv.reader(f)][1:]
    pos = {k: i for i, k in enumerate(old)}
    keep = sorted((r for r in rows if r[0] in pos), key=lambda r: pos[r[0]])
    return keep + sorted((r for r in rows if r[0] not in pos), key=lambda r: r[0].lower())

def walk(root, top):
    for base, dirs, names in os.walk(root):
        here = Path(base)
        dirs[:] = [d for d in dirs if d != '__pycache__' and not (here == top and d in {'.git', '.venv', 'venv'})]
        for n in names:
            p = here / n
            if p.name == 'manifest_sha256.csv' and p.parent == root: continue
            if p.suffix in {'.pyc', '.pyo'}: continue
            yield p

ap = argparse.ArgumentParser(); ap.add_argument('repo'); ap.add_argument('--components', nargs='*', default=[])
a = ap.parse_args(); repo = Path(a.repo).resolve()
for c in a.components:
    cd = repo / 'components' / c
    if not cd.is_dir(): raise SystemExit('No component folder: ' + c)
    rows = ordered([(p.relative_to(cd).as_posix(), sha(p)) for p in walk(cd, cd)], cd / 'manifest_sha256.csv')
    with (cd / 'manifest_sha256.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f, lineterminator='\r\n'); w.writerow(['path', 'sha256']); w.writerows(rows)
    print('component', c, len(rows), 'files')
    reg_path = repo / 'components.json'; raw = reg_path.read_bytes()
    reg = json.loads(raw.decode('utf-8'))
    hit = [e for e in reg if e.get('component') == c]
    if not hit: raise SystemExit(c + ' is not registered in components.json; add its entry first')
    hit[0]['manifest_sha256'] = sha(cd / 'manifest_sha256.csv'); hit[0]['files'] = len(rows)
    nl = '\r\n' if b'\r\n' in raw else '\n'
    txt = json.dumps(reg, indent=2, ensure_ascii=False).replace('\n', nl) + (nl if raw.endswith(nl.encode()) else '')
    reg_path.write_bytes(txt.encode('utf-8'))
rows = ordered([(p.relative_to(repo).as_posix(), p.stat().st_size, sha(p)) for p in walk(repo, repo)], repo / 'manifest_sha256.csv')
with (repo / 'manifest_sha256.csv').open('w', newline='', encoding='utf-8') as f:
    w = csv.writer(f, lineterminator='\r\n'); w.writerow(['file', 'bytes', 'sha256']); w.writerows(rows)
print('root manifest', len(rows), 'files')
