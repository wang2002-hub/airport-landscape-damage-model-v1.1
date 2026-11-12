"""Static 2015 canopy contrasts under annual and fixed land-cover inputs."""
from pathlib import Path
import argparse,json,time,traceback
import numpy as np,pandas as pd,joblib
from model_core import RandomInterceptLogit,fit_calibrator,predict_bundle,HistGradientBoostingClassifier
from enhanced_encoder import ExtendedEncoder
from run_support import prepare_output,validate_events
from sklearn.metrics import roc_auc_score,log_loss,brier_score_loss
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--inputs',required=True);parser.add_argument('--output',required=True);parser.add_argument('--family',choices=['all','glmm','hgb'],default='all');args=parser.parse_args()
manifest=Path(args.inputs).resolve(strict=True);bindings=json.loads(manifest.read_text(encoding='utf-8'))
paths={k:(manifest.parent/Path(v)).resolve(strict=True) for k,v in bindings['paths'].items()}
D=prepare_output(args.output,{'bindings':manifest,**paths},['results','models','logs'])
try:
 d=pd.read_parquet(paths['analysis_events']);validate_events(d)
 can=pd.read_csv(paths['canopy_measurements']);can=can[can.year.eq(2015)].copy()
 if can.duplicated(['airport_id','zone']).any():raise ValueError('Duplicate 2015 canopy key.')
 e=pd.read_parquet(paths['environment'])
 if e.duplicated(['airport_id','year']).any():raise ValueError('Duplicate environment key.')
 for zone in ['b03','b08','b13']:
  available=can[can.zone.eq(zone)].set_index('airport_id')
  means=d.airport_id.map(available.canopy_mean_pct);coverage=d.airport_id.map(available.canopy_coverage)
  if means.isna().any() or not means.between(0,100).all():raise ValueError('Incomplete or invalid 2015 canopy measurement.')
  if coverage.isna().any() or not coverage.ge(.95).all():raise ValueError('Insufficient 2015 canopy coverage.')
 if not set(d.airport_id)<=set(e.loc[e.year.eq(2015),'airport_id']):raise ValueError('Missing fixed-2015 environment key.')
except Exception:
 (D/'logs/input_failure.txt').write_text(traceback.format_exc(),encoding='utf-8');raise
for z in ['b03','b08','b13']:
 v=can[can.zone.eq(z)].set_index('airport_id');d['canopy_mean_pct__'+z]=d.airport_id.map(v.canopy_mean_pct);assert d['canopy_mean_pct__'+z].notna().all();assert d.airport_id.map(v.canopy_coverage).min()>=.95
fixed=d.copy();e=e[e.year.eq(2015)].set_index('airport_id')
for c in e:
 if '_fraction__' in c or c.startswith('impervious_mean_pct__'):fixed[c]=fixed.airport_id.map(e[c])
metrics=[];fail=[]
for family in ['glmm','hgb']:
 if args.family not in ['all',family]:continue
 config=json.loads(paths[family+'_config'].read_text(encoding='utf-8'));scale=config['selected_scale'];params=config['params'];jobs=[]
 for timing,data in [('annual',d),('fixed2015',fixed)]:
  for canopy in [False,True]:jobs.append((timing+('_canopy' if canopy else '_base'),'EBL',data,['canopy'] if canopy else []))
 for name,block,data,extras in jobs:
  key=f'{family}_{name}_{block}';start=time.time();print('START',key,flush=True)
  try:
   train=data[~data.target&data.year.le(2022)].copy();cal=data[~data.target&data.year.eq(2023)].copy();test=data[~data.target&data.year.ge(2024)].copy();target=data[data.target].copy()
   enc=ExtendedEncoder(scale if 'L' in block else None,int('B' in block),extras).fit(train);X=enc.transform(train);y=train.damage_binary.to_numpy(float)
   if family=='glmm':
    model=RandomInterceptLogit(maxiter=500).fit(X,y,train.airport_id);optim=model.optim.copy();grad=model.objective(model.theta)[1];rho=model.theta[-1]
    if rho<=-4+1e-6 and grad[-1]>0:grad[-1]=0
    if rho>=2-1e-6 and grad[-1]<0:grad[-1]=0
    optim['projected_max_abs_gradient']=float(abs(grad).max());assert optim['success'] and abs(grad).max()<=.025,optim
   else:model=HistGradientBoostingClassifier(**params,early_stopping=False,random_state=20261028).fit(X[:,1:],y);optim={'success':True}
   bundle={'encoder':enc,'model':model,'kind':family,'calibrator':None};p=predict_bundle(bundle,cal);bundle['calibrator'],calmeta=fit_calibrator(cal.damage_binary,p);assert calmeta['success']
   out=[]
   for label,v in [('national',test),('target',target)]:
    o=v[['event_id','airport_id','year','damage_binary']].copy();o['p_raw']=predict_bundle(bundle,v);o['p_calibrated']=predict_bundle(bundle,v,True);o['dataset']=label;out.append(o)
    subsets=[('all',o)]+([('recent',o[o.year.ge(2024)])] if label=='target' else [])
    for period,u in subsets:
     yy=u.damage_binary;pp=u.p_calibrated;metrics.append(dict(key=key,family=family,analysis=name,block=block,dataset=label,period=period,n=len(u),damages=int(yy.sum()),brier=brier_score_loss(yy,pp),logloss=log_loss(yy,pp),auc=roc_auc_score(yy,pp),bias_pp=100*(pp.mean()-yy.mean()),oe=float(yy.sum()/pp.sum())))
   pd.concat(out).to_parquet(D/'results'/f'{key}_predictions.parquet',index=False)
   meta=dict(key=key,seconds=time.time()-start,scale=enc.scale,params=params,optim=optim,calibration=calmeta,encoder=enc.metadata(),training_n=len(train),calibration_n=len(cal),test_n=len(test))
   (D/'results'/f'{key}_config.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
   if family=='glmm':model.compact()
   joblib.dump(bundle,D/'models'/f'{key}.joblib',compress=3)
   print('DONE',key,round(time.time()-start,1),metrics[-3:],flush=True)
  except Exception as ex:
   fail.append(dict(key=key,error=str(ex),traceback=traceback.format_exc()));print('FAILED',key,str(ex),flush=True)
  pd.DataFrame(metrics).to_csv(D/'results/canopy_metrics.csv',index=False);(D/'results/model_failures.json').write_text(json.dumps(fail,indent=2),encoding='utf-8')
print('FINISHED',len(metrics),'metric rows',len(fail),'failed fits',flush=True)

if fail:raise SystemExit(1)
