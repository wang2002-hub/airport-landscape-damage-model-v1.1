"""Explicit prediction sources shared by national profile entries."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
from run_support import prepare_output,validate_events

def configure(parser,extra):
    for name in ['data','national-dir','simple','reference','output']+extra:
        parser.add_argument('--'+name,required=True)
    args=parser.parse_args()
    paths={'data':args.data,'simple':args.simple,'reference':args.reference}
    for name in extra:paths[name]=getattr(args,name.replace('-','_'))
    for family,block in [('glmm','EB'),('glmm','EBL'),('hgb','EB'),('hgb','EBL')]:
        for fold in range(1,6):
            name=f'spatial_{fold}_{family}_{block}_predictions.parquet'
            paths[name]=Path(args.national_dir)/name
    output=prepare_output(args.output,paths,['results','logs'])
    return args,output

def valid_predictions(d):
    p=d.p_calibrated.to_numpy(float)
    if not np.isfinite(p).all() or not ((p>0)&(p<1)).all():
        raise ValueError('Predictions must be finite probabilities strictly between zero and one.')
    if not d.event_id.is_unique:
        raise ValueError('An evaluation population contains duplicate event identifiers.')
