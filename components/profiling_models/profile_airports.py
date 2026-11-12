from pathlib import Path
import sys,json,hashlib,itertools
import numpy as np
import pandas as pd
from scipy.stats import norm,spearmanr,kendalltau
import argparse,traceback
from profile_inputs import configure,valid_predictions,validate_events
args,out=configure(argparse.ArgumentParser(description='National airport profiles and paired target comparisons.'),['draws','intervals'])
O=out/'results' 
sources=[]
def read(rel):
 p=Path(rel);sources.append({'filename':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
 return pd.read_parquet(p) if p.suffix=='.parquet' else pd.read_csv(p)
try:
 cohort=read(args.data);validate_events(cohort)
 A=['KDEN','KJFK','KMIA','KMSP','KBOS','KSFO','KSAT','KSTL']
 expected=set(cohort.loc[~cohort.airport_id.isin(A),'event_id'])
 models={}
 for family,block in [('glmm','EB'),('glmm','EBL'),('hgb','EB'),('hgb','EBL')]:
  d=pd.concat([read(Path(args.national_dir)/f'spatial_{k}_{family}_{block}_predictions.parquet') for k in range(1,6)],ignore_index=True)
  d=d[d.dataset=='national'];assert len(d)==46167 and set(d.event_id)==expected and not d.event_id.duplicated().any()
  assert d.groupby('airport_id').spatial_fold.nunique().max()==1
  models[family+'_'+block]=d
 d=read(args.simple);d=d[(d.scheme=='spatial')&(d.dataset=='national')]
 assert len(d)==46167 and set(d.event_id)==expected
 models['ordinary_EB']=d
 for frame in models.values():valid_predictions(frame)
 def pb(p):
  f=np.ones(1)
  for v in p:
   g=np.zeros(len(f)+1);g[:-1]+=f*(1-v);g[1:]+=f*v;f=g
  assert np.isclose(f.sum(),1)
  return f
 profiles=[]
 for name,d in models.items():
  check=d.merge(cohort[['event_id','damage_binary']],on='event_id',validate='one_to_one',suffixes=('','_check'))
  assert (check.damage_binary==check.damage_binary_check).all()
  for a,g in d.groupby('airport_id'):
   p=g.p_calibrated.to_numpy();n=len(g);obs=int(g.damage_binary.sum());e=p.sum();v=(p*(1-p)).sum();pmf=pb(p);cdf=np.cumsum(pmf)
   row={'model':name,'airport':a,'n':n,'O':obs,'E':e,'OE':obs/e,'variance':v,'z':(obs-e)/np.sqrt(v),'p_conditional':min(1,2*min(cdf[obs],pmf[obs:].sum()))}
   for alpha,label in [(.05,'95'),(.002,'998')]:
    lo=np.searchsorted(cdf,alpha/2);hi=np.searchsorted(cdf,1-alpha/2)
    row.update({f'low_{label}':lo/e,f'high_{label}':hi/e,f'flag_{label}':bool(obs<lo or obs>hi)})
   profiles.append(row)
 profiles=pd.DataFrame(profiles);assert profiles.groupby('model').size().eq(1375).all()
 disp=[]
 for name,g in profiles.groupby('model'):
  phi=max(1,float(np.mean(g.z**2)))
  profiles.loc[g.index,'phi']=phi
  profiles.loc[g.index,'z_dispersion']=g.z/np.sqrt(phi)
  for subset,h in [('all',g),('expected_ge5',g[g.E>=5]),('reports_ge100',g[g.n>=100])]:
   disp.append({'model':name,'subset':subset,'airports':len(h),'zero_outcomes':int(h.O.eq(0).sum()),'conditional_flags_998':int(h.flag_998.sum()),'nominal_expected_flags':.002*len(h),'phi_all':phi,'adjusted_normal_flags':int((abs(h.z)/np.sqrt(phi)>norm.ppf(.999)).sum())})
 profiles.to_csv(O/'national_profiles.csv',index=False);pd.DataFrame(disp).to_csv(O/'national_dispersion_sensitivity.csv',index=False)
 wide=profiles.pivot(index='airport',columns='model',values='OE');ranks=[]
 for label,ids in [('all',wide.index),('primary_expected_ge5',profiles.query("model=='glmm_EBL' and E>=5").airport)]:
  z=wide.loc[ids];k=max(1,int(np.ceil(len(z)*.1)))
  for a,b in itertools.combinations(z.columns,2):
   def jacc(x,y):return len(x&y)/len(x|y) if x|y else np.nan
   # Include boundary ties rather than choosing arbitrary airport identifiers.
   topa=set(z.index[z[a]>=z[a].nlargest(k).min()]);topb=set(z.index[z[b]>=z[b].nlargest(k).min()])
   bota=set(z.index[z[a]<=z[a].nsmallest(k).max()]);botb=set(z.index[z[b]<=z[b].nsmallest(k).max()])
   fa=set(profiles.loc[(profiles.model==a)&profiles.flag_998,'airport'])&set(ids);fb=set(profiles.loc[(profiles.model==b)&profiles.flag_998,'airport'])&set(ids)
   ranks.append(dict(subset=label,model_a=a,model_b=b,n=len(z),spearman=spearmanr(z[a],z[b]).statistic,kendall=kendalltau(z[a],z[b]).statistic,top_decile_jaccard=jacc(topa,topb),bottom_decile_jaccard=jacc(bota,botb),bottom_a_count=len(bota),bottom_b_count=len(botb),flag_jaccard=jacc(fa,fb)))
 pd.DataFrame(ranks).to_csv(O/'reference_rank_concordance.csv',index=False)
 local=read(args.reference);local=local[local.dataset=='target']
 valid_predictions(local)
 assert set(local.event_id)==set(cohort.loc[cohort.target,'event_id'])
 expected_labels=cohort.set_index('event_id').loc[local.event_id,'damage_binary'].to_numpy()
 assert np.array_equal(expected_labels,local.damage_binary.to_numpy())
 pooled_n=len(local);pooled_O=int(local.damage_binary.sum());pooled_E=float(local.p_calibrated.sum())
 draw=read(args.draws);point=read(args.intervals)
 draw['n']=-100*draw.observed_minus_expected/draw.bias_pp;draw['E']=draw.n*draw.predicted;draw['O']=draw.E+draw.observed_minus_expected
 assert np.max(abs(draw.n-draw.n.round()))<1e-7 and np.max(abs(draw.O-draw.O.round()))<1e-7
 pool=draw.groupby(['replicate','sample'])[['O','E']].sum();pool['OE']=pool.O/pool.E
 mat=draw.pivot(index=['replicate','sample'],columns='airport',values='oe')[A];assert len(mat)==9960 and mat.notna().all().all()
 theta=np.log(point[point.measure=='oe'].set_index('airport').loc[A,'estimate'].to_numpy());x=np.log(mat.to_numpy());se=x.std(axis=0,ddof=1)
 target=[]
 for centering,center in [('fitted_estimate',theta),('bootstrap_mean',x.mean(axis=0))]:
  delta=x-center;t=delta/se;critical=np.quantile(abs(t).max(axis=1),.95)
  p=(1+(abs(t)>=abs(theta/se)).sum(axis=0))/(len(t)+1);order=np.argsort(p);holm=np.empty(8);holm[order]=np.minimum(1,np.maximum.accumulate(p[order]*(8-np.arange(8))))
  for i,a in enumerate(A):
   rel=mat[a]/pool.OE;lo,hi=np.quantile(rel,[.025,.975]);est=np.exp(theta[i])/(pooled_O/pooled_E)
   target.append(dict(airport=a,centering=centering,OE=np.exp(theta[i]),relative_to_pooled=est,relative_low=lo,relative_high=hi,max_stat_low=np.exp(theta[i]-critical*se[i]),max_stat_high=np.exp(theta[i]+critical*se[i]),bootstrap_p=p[i],holm_p=holm[i],critical=critical,log_ratio_sd=se[i]))
 pd.DataFrame(target).to_csv(O/'target_simultaneous_relative.csv',index=False)
 pd.DataFrame([{'n':pooled_n,'O':pooled_O,'E':pooled_E,'OE':pooled_O/pooled_E,'low':pool.OE.quantile(.025),'high':pool.OE.quantile(.975)}]).to_csv(O/'pooled_targets.csv',index=False)
 
 joined=local.merge(cohort[['event_id','DAMAGE_LEVEL','SOURCE','PERSON']],on='event_id',validate='one_to_one')
 coding=[];strata=[]
 for a,g in joined.groupby('airport_id'):
  coding.append(dict(airport=a,n=len(g),damage=int(g.damage_binary.sum()),undetermined=int(g.DAMAGE_LEVEL.eq('M?').sum()),documented_damage=int((g.damage_binary.eq(1)&g.DAMAGE_LEVEL.ne('M?')).sum())))
  for source,h in g.groupby(g.SOURCE.fillna('Missing').astype(str)):
   e=h.p_calibrated.sum();strata.append(dict(airport=a,source=source,n=len(h),damage=int(h.damage_binary.sum()),undetermined=int(h.DAMAGE_LEVEL.eq('M?').sum()),expected=e,OE=h.damage_binary.sum()/e))
 pd.DataFrame(coding).to_csv(O/'target_damage_composition.csv',index=False);pd.DataFrame(strata).to_csv(O/'target_source_strata.csv',index=False)
 overlay=[]
 for a,g in local.groupby('airport_id'):
  p=g.p_calibrated.to_numpy();e=p.sum();obs=int(g.damage_binary.sum());cdf=np.cumsum(pb(p));lo=np.searchsorted(cdf,.001);hi=np.searchsorted(cdf,.999)
  overlay.append(dict(airport=a,n=len(g),O=obs,E=e,OE=obs/e,low_998=lo/e,high_998=hi/e,flag_998=bool(obs<lo or obs>hi),prediction_design='temporal model, held-out airport, full period'))
 pd.DataFrame(overlay).to_csv(O/'target_funnel_overlay.csv',index=False)
 (O/'input_manifest.json').write_text(json.dumps(sources,indent=2),encoding='utf-8')
 print(pd.DataFrame(disp).query("model=='glmm_EBL'").to_string(index=False))
 print(pd.DataFrame(target).query("airport=='KJFK'").to_string(index=False))
 print(pd.DataFrame(ranks).groupby('subset').spearman.agg(['min','max']).to_string())
except Exception:
 (out/'logs/profiling_failure.json').write_text(json.dumps({'traceback':traceback.format_exc()},indent=2),encoding='utf-8')
 raise
