"""Hash-checked loading of bundled aggregate inputs for the reporting-signal component."""
from pathlib import Path
import argparse, hashlib, json

HERE = Path(__file__).resolve().parent


def parse(description):
    p = argparse.ArgumentParser(description=description)
    p.add_argument('--config', type=Path, default=HERE / 'inputs.json')
    p.add_argument('--output', type=Path, required=True, help='new output directory')
    a = p.parse_args()
    if a.output.exists():
        p.error('Choose a new output directory to preserve prior results.')
    return a


def resolve(config_path, roles):
    config_path = Path(config_path).resolve()
    cfg = json.loads(config_path.read_text(encoding='utf-8'))['inputs']
    out = {}
    for role in roles:
        e = cfg[role]
        p = Path(e['path'])
        p = (config_path.parent / p).resolve() if not p.is_absolute() else p
        if not p.is_file():
            raise FileNotFoundError(p)
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        if h != e['sha256']:
            raise ValueError(f'Input checksum mismatch for {role}')
        out[role] = p
    return out, {r: cfg[r]['sha256'] for r in roles}
