from pathlib import Path
import argparse,hashlib,json,traceback

def execute(run,roles):
    parser=argparse.ArgumentParser(description='Recompute diagnostics from explicitly mapped retained inputs.')
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():parser.error('Choose a new output directory to preserve prior results.')
    try:
        config_path=args.config.resolve()
        config=json.loads(config_path.read_text(encoding='utf-8'))['inputs']
        if set(config)!=set(roles):raise ValueError('Input role set differs')
        paths={}
        for role,entry in config.items():
            p=Path(entry['path'])
            p=(config_path.parent/p).resolve() if not p.is_absolute() else p.resolve()
            if not p.is_file():raise FileNotFoundError(p)
            if hashlib.sha256(p.read_bytes()).hexdigest()!=entry['sha256']:
                raise ValueError('Input checksum mismatch for '+role)
            paths[role]=p
        args.output.mkdir(parents=True)
        run(paths,args.output.resolve())
        (args.output/'input_hashes.json').write_text(json.dumps({k:config[k]['sha256'] for k in roles},indent=2),encoding='utf-8')
    except Exception:
        args.output.mkdir(parents=True,exist_ok=True)
        (args.output/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise
