"""Exploratory damage-extent coding model and observed-population diagnostics."""
from pathlib import Path
import sys,os,json,time,traceback,hashlib
from model_core import Encoder,fit_calibrator
import numpy as np,pandas as pd
from scipy.optimize import minimize
from scipy.special import expit,logit
from threadpoolctl import threadpool_limits
threadpool_limits(1)
import argparse
from run_support import prepare_output,validate_events
parser=argparse.ArgumentParser(description='Conditional M? coding diagnostics with frozen-reference and restricted-population summaries.')
for key in ['data','reference','restriction','labels','output']:
 parser.add_argument('--'+key,required=True)
args=parser.parse_args()
out=prepare_output(args.output,{key:getattr(args,key) for key in ['data','reference','restriction','labels']},['results','logs'])
O=out/'results';records=[];start=time.perf_counter()
try:
 d=pd.read_parquet(Path(args.data));validate_events(d);nat=d[~d.target];tr=nat[(nat.year<=2022)&nat.damage_binary.eq(1)].copy().reset_index(drop=True)
 ca=nat[nat.year.eq(2023)&nat.damage_binary.eq(1)].copy().reset_index(drop=True)
 assert not set(tr.airport_id)&set(d[d.target].airport_id)
 enc=Encoder(None,False,1).fit(tr);X=enc.transform(tr);y=tr.DAMAGE_LEVEL.eq('M?').to_numpy(float);pen=np.ones(X.shape[1]);pen[0]=0
 def obj(b):
  z=X@b;return np.logaddexp(0,z).sum()-y@z+.5e-4*np.sum(pen*b*b),X.T@(expit(z)-y)+1e-4*pen*b
 b=np.zeros(X.shape[1]);b[0]=logit(y.mean())
 for k in range(2):
  fit=minimize(obj,b,jac=True,method='L-BFGS-B',options={'maxiter':1500,'ftol':1e-12 if k==0 else 1e-14,'gtol':1e-7,'maxls':40});b=fit.x
  records.append(dict(attempt=k,success=bool(fit.success),gradient=float(abs(fit.jac).max()),message=str(fit.message)))
  if fit.success and abs(fit.jac).max()<.025:break
 assert fit.success and abs(fit.jac).max()<.025
 cal,cm=fit_calibrator(ca.DAMAGE_LEVEL.eq('M?').to_numpy(float),expit(enc.transform(ca)@b));assert cm['success']
 def predict(v):return expit(cal[0]+cal[1]*(enc.transform(v)@b))
 metrics=[]
 for label,v in [('national_test',nat[(nat.year>=2024)&nat.damage_binary.eq(1)]),('target_damaged',d[d.target&d.damage_binary.eq(1)])]:
  q=predict(v);yy=v.DAMAGE_LEVEL.eq('M?').to_numpy(float)
  metrics.append(dict(population=label,n=len(v),undetermined=int(yy.sum()),expected_undetermined=q.sum(),brier=np.mean((yy-q)**2),logloss=-np.mean(yy*np.log(q)+(1-yy)*np.log1p(-q)),mean_q=q.mean()))
 pd.DataFrame(metrics).to_csv(O/'coding_model_performance.csv',index=False)
 pred=pd.read_parquet(Path(args.reference));pred=pred[pred.dataset=='target'][['event_id','p_calibrated']]
 assert pred.event_id.is_unique and set(pred.event_id)==set(d.loc[d.target,'event_id'])
 tar=d[d.target].merge(pred,on='event_id',validate='one_to_one');assert np.isfinite(tar.p_calibrated).all() and tar.p_calibrated.between(0,1,inclusive='neither').all();tar['q_undetermined']=predict(tar)
 tar['p_undetermined']=tar.p_calibrated*tar.q_undetermined;tar['p_documented']=tar.p_calibrated*(1-tar.q_undetermined)
 tar[['event_id','airport_id','year','damage_binary','DAMAGE_LEVEL','p_calibrated','q_undetermined','p_undetermined','p_documented']].to_parquet(O/'coding_target_predictions_private.parquet',index=False)
 refit=pd.read_csv(Path(args.restriction));labels=pd.read_csv(Path(args.labels)).set_index('airport_id')
 decomposition=[];restriction=[];missing=[]
 for a,g in tar.groupby('airport_id'):
  yy=g.damage_binary.eq(1);u=g.DAMAGE_LEVEL.eq('M?');e=g.p_calibrated.sum();eu=g.p_undetermined.sum();ed=g.p_documented.sum();assert np.isclose(e,eu+ed)
  decomposition.append(dict(airport=a,n=len(g),O=int(yy.sum()),E=e,O_undetermined=int(u.sum()),E_undetermined=eu,OE_undetermined=u.sum()/eu,O_documented=int((yy&~u).sum()),E_documented=ed,OE_documented=(yy&~u).sum()/ed,conditional_damaged_n=int(yy.sum()),conditional_expected_undetermined=g.loc[yy,'q_undetermined'].sum(),conditional_OE_undetermined=u.sum()/g.loc[yy,'q_undetermined'].sum(),undetermined_discrepancy=u.sum()-eu,documented_discrepancy=(yy&~u).sum()-ed))
  r=refit[refit.airport==a[1:]].iloc[0];v=g[~u];assert len(v)==r.restricted_n and v.damage_binary.sum()==r.restricted_damage
  restriction.append(dict(airport=a,full_n=len(g),full_O=int(yy.sum()),full_E=e,full_OE=yy.sum()/e,restricted_n=len(v),restricted_O=int(v.damage_binary.sum()),frozen_restricted_E=v.p_calibrated.sum(),frozen_restricted_OE=v.damage_binary.sum()/v.p_calibrated.sum(),refitted_restricted_E=r.restricted_expected,refitted_restricted_OE=r.restricted_oe))
  l=labels.loc[a];assert int(l.known)==len(g);m=int(l.near-l.known);N=int(l.near);o=int(yy.sum());benchmark=e/len(g);threshold=(N*benchmark-o)/m
  missing.append(dict(airport=a,known_n=len(g),unknown_n=m,all_near_n=N,known_damage=o,lower_damage_proportion=o/N,upper_damage_proportion=(o+m)/N,known_reference_mean=benchmark,hypothetical_missing_rate_for_same_proportion=threshold,threshold_feasible=bool(0<=threshold<=1)))
 pd.DataFrame(decomposition).to_csv(O/'damage_subtype_decomposition.csv',index=False)
 pd.DataFrame(restriction).to_csv(O/'extent_population_and_refit.csv',index=False)
 pd.DataFrame(missing).to_csv(O/'missing_label_bounds.csv',index=False)
 meta=dict(training_reports=len(tr),training_undetermined=int(y.sum()),training_airports=int(tr.airport_id.nunique()),calibration=cm,attempts=records,encoder=enc.metadata(),beta=b.tolist(),calibrator=cal.tolist(),seconds=time.perf_counter()-start,input_sha256=hashlib.sha256((Path(args.data)).read_bytes()).hexdigest(),scope='Exploratory conditional coding model; no target fitting; point subtype expectations, without development uncertainty intervals.')
 (O/'coding_model_fit.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
 print(pd.DataFrame(decomposition).query("airport=='KJFK'").to_string(index=False));print(pd.DataFrame(restriction).query("airport=='KJFK'").to_string(index=False));print(pd.DataFrame(metrics).to_string(index=False))
except Exception:
 (O/'coding_model_failure.json').write_text(json.dumps({'attempts':records,'traceback':traceback.format_exc()},indent=2),encoding='utf-8');raise
