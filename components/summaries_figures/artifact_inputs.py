"""Explicit input bindings and protected output directories."""
from pathlib import Path
import argparse,json
from run_support import prepare_output

class Inputs:
    def __init__(self,description):
        parser=argparse.ArgumentParser(description=description)
        parser.add_argument('--inputs',required=True,help='JSON bindings; relative paths resolve against this file.')
        parser.add_argument('--output',required=True)
        args=parser.parse_args();self.manifest=Path(args.inputs).resolve(strict=True)
        self.config=json.loads(self.manifest.read_text(encoding='utf-8'))
        self.base=self.manifest.parent
        self.output=prepare_output(args.output,{'input_bindings':self.manifest},['results','logs','figures'])
    def path(self,key,name=None):
        raw=Path(self.config['paths'][key]);base=raw if raw.is_absolute() else self.base/raw
        path=base if name is None else base/name
        path=path.resolve(strict=True)
        if self.output==path or self.output in path.parents:
            raise ValueError('An input must be outside the output directory.')
        return path
    def label(self,key):return self.config['labels'][key]
