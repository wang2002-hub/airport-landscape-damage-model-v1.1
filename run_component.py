"""Run a named study component with its own explicit arguments."""
from pathlib import Path
import argparse,json,subprocess,sys,os
ROOT=Path(__file__).resolve().parent
def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--list',action='store_true');parser.add_argument('--component');parser.add_argument('--entry');parser.add_argument('arguments',nargs=argparse.REMAINDER)
 args=parser.parse_args();registry={x['component']:x['entries'] for x in json.loads((ROOT/'components.json').read_text(encoding='utf-8'))}
 if args.list:
  for name,scripts in registry.items():print(name+': '+', '.join(scripts))
  return 0
 if args.component not in registry or args.entry not in registry[args.component]:parser.error('Choose a registered component and entry. Use --list for available commands.')
 forwarded=args.arguments[1:] if args.arguments[:1]==['--'] else args.arguments
 if not forwarded:parser.error('Pass the component arguments after --, or use -- --help.')
 env=os.environ.copy();env['PYTHONDONTWRITEBYTECODE']='1'
 return subprocess.call([sys.executable,'-B',str(ROOT/'components'/args.component/args.entry),*forwarded],env=env)
if __name__=='__main__':raise SystemExit(main())
