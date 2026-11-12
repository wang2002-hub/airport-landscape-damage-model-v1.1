"""Shared file checks and run provenance for command-line analyses."""
from pathlib import Path
import hashlib
import importlib.metadata
import json
import platform
import sys

def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def prepare_output(output, inputs, subdirs):
    output = Path(output).resolve()
    inputs = {key: Path(value).resolve(strict=True) for key, value in inputs.items()}
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError('Use a new or empty output directory; previous runs are preserved.')
    for path in inputs.values():
        if output == path or output in path.parents:
            raise ValueError('The output directory must not contain an input file.')
    output.mkdir(parents=True, exist_ok=True)
    for name in subdirs:
        (output / name).mkdir(exist_ok=True)
    packages = ['numpy', 'pandas', 'scipy', 'scikit-learn', 'joblib', 'pyarrow', 'threadpoolctl']
    metadata = {
        'python': sys.version,
        'platform': platform.platform(),
        'versions': {name: importlib.metadata.version(name) for name in packages},
        'inputs': {key: {'filename': path.name, 'bytes': path.stat().st_size,
                         'sha256': file_hash(path)} for key, path in inputs.items()},
        'source_sha256': {path.name: file_hash(path) for path in sorted(Path(__file__).parent.glob('*.py'))},
    }
    (output / 'run_inputs.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    return output

def validate_events(data):
    required = ['event_id', 'airport_id', 'year', 'damage_binary', 'spatial_fold', 'target']
    if not set(required).issubset(data.columns):
        raise ValueError('Analysis data are missing required columns.')
    if not data.event_id.is_unique or data[required].isna().any().any():
        raise ValueError('Event identifiers must be unique and design fields complete.')
    if not data.damage_binary.isin([0, 1]).all() or not data.year.between(2015, 2025).all():
        raise ValueError('Unexpected outcomes or study years.')
    if str(data.target.dtype) not in ['bool', 'boolean']:
        raise ValueError('The target field must have Boolean dtype.')
    expected = {'KDEN','KJFK','KMIA','KMSP','KBOS','KSFO','KSAT','KSTL'}
    if set(data.loc[data.target, 'airport_id']) != expected:
        raise ValueError('The eight target airports must be present.')
    if not data.target.equals(data.airport_id.isin(expected)):
        raise ValueError('Target membership conflicts with airport identifiers.')
    national = data[~data.target]
    if set(national.spatial_fold.unique()) != {1,2,3,4,5}:
        raise ValueError('National data must retain all five assigned folds.')
    if national.groupby('airport_id').spatial_fold.nunique().max() != 1:
        raise ValueError('An airport spans multiple geographic folds.')
