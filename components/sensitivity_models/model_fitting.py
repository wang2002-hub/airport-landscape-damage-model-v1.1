"""Shared convergence-checked reference fit."""
import time
from model_core import *

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
