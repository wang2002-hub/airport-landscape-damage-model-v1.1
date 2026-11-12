from pathlib import Path
import sys,json,time,traceback
from model_core import Encoder,RandomInterceptLogit
import numpy as np,pandas as pd
from scipy.special import expit
from scipy.stats import norm,rankdata
from scipy.integrate import quad
from threadpoolctl import threadpool_limits
threadpool_limits(2)
import argparse
from run_support import prepare_output,validate_events
parser=argparse.ArgumentParser(description='Conditional airport effects and rank uncertainty at fitted hyperparameters.')
for key in ['data','profiles','output']:parser.add_argument('--'+key,required=True)
args=parser.parse_args()
out=prepare_output(args.output,{'analysis_events':args.data,'national_profiles':args.profiles},['results','logs'])
O=out/'results';start=time.perf_counter()
try:
 d=pd.read_parquet(Path(args.data)).reset_index(drop=True);validate_events(d)
 enc=Encoder('b03',False,1).fit(d);X=enc.transform(d);m=RandomInterceptLogit(maxiter=1000).fit(X,d.damage_binary.to_numpy(),d.airport_id.to_numpy())
 (O/'partial_pooling_optimization.json').write_text(json.dumps(m.optim,indent=2),encoding='utf-8')
 assert m.optim['success'] and m.optim['max_abs_gradient']<.025 and not m.optim['rho_boundary'],m.optim
 eta=X@m.coef;rng=np.random.default_rng(20261102);width=max(8*m.sigma,8);grid=np.linspace(-width,width,4001);draws=np.empty((5000,m.G));rows=[];checks=[]
 # Exact conditional univariate posterior at plug-in beta/tau, evaluated on a fine grid.
 for j,a in enumerate(m.groups):
  ix=np.flatnonzero(m.g==j);e=eta[ix];yy=d.damage_binary.to_numpy()[ix];obs=int(yy.sum())
  ll=np.empty(len(grid))
  for k in range(0,len(grid),100):
   z=e[:,None]+grid[None,k:k+100];ll[k:k+100]=obs*grid[k:k+100]-np.logaddexp(0,z).sum(axis=0)-.5*(grid[k:k+100]/m.sigma)**2
  w=np.exp(ll-ll.max());mass=w/w.sum();assert mass[0]+mass[-1]<1e-8
  cdf=np.cumsum(mass);mean=float(mass@grid);lo,hi=np.interp([.025,.975],cdf,grid);draws[:,j]=np.interp(rng.random(5000),cdf,grid)
  rows.append(dict(airport=a,n=len(ix),damage=obs,conditional_mean_b=mean,conditional_mode_b=m.b_mode[j],low_b=lo,high_b=hi,conditional_odds_multiplier=np.exp(mean),odds_low=np.exp(lo),odds_high=np.exp(hi),target=bool(d.iloc[ix[0]].target)))
  if a in ['KJFK','KDEN'] or len(checks)<2:
   def f(b):return float(np.exp(obs*b-np.logaddexp(0,e+b).sum()-.5*(b/m.sigma)**2-ll.max()))
   den=quad(f,-width,width,epsabs=1e-9)[0];v=quad(lambda b:b*f(b),-width,width,epsabs=1e-9)[0]/den
   assert abs(v-mean)<1e-5;checks.append(dict(airport=a,grid_mean=mean,adaptive_mean=v))
  if j%250==0:print('Conditional densities',j,'of',m.G,flush=True)
 ranks=np.empty_like(draws)
 for i in range(len(draws)):ranks[i]=rankdata(-draws[i],method='average')
 res=pd.DataFrame(rows)
 for name,values in [('mean',ranks.mean(axis=0)),('low',np.quantile(ranks,.025,axis=0)),('high',np.quantile(ranks,.975,axis=0)),('half1_low',np.quantile(ranks[:2500],.025,axis=0)),('half2_low',np.quantile(ranks[2500:],.025,axis=0)),('half1_high',np.quantile(ranks[:2500],.975,axis=0)),('half2_high',np.quantile(ranks[2500:],.975,axis=0))]:res['rank_'+name]=values
 res.to_csv(O/'airport_partial_pooling.csv',index=False)
 national=pd.read_csv(Path(args.profiles)).query("model=='glmm_EBL'")[['airport','OE','E']];res.merge(national,on='airport',how='left').to_csv(O/'partial_pooling_vs_external_ratio.csv',index=False)
 meta=dict(optim=m.optim,n=len(d),airports=m.G,encoder=enc.metadata(),coefficients=m.coef.tolist(),tau=m.sigma,MOR=float(np.exp(np.sqrt(2)*norm.ppf(.75)*m.sigma)),posterior_draws=5000,seed=20261102,quadrature_checks=checks,median_rank_width=float(np.median(res.rank_high-res.rank_low)),seconds=time.perf_counter()-start,scope='Full-data explanatory EBL fit including targets; exact-grid conditional posterior at estimated beta/tau. Intervals omit hyperparameter uncertainty; ranks are not safety ranks or out-of-sample validation.')
 (O/'partial_pooling_fit.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
 print(res[res.target][['airport','conditional_mean_b','low_b','high_b','rank_low','rank_high']].to_string(index=False));print('tau',m.sigma,'MOR',meta['MOR'],'median rank width',meta['median_rank_width'])
except Exception:
 (O/'partial_pooling_failure.txt').write_text(traceback.format_exc(),encoding='utf-8');raise
