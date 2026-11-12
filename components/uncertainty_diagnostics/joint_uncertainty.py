"""Airport-history resampling with nested selection and national calibration."""
from pathlib import Path
import sys,os,json,time,traceback
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
from model_core import *
from threadpoolctl import threadpool_limits
threadpool_limits(1)
from concurrent.futures import ProcessPoolExecutor,as_completed
from fit_references import checked_fit as fit
from run_support import prepare_output,validate_events
NATTEMPTS=500

def configure(data,config,output):
 global DATA,P,D
 DATA=Path(data);P=json.loads(Path(config).read_text(encoding='utf-8'));D=Path(output)
 threadpool_limits(1)

def run(rep):
 out=D/'results'/f'joint_{rep:03}.json'
 if out.exists():raise FileExistsError('Replicate already exists: '+str(rep))
 t=time.time();rec=[]
 try:
  d=pd.read_parquet(DATA);n=d[~d.target];target=d[d.target].copy();ids=sorted(n.airport_id.unique());rng=np.random.default_rng(P['seed']+rep);groups={a:g for a,g in n.groupby('airport_id')};parts=[]
  for j,a in enumerate(rng.choice(ids,len(ids),replace=True)):
   g=groups[a].copy();g['airport_id']=str(j)+'_'+a;parts.append(g)
  n=pd.concat(parts,ignore_index=True);tr=n[n.year<=2022];ca=n[n.year.eq(2023)];opts=[]
  for scale in P['scales']:
   ls=[]
   for yr in P['inner_temporal_years']:
    b=fit(tr[tr.year<yr],'glmm',scale,1,None,rec,f'{scale}_{yr}');v=tr[tr.year.eq(yr)];p=predict_bundle(b,v);y=v.damage_binary.to_numpy();ls.append(float(np.mean(-y*np.log(p)-(1-y)*np.log1p(-p))))
   opts.append((float(np.mean(ls)),scale))
  scale=min(enumerate(opts),key=lambda x:(x[1][0],x[0]))[1][1];b=fit(tr,'glmm',scale,1,None,rec,'final');b['calibrator'],cm=fit_calibrator(ca.damage_binary,predict_bundle(b,ca));assert cm['success'],cm;p=predict_bundle(b,target,True)
  np.savez_compressed(D/'results'/f'joint_{rep:03}_predictions.npz',event_id=target.event_id.to_numpy(dtype=str),p=p)
  obj={'replicate':rep,'success':True,'scale':scale,'seconds':time.time()-t,'calibration':cm,'fits':rec}
 except Exception:obj={'replicate':rep,'success':False,'seconds':time.time()-t,'error':traceback.format_exc(),'fits':rec}
 out.write_text(json.dumps(obj,indent=2),encoding='utf-8');return obj
if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser(description='National development bootstrap with target predictions and retained failed fits.')
 parser.add_argument('--data',required=True)
 parser.add_argument('--config',required=True)
 parser.add_argument('--output',required=True)
 parser.add_argument('--workers',type=int,default=2)
 parser.add_argument('--replicates',help='Comma-separated attempt IDs; default runs all IDs 0 through 499.')
 args=parser.parse_args()
 ids=list(range(NATTEMPTS)) if args.replicates is None else [int(x) for x in args.replicates.split(',')]
 if not ids or len(ids)!=len(set(ids)) or any(i<0 or i>=NATTEMPTS for i in ids):
  parser.error('Replicate IDs must be distinct integers from 0 to 499.')
 if args.workers<1:parser.error('--workers must be positive')
 validate_events(pd.read_parquet(args.data))
 output=prepare_output(args.output,{'analysis_events':args.data,'configuration':args.config},['results','logs'])
 configure(args.data,args.config,output)
 (output/'attempt_plan.json').write_text(json.dumps({'attempt_ids':ids,'workers':args.workers,'threads_per_worker':1},indent=2),encoding='utf-8')
 results=[]
 with ProcessPoolExecutor(max_workers=args.workers,initializer=configure,
      initargs=(str(Path(args.data).resolve()),str(Path(args.config).resolve()),str(output))) as ex:
  for future in as_completed([ex.submit(run,i) for i in ids]):
   obj=future.result();results.append(obj)
   print('rep',obj['replicate'],'success',obj['success'],flush=True)
 summary={'attempts_recorded':len(results),'successful':sum(x['success'] for x in results),
          'failed_ids':sorted(x['replicate'] for x in results if not x['success']),
          'complete_500_attempt_set':set(ids)==set(range(500)),
          'meaning':'Completion records all requested attempts, including numerical failures.'}
 (output/'run_status.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
 print(json.dumps(summary),flush=True)
