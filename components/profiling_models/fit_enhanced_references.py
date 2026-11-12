from pathlib import Path
import sys,os,json,time
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
from model_core import *
from enhanced_encoder import ExtendedEncoder
from threadpoolctl import threadpool_limits
threadpool_limits(1)
import joblib
from sklearn.metrics import roc_auc_score,log_loss,brier_score_loss
import argparse,traceback
from run_support import prepare_output,validate_events
parser=argparse.ArgumentParser(description='Enhanced event references with temporal selection and paired landscape comparisons.')
for key in ['data','config','features','output']:parser.add_argument('--'+key,required=True)
args=parser.parse_args()
D=prepare_output(args.output,{key:getattr(args,key) for key in ['data','config','features']},['results','models','logs'])
P=json.loads(Path(args.config).read_text(encoding='utf-8'))
extra=json.loads(Path(args.features).read_text(encoding='utf-8'))['extra']
records=[]
try:
 d=pd.read_parquet(Path(args.data));validate_events(d);n=d[~d.target];tr=n[n.year<=2022];ca=n[n.year.eq(2023)];te=n[n.year>=2024];tar=d[d.target];records=[]
 def fit(data,family,scale,bird,params,label):
  t=time.time();enc=ExtendedEncoder(scale,bird,extra).fit(data);X=enc.transform(data);y=data.damage_binary.to_numpy(float)
  if family=='glmm':
   model=RandomInterceptLogit(maxiter=500).fit(X,y,data.airport_id);g=model.objective(model.theta)[1];rho=model.theta[-1]
   if (rho<=-3.999 and g[-1]>0) or (rho>=1.999 and g[-1]<0):g[-1]=0
   info={**model.optim,'projected_gradient':float(abs(g).max())};assert info['success'] and abs(g).max()<=.025,info
  else:model=HistGradientBoostingClassifier(**params,early_stopping=False,random_state=P['seed']).fit(X[:,1:],y);info={'success':True}
  records.append(dict(label=label,n=len(data),seconds=time.time()-t,**info));return dict(encoder=enc,model=model,kind=family,calibrator=None)
 metrics=[]
 for family in ['glmm','hgb']:
  for block in ['E','EL','EB','EBL']:
   key=family+'_'+block;t=time.time();records=[];opts=[]
   for scale in (P['scales'] if 'L' in block else [None]):
    for params in (P['hgb_candidates'] if family=='hgb' else [None]):
     ls=[]
     for yr in P['inner_temporal_years']:
      b=fit(tr[tr.year<yr],family,scale,int('B' in block),params,f'{scale}_{params}_{yr}');v=tr[tr.year.eq(yr)];ls.append(log_loss(v.damage_binary,predict_bundle(b,v)))
     opts.append(dict(scale=scale,params=params,fold_losses=ls,loss=float(np.mean(ls))))
   best=min(enumerate(opts),key=lambda x:(x[1]['loss'],x[0]))[1];b=fit(tr,family,best['scale'],int('B' in block),best['params'],'final');b['calibrator'],cm=fit_calibrator(ca.damage_binary,predict_bundle(b,ca));assert cm['success'];out=[]
   for name,v in [('national',te),('target',tar)]:
    q=v[['event_id','airport_id','year','damage_binary']].copy();q['p_calibrated']=predict_bundle(b,v,True);q['dataset']=name;out.append(q);y=q.damage_binary;p=q.p_calibrated
    metrics.append(dict(family=family,block=block,dataset=name,scale=best['scale'],brier=brier_score_loss(y,p),logloss=log_loss(y,p),auc=roc_auc_score(y,p),bias_pp=100*(p.mean()-y.mean()),oe=y.sum()/p.sum()))
   pd.concat(out).to_parquet(D/'results'/f'enhanced_{key}_predictions.parquet',index=False)
   meta=dict(family=family,block=block,selected=best,candidates=opts,fits=records,calibration=cm,encoder=b['encoder'].metadata(),seconds=time.time()-t)
   (D/'results'/f'enhanced_{key}_config.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
   if family=='glmm':b['model'].compact()
   joblib.dump(b,D/'models'/f'enhanced_{key}.joblib',compress=3);print('DONE',key,best['scale'],round(time.time()-t,1),flush=True)
 pd.DataFrame(metrics).to_csv(D/'results/enhanced_metrics.csv',index=False)
 rows=[]
 for family in ['glmm','hgb']:
  for base,aug in [('E','EL'),('EB','EBL')]:
   a=pd.read_parquet(D/'results'/f'enhanced_{family}_{base}_predictions.parquet');a=a[a.dataset.eq('national')].set_index('event_id');b=pd.read_parquet(D/'results'/f'enhanced_{family}_{aug}_predictions.parquet').set_index('event_id').loc[a.index];diff=(b.p_calibrated-a.damage_binary)**2-(a.p_calibrated-a.damage_binary)**2
   g=pd.DataFrame({'a':a.airport_id,'diff':diff}).groupby('a')['diff'].agg(['sum','size']).to_numpy();rng=np.random.default_rng(20261028);vals=[]
   for i in range(2000):v=g[rng.integers(len(g),size=len(g))];vals.append(v[:,0].sum()/v[:,1].sum())
   lo,hi=np.quantile(vals,[.025,.975]);rows.append(dict(family=family,contrast=aug+' minus '+base,delta=float(diff.mean()),low=lo,high=hi))
 pd.DataFrame(rows).to_csv(D/'results/enhanced_contrasts.csv',index=False);print(rows,flush=True)
except Exception:
 (D/'logs/enhanced_failure.json').write_text(json.dumps({'fits':records,'traceback':traceback.format_exc()},indent=2),encoding='utf-8')
 raise
