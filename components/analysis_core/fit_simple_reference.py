"""Fixed-effect logistic EB comparator with training-only encoding."""
from pathlib import Path
import os,sys,json,time,traceback,hashlib,argparse,platform
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
from model_core import Encoder,fit_calibrator
import numpy as np,pandas as pd,scipy,sklearn,joblib
from scipy.optimize import minimize
from scipy.special import expit,logit
from threadpoolctl import threadpool_limits,threadpool_info
threadpool_limits(1)
from run_support import prepare_output, validate_events
parser=argparse.ArgumentParser(description='Fit and calibrate the simple EB reference on the retained validation splits.')
parser.add_argument('--data', required=True)
parser.add_argument('--output', required=True)
args=parser.parse_args()
D=prepare_output(args.output, {'analysis_events': args.data}, ['results','models','logs'])
start=time.perf_counter();cpu0=time.process_time();records=[]
def fit(df,label):
 t=time.perf_counter();df=df.reset_index(drop=True);enc=Encoder(None,False,1).fit(df);X=enc.transform(df);y=df.damage_binary.to_numpy(float);pen=np.ones(X.shape[1]);pen[0]=0;ridge=1e-4
 def fun(beta):
  z=X@beta;p=expit(z);return np.sum(np.logaddexp(0,z)-y*z)+.5*ridge*np.sum(pen*beta**2), X.T@(p-y)+ridge*pen*beta
 beta=np.zeros(X.shape[1]);beta[0]=logit(y.mean());attempts=[]
 for attempt in range(2):
  r=minimize(fun,beta,jac=True,method='L-BFGS-B',options={'maxiter':1000,'ftol':1e-12 if attempt==0 else 1e-14,'gtol':1e-7,'maxls':40,'maxcor':30});attempts.append(dict(attempt=attempt,success=bool(r.success),message=str(r.message),iterations=int(r.nit),gradient=float(abs(r.jac).max()),objective=float(r.fun)));beta=r.x
  if r.success and abs(r.jac).max()<=.025:break
 record=dict(label=label,n=len(df),airports=int(df.airport_id.nunique()),damage=int(y.sum()),features=X.shape[1],seconds=time.perf_counter()-t,attempts=attempts);records.append(record)
 assert r.success and abs(r.jac).max()<=.025,record
 return dict(encoder=enc,beta=r.x,calibrator=None)
def predict(b,df,calibrated=False):
 p=np.clip(expit(b['encoder'].transform(df)@b['beta']),1e-8,1-1e-8)
 if calibrated:p=np.clip(expit(b['calibrator'][0]+b['calibrator'][1]*logit(p)),1e-8,1-1e-8)
 return p
try:
 data=pd.read_parquet(Path(args.data));validate_events(data)
 nat=data[~data.target];tar=data[data.target];targets=set(tar.airport_id);outputs=[];settings=[]
 for scheme,fold in [('temporal',0)]+[('spatial',i) for i in range(1,6)]:
  if scheme=='temporal':
   tr=nat[nat.year<=2022];ca=nat[nat.year.eq(2023)];te=nat[nat.year>=2024];b=fit(tr,'temporal_final');cp=predict(b,ca);cy=ca.damage_binary.to_numpy()
  else:
   tr=nat[nat.spatial_fold.ne(fold)];te=nat[nat.spatial_fold.eq(fold)];cp=[];cy=[]
   for f in sorted(tr.spatial_fold.unique()):
    it=tr[tr.spatial_fold.ne(f)];iv=tr[tr.spatial_fold.eq(f)];inner=fit(it,f'spatial_{fold}_inner_{f}');cp.extend(predict(inner,iv));cy.extend(iv.damage_binary)
   b=fit(tr,f'spatial_{fold}_final');cp=np.array(cp);cy=np.array(cy)
  assert not set(tr.airport_id)&targets;assert not set(tr.event_id)&set(te.event_id)
  b['calibrator'],cm=fit_calibrator(cy,cp);assert cm['success'],cm
  populations=[('national',te)]+([('target',tar)] if scheme=='temporal' else [])
  for ds,v in populations:
   q=v[['event_id','airport_id','year','damage_binary','spatial_fold']].copy();q['p_raw']=predict(b,v);q['p_calibrated']=predict(b,v,True);q['dataset']=ds;q['scheme']=scheme;q['fold']=fold;q['family']='simple';q['model']='EB';outputs.append(q)
  settings.append(dict(scheme=scheme,fold=fold,calibration=cm,encoding=b['encoder'].metadata()))
  joblib.dump(b,D/'models'/f'{scheme}_{fold}_simple_EB.joblib',compress=3)
  print('Fitted',scheme,fold,'training',len(tr),'test',len(te),flush=True)
 result=pd.concat(outputs,ignore_index=True);result.to_parquet(D/'results/simple_predictions.parquet',index=False)
 pd.DataFrame({'feature':settings[0]['encoding']['feature_names'],'coefficient':joblib.load(D/'models/temporal_0_simple_EB.joblib')['beta']}).to_csv(D/'results/simple_coefficients.csv',index=False)
 meta=dict(success=True,wall_seconds=time.perf_counter()-start,cpu_seconds=time.process_time()-cpu0,python=sys.version,numpy=np.__version__,pandas=pd.__version__,scipy=scipy.__version__,scikit_learn=sklearn.__version__,platform=platform.platform(),processor=platform.processor(),threadpools=[{k:v for k,v in pool.items() if k!='filepath'} for pool in threadpool_info()],input_sha256=hashlib.sha256((Path(args.data)).read_bytes()).hexdigest(),fits=records,settings=settings,prediction_rows=len(result))
 (D/'results/simple_run.json').write_text(json.dumps(meta,indent=2),encoding='utf-8');print('COMPLETE',meta['wall_seconds'],len(records),flush=True)
except Exception:
 (D/'logs/simple_failure.json').write_text(json.dumps({'fits':records,'traceback':traceback.format_exc()},indent=2),encoding='utf-8');raise
