"""Reconstruct paired year draws and interval summaries from all bootstrap attempts."""
from pathlib import Path
import argparse,json,traceback
import numpy as np,pandas as pd
from run_support import prepare_output,file_hash
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--reference',required=True)
parser.add_argument('--bootstrap-dir',required=True)
parser.add_argument('--output',required=True)
parser.add_argument('--trusted-object-arrays',action='store_true',help='Permit trusted retained NPZ files with object identifiers. Newly generated files use string arrays.')
args=parser.parse_args()
D=prepare_output(args.output,{'reference_predictions':args.reference},['results','logs'])
BOOT=Path(args.bootstrap_dir).resolve(strict=True)
inputs={p.name:file_hash(p) for p in sorted(BOOT.glob('joint_*')) if p.is_file() and p.suffix in ['.json','.npz']}
(D/'bootstrap_input_hashes.json').write_text(json.dumps(inputs,indent=2),encoding='utf-8')
try:
 q=pd.read_parquet(Path(args.reference));q=q[q.dataset.eq('target')].reset_index(drop=True);years=np.arange(2015,2026);airports=sorted(q.airport_id.unique());meta=[json.loads(p.read_text()) for p in sorted(BOOT.glob('joint_???.json'))];assert len(meta)==500,len(meta)
 assert sorted(m['replicate'] for m in meta)==list(range(500)), 'Incomplete or duplicate replicate IDs'
 assert q.event_id.is_unique and len(airports)==8
 assert set(airports)=={'KDEN','KJFK','KMIA','KMSP','KBOS','KSFO','KSAT','KSTL'}
 assert np.isfinite(q.p_calibrated).all() and q.p_calibrated.between(0,1,inclusive='neither').all()
 records=[]
 def sample_years(rng,block):
  if not block:return rng.integers(0,11,11)
  starts=rng.integers(0,11,6);return np.ravel(np.c_[starts,(starts+1)%11])[:11]
 def summaries(p,rep,kind,nsamp,block=False):
  rng=np.random.default_rng(83720+rep+int(block)*10000);g=q.assign(p=p).groupby(['airport_id','year']).agg(n=('event_id','size'),o=('damage_binary','sum'),e=('p','sum')).reindex(pd.MultiIndex.from_product([airports,years]),fill_value=0).to_numpy().reshape(8,11,3)
  for j in range(nsamp):
   idx=sample_years(rng,block) if kind!='development_only' else np.arange(11);a=g[:,idx].sum(axis=1)
   for k,airport in enumerate(airports):
    n,o,e=a[k];records.append(dict(replicate=rep,sample=j,scope=kind,airport=airport,predicted=e/n,bias_pp=100*(e-o)/n,oe=o/e,observed_minus_expected=o-e))
 for m in meta:
  if m['success']:
   v=np.load(BOOT/f"joint_{m['replicate']:03}_predictions.npz",allow_pickle=args.trusted_object_arrays);event_ids=v['event_id'];assert pd.Index(event_ids).is_unique and len(event_ids)==len(q);idx=pd.Index(event_ids).get_indexer(q.event_id);assert min(idx)>=0;p=v['p'][idx];assert np.isfinite(p).all() and ((p>0)&(p<1)).all()
   summaries(p,m['replicate'],'development_only',1);summaries(p,m['replicate'],'joint_iid_year',20);summaries(p,m['replicate'],'joint_block2',20,True)
 summaries(q.p_calibrated.to_numpy(),-1,'fixed_iid_year',2000);summaries(q.p_calibrated.to_numpy(),-1,'fixed_block2',2000,True)
 v=pd.DataFrame(records);v.to_parquet(D/'results/local_bootstrap_values.parquet',index=False);rows=[]
 for (scope,airport),g in v.groupby(['scope','airport']):
  point=q[q.airport_id.eq(airport)];y=point.damage_binary;p=point.p_calibrated;pts=dict(predicted=p.mean(),bias_pp=100*(p.mean()-y.mean()),oe=y.sum()/p.sum(),observed_minus_expected=y.sum()-p.sum())
  for measure,point in pts.items():
   lo,hi=np.quantile(g[measure],[.025,.975]);row=dict(scope=scope,airport=airport,measure=measure,estimate=point,low=lo,high=hi,draws=len(g),development_fits=g.replicate.nunique() if scope.startswith(('joint','development')) else 0)
   if scope.startswith(('joint','development')):
    for tag,sub in [('first',g[g.replicate<250]),('second',g[g.replicate>=250])]:row[tag+'_low'],row[tag+'_high']=np.quantile(sub[measure],[.025,.975])
   rows.append(row)
 pd.DataFrame(rows).to_csv(D/'results/local_absolute_intervals.csv',index=False);summary=dict(attempts=500,successful=sum(m['success'] for m in meta),failures=[m['replicate'] for m in meta if not m['success']],selected_scales=pd.Series([m.get('scale') for m in meta if m['success']]).value_counts().to_dict(),sum_worker_seconds=sum(m['seconds'] for m in meta))
 (D/'results/bootstrap_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(summary);print(pd.DataFrame(rows).query("airport=='KJFK' and measure in ['bias_pp','oe']").to_string(index=False))
except Exception:
 (D/'logs/aggregation_failure.json').write_text(json.dumps({'traceback':traceback.format_exc()},indent=2),encoding='utf-8')
 raise
