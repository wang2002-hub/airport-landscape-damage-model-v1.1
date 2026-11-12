"""Nested selection, calibration and held-out evaluation of national references."""
from pathlib import Path
import sys,json,time,traceback,os
from model_core import *
import joblib
from concurrent.futures import ProcessPoolExecutor,as_completed
from run_support import prepare_output, validate_events

def configure(data, config, output):
 global DATA,P,W
 DATA=Path(data);P=json.loads(Path(config).read_text(encoding='utf-8'));W=Path(output)

def dump(obj,path):path.write_text(json.dumps(obj,indent=2,default=str),encoding='utf-8')
def checked_fit(d,kind,scale,bird,params,records,label,**kw):
 t=time.time();b=fit_bundle(d.reset_index(drop=True),kind=kind,scale=scale,geo=False,bird=bird,params=params,**kw)
 r={'label':label,'n':len(d),'airports':int(d.airport_id.nunique()),'damage':int(d.damage_binary.sum()),'seconds':time.time()-t}
 if kind=='glmm':
  r.update(b['model'].optim)
  # At a variance bound the constrained optimum need not have zero raw gradient.
  grad=b['model'].objective(b['model'].theta)[1].copy();rho=b['model'].theta[-1]
  if (rho<=-3.999 and grad[-1]>0) or (rho>=1.999 and grad[-1]<0):grad[-1]=0
  r['max_projected_gradient']=float(abs(grad).max());records.append(r)
  if not r['success'] or r['max_projected_gradient']>.025:raise RuntimeError('Unacceptable convergence '+str(r))
 else:records.append(r)
 return b
def task(args):
 scheme,fold,kind,block=args;tag=f'{scheme}_{fold}_{kind}_{block}';done=W/'results'/f'{tag}_config.json'
 if done.exists():raise FileExistsError('Task output already exists: '+tag)
 records=[];start=time.time()
 try:
  all_data=pd.read_parquet(DATA);validate_events(all_data);n=all_data[~all_data.target].copy();target=all_data[all_data.target].copy()
  if scheme=='temporal':
   train=n[n.year<=2022];cal=n[n.year.eq(2023)];test=n[n.year>=2024];inners=[(train[train.year<y],train[train.year.eq(y)]) for y in P['inner_temporal_years']]
  else:
   train=n[n.spatial_fold.ne(fold)];test=n[n.spatial_fold.eq(fold)];cal=None;inners=[(train[train.spatial_fold.ne(f)],train[train.spatial_fold.eq(f)]) for f in sorted(train.spatial_fold.unique())]
  assert not set(train.airport_id)&set(P['target_airports']);assert not set(test.event_id)&set(train.event_id)
  bird=int('B' in block);grid=P['hgb_candidates'] if kind=='hgb' else [None];opts=[]
  for scale in (P['scales'] if 'L' in block else [None]):
   for pi,params in enumerate(grid):
    losses=[];ips=[];ys=[]
    for j,(it,iv) in enumerate(inners):
     b=checked_fit(it,kind,scale,bird,params,records,f'{scale}_{pi}_inner{j}');p=predict_bundle(b,iv);y=iv.damage_binary.to_numpy(float);losses.append(float(np.mean(-y*np.log(p)-(1-y)*np.log1p(-p))));ips.append(p);ys.append(y)
    opts.append((float(np.mean(losses)),scale,pi,params,np.concatenate(ips),np.concatenate(ys),losses))
  best=min(enumerate(opts),key=lambda x:(x[1][0],x[0]))[1];loss,scale,pi,params,cp,cy,_=best
  b=checked_fit(train,kind,scale,bird,params,records,'final')
  if cal is not None:cp=predict_bundle(b,cal);cy=cal.damage_binary.to_numpy(float)
  b['calibrator'],cr=fit_calibrator(cy,cp);assert cr['success'];cr['bound_hit']=bool(abs(cr['slope']-.05)<1e-5 or abs(cr['slope']-5)<1e-5 or abs(cr['intercept'])>9.999)
  outs=[]
  for ds,sub in [('national',test)]+([('target',target)] if scheme=='temporal' else []):
   o=sub[['event_id','airport_id','year','damage_binary','spatial_fold']].copy();o['p_raw']=predict_bundle(b,sub);o['p_calibrated']=predict_bundle(b,sub,True);o['model']=block;o['family']=kind;o['scheme']=scheme;o['dataset']=ds;outs.append(o)
  pd.concat(outs).to_parquet(W/'results'/f'{tag}_predictions.parquet',index=False)
  config={'scheme':scheme,'fold':fold,'family':kind,'block':block,'selected_scale':scale,'params':params,'calibration':cr,'encoder':b['encoder'].metadata(),'test_qc':b['encoder'].qc(test),'target_qc':b['encoder'].qc(target),'candidates':[{'mean_logloss':x[0],'scale':x[1],'params':x[3],'fold_losses':x[6]} for x in opts],'fits':records,'seconds':time.time()-start}
  if kind=='glmm':b['model'].compact()
  joblib.dump(b,W/'models'/f'{tag}.joblib',compress=3);dump(config,done)
  return f'DONE {tag} scale={scale} seconds={time.time()-start:.1f}'
 except Exception:
  dump({'fits':records,'traceback':traceback.format_exc()},W/'logs'/f'{tag}_failure.json');return 'FAILED '+tag+' '+traceback.format_exc()
if __name__ == '__main__':
 import argparse
 parser=argparse.ArgumentParser(description='Fit national hierarchical and boosted-tree references with nested validation.')
 parser.add_argument('--data',required=True)
 parser.add_argument('--config',required=True)
 parser.add_argument('--output',required=True)
 parser.add_argument('--workers',type=int,default=2)
 parser.add_argument('--scheme',choices=['all','temporal','spatial'],default='all')
 parser.add_argument('--family',choices=['all','glmm','hgb'],default='all')
 parser.add_argument('--block',choices=['all','E','EL','EB','EBL'],default='all')
 args=parser.parse_args()
 if args.workers < 1:parser.error('--workers must be positive')
 output=prepare_output(args.output,{'analysis_events':args.data,'configuration':args.config},['results','models','logs'])
 configure(args.data,args.config,output)
 tasks=[(scheme,fold,kind,block) for scheme in ['temporal','spatial']
        for fold in ([0] if scheme=='temporal' else range(1,6))
        for kind in ['glmm','hgb'] for block in ['E','EL','EB','EBL']
        if args.scheme in ['all',scheme] and args.family in ['all',kind]
        and args.block in ['all',block]]
 dump({'tasks':tasks,'workers':args.workers,'threads_per_worker':2},output/'run_tasks.json')
 results=[]
 with ProcessPoolExecutor(max_workers=args.workers,initializer=configure,
                          initargs=(str(Path(args.data).resolve()),str(Path(args.config).resolve()),str(output))) as ex:
  for future in as_completed([ex.submit(task,x) for x in tasks]):
   result=future.result();results.append(result);print(result,flush=True)
 failures=[result for result in results if result.startswith('FAILED')]
 dump({'success':not failures,'completed_tasks':len(results)-len(failures),'failed_tasks':len(failures)},output/'run_status.json')
 if failures:raise SystemExit(1)
