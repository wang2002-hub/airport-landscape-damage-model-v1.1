"""Airport-history bootstrap of the EB-to-EBL development pipeline."""
from pathlib import Path
import argparse,json,time,traceback
from model_core import *
from model_fitting import checked_fit
from run_support import prepare_output,validate_events
from concurrent.futures import ProcessPoolExecutor,as_completed

def configure(data,config,output):
 global DATA,P,W
 DATA=Path(data);P=json.loads(Path(config).read_text(encoding='utf-8'));W=Path(output)

def losses(y,p):return np.array([np.mean((y-p)**2),np.mean(-y*np.log(p)-(1-y)*np.log1p(-p))])
def run(rep):
 path=W/'results'/f'bootstrap_{rep:03d}.json'
 if path.exists():raise FileExistsError('Attempt output already exists.')
 records=[];t=time.time()
 try:
  d=pd.read_parquet(DATA);n=d[~d.target];target=d[d.target];ids=sorted(n.airport_id.unique());rng=np.random.default_rng(P['seed']+rep)
  groups={aid:g for aid,g in n.groupby('airport_id')};parts=[]
  for j,aid in enumerate(rng.choice(ids,len(ids),replace=True)):
   g=groups[aid].copy();g['airport_id']=str(j)+'_'+aid;parts.append(g)
  n=pd.concat(parts,ignore_index=True);train=n[n.year<=2022];cal=n[n.year.eq(2023)];test=n[n.year>=2024];pred={};selected={}
  for block in ['EB','EBL']:
   opts=[]
   for scale in (P['scales'] if block=='EBL' else [None]):
    ls=[]
    for yr in P['inner_temporal_years']:
     it=train[train.year<yr];iv=train[train.year.eq(yr)];b=checked_fit(it,'glmm',scale,1,None,records,f'{block}_{scale}_{yr}');ls.append(losses(iv.damage_binary.to_numpy(),predict_bundle(b,iv))[1])
    opts.append((float(np.mean(ls)),scale))
   scale=min(enumerate(opts),key=lambda x:(x[1][0],x[0]))[1][1];selected[block]=scale
   b=checked_fit(train,'glmm',scale,1,None,records,f'{block}_final');b['calibrator'],cr=fit_calibrator(cal.damage_binary.to_numpy(),predict_bundle(b,cal));assert cr['success']
   pred[block]={'national':predict_bundle(b,test,True),'target':predict_bundle(b,target,True)}
  rows=[]
  for ds,sub in [('national',test),('target',target)]:
   for aid,ix in [('pooled',np.ones(len(sub),bool))]+([(aid,sub.airport_id.eq(aid).to_numpy()) for aid in P['target_airports']] if ds=='target' else []):
    y=sub.damage_binary.to_numpy()[ix];delta=losses(y,pred['EBL'][ds][ix])-losses(y,pred['EB'][ds][ix]);rows.append({'dataset':ds,'airport':aid,'delta_brier':float(delta[0]),'delta_logloss':float(delta[1])})
  obj={'replicate':rep,'success':True,'seconds':time.time()-t,'selected':selected,'rows':rows,'fits':records}
 except Exception:obj={'replicate':rep,'success':False,'seconds':time.time()-t,'error':traceback.format_exc(),'fits':records}
 path.write_text(json.dumps(obj,indent=2));return f"rep {rep} success={obj['success']} seconds={time.time()-t:.1f}"

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--data',required=True);parser.add_argument('--config',required=True);parser.add_argument('--output',required=True);parser.add_argument('--workers',type=int,default=2);parser.add_argument('--attempts',default='all',help='all or comma-separated unique original attempt IDs, 0 through 199');args=parser.parse_args()
 if args.workers<1:parser.error('workers must be positive')
 attempts=list(range(200)) if args.attempts=='all' else [int(x) for x in args.attempts.split(',')]
 if not attempts or len(attempts)!=len(set(attempts)) or not all(0<=x<200 for x in attempts):parser.error('Attempt IDs must be unique integers from 0 through 199.')
 output=prepare_output(args.output,{'analysis_events':args.data,'configuration':args.config},['results','logs'])
 configure(args.data,args.config,output)
 try:
  validate_events(pd.read_parquet(DATA))
  if P['inner_temporal_years']!=[2019,2020,2021,2022]:raise ValueError('Unexpected inner temporal years.')
  if P['scales']!=['b03','b08','b13','rings']:raise ValueError('Unexpected landscape candidates.')
 except Exception:
  (output/'logs/input_failure.txt').write_text(traceback.format_exc(),encoding='utf-8');raise
 scope={'primary_contrast':'EB to EBL','family':'GLMM','attempt_ids':attempts,'workers':args.workers,'threads_per_worker':2,'resampling':'Complete national airport histories; duplicate copies receive distinct random-intercept identifiers.','target_uncertainty':'Fixed target reports; development-pipeline variation only.','selection':'Repeat preprocessing, scale selection, fitting and 2023 calibration.'}
 (output/'bootstrap_scope.json').write_text(json.dumps(scope,indent=2),encoding='utf-8')
 with ProcessPoolExecutor(max_workers=args.workers,initializer=configure,initargs=(str(Path(args.data).resolve()),str(Path(args.config).resolve()),str(output))) as pool:
  for future in as_completed([pool.submit(run,i) for i in attempts]):print(future.result(),flush=True)
 records=[json.loads((output/'results'/f'bootstrap_{i:03d}.json').read_text(encoding='utf-8')) for i in attempts]
 failed=[r['replicate'] for r in records if not r['success']]
 (output/'run_status.json').write_text(json.dumps({'recorded_attempts':len(records),'successful_attempts':len(records)-len(failed),'failed_attempts':failed},indent=2),encoding='utf-8')
 if failed:raise SystemExit(2)
