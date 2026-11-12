import numpy as np,pandas as pd
from model_core import Encoder
class ExtendedEncoder:
 def __init__(self,scale,bird,extra):self.base=Encoder(scale,False,bird);self.extra=extra;self.scale=scale
 def frame(self,d):
  num=pd.DataFrame(index=d.index);cat=pd.DataFrame(index=d.index)
  for c in self.extra:
   if c=='canopy':num['static_2015_canopy']=d['canopy_mean_pct__'+self.scale]/100
   elif c in ['HEIGHT','DISTANCE','SPEED']:
    z=pd.to_numeric(d[c],errors='coerce').astype(float)
    if c=='SPEED':z=z.where(z.between(0,400))
    num['log1p_'+c]=np.log1p(z)
   else:cat[c]=d[c].astype('string').fillna('Unknown')
  return num,cat
 def fit(self,d):
  self.base.fit(d);num,cat=self.frame(d);self.med=num.median().fillna(0);clean=num.fillna(self.med);self.mean=clean.mean();self.sd=clean.std(ddof=0).where(lambda x:x>1e-10,1);self.missing=[c for c in num if num[c].isna().any()];self.levels={};self.keep={};self.observed={};self.names=list(self.base.names)+list(num)+[c+'_missing' for c in self.missing]
  for c in cat:
   vc=cat[c].value_counts();self.observed[c]=list(vc.index);self.keep[c]=list(vc[vc>=30].index);v=cat[c].where(cat[c].isin(self.keep[c]),'Other');counts=v.value_counts();v=v.where(~v.eq('Other')|(counts.get('Other',0)>=30),counts.index[0]);self.levels[c]=list(v.value_counts().index);self.names.extend(c+'='+str(k) for k in self.levels[c][1:])
  return self
 def transform(self,d):
  num,cat=self.frame(d);arr=[self.base.transform(d),((num.fillna(self.med)-self.mean)/self.sd).to_numpy(float)]
  if self.missing:arr.append(num[self.missing].isna().to_numpy(float))
  for c,levels in self.levels.items():
   v=cat[c].where(cat[c].isin(self.keep[c]),'Other');v=v.where(cat[c].isin(self.observed[c]),'__UNSEEN__');v=v.where(~v.eq('Other')|('Other' in levels),levels[0]);arr.extend((v==x).to_numpy(float)[:,None] for x in levels[1:])
  x=np.ascontiguousarray(np.hstack(arr));assert np.isfinite(x).all();return x
 def metadata(self):return {'base':self.base.metadata(),'extra':self.extra,'extra_medians':self.med.to_dict(),'extra_means':self.mean.to_dict(),'extra_sds':self.sd.to_dict(),'extra_missing_indicators':self.missing,'extra_levels':self.levels,'feature_names':self.names,'note':'Extra event variables and single static canopy addition exempt from environmental correlation screening; the base environmental subset is unchanged within a pair.'}
