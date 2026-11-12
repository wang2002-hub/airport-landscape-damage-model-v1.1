"""Feature encoding, hierarchical models and probability calibration."""
import os
for _key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[_key]='2'
import numpy as np,pandas as pd
from scipy.special import expit,logit,logsumexp
from scipy.optimize import minimize
from numpy.polynomial.hermite import hermgauss
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from threadpoolctl import threadpool_limits
from model_config import ENV,SEED
threadpool_limits(2)

def feature_frame(d,scale=None,geo=True,bird=0,mode='level'):
    num=pd.DataFrame(index=d.index);num['year']=(d.year.to_numpy(float)-2020)/5;num['month_sin']=d.month_sin.to_numpy(float);num['month_cos']=d.month_cos.to_numpy(float)
    if scale:
        if mode=='ilr':
            from scipy.linalg import helmert
            parts=['water','developed','forest','shrub','grassland','pasture','cropland','wetland','other']
            comp=d[[x+'_fraction__'+scale for x in parts]].to_numpy(float)
            comp=np.maximum(comp,1e-6);comp/=comp.sum(axis=1,keepdims=True)
            ilr=np.log(comp)@helmert(9).T
            for j in range(8):num['ilr_'+str(j+1)]=ilr[:,j]
            num['impervious_mean_pct']=d['impervious_mean_pct__'+scale].to_numpy(float)/100
        elif mode=='cre':
            for name in ENV:
                num['between_'+name]=d['between_'+name].to_numpy(float);num['within_'+name]=d['within_'+name].to_numpy(float)
        elif mode=='within':
            for name in ENV:num['within_'+name]=d['within_'+name].to_numpy(float)
        elif mode=='changes':
            for name in ENV:
                col='impervious_mean_delta_common_pp' if name=='impervious_mean_pct' else name.replace('_fraction','_delta_common_pp')
                num['change_'+name]=d[col+'__'+scale].to_numpy(float)/100
        elif scale=='rings':
            for zone in ['r00_03','r03_08','r08_13']:
                num['water_wetland_'+zone]=d['water_fraction__'+zone].to_numpy(float)+d['wetland_fraction__'+zone].to_numpy(float)
                num['cropland_'+zone]=d['cropland_fraction__'+zone].to_numpy(float)
        elif mode=='merged':
            num['water_wetland_fraction']=(d['water_fraction__'+scale]+d['wetland_fraction__'+scale]).to_numpy(float)
            num['open_vegetation_fraction']=(d['grassland_fraction__'+scale]+d['pasture_fraction__'+scale]).to_numpy(float)
            for name in ['cropland_fraction','impervious_mean_pct']:num[name]=d[name+'__'+scale].to_numpy(float)/(100 if name.endswith('_pct') else 1)
        else:
            for name in ENV:num[name]=d[name+'__'+scale].to_numpy(float)/(100 if name.endswith('_pct') else 1)
            if mode=='canopy':num['canopy_mean_pct']=d['canopy_mean_pct__'+scale].to_numpy(float)/100
            if mode=='level_and_change':
                for name in ENV:
                    col='impervious_mean_delta_common_pp' if name=='impervious_mean_pct' else name.replace('_fraction','_delta_common_pp')
                    num['change_'+name]=d[col+'__'+scale].to_numpy(float)/100
    cats=['aircraft_mass_class','phase']+(['faa_region'] if geo else [])+(['bird_size_reported','number_struck_category'] if bird>=1 else [])+(['species_group'] if bird>=2 else [])
    return num,d[cats].astype('string').fillna('Unknown')

class Encoder:
    def __init__(self,scale=None,geo=True,bird=0,mode='level',screen=True):self.scale=scale;self.geo=geo;self.bird=bird;self.mode=mode;self.screen=screen
    def fit(self,d):
        num,cat=feature_frame(d,self.scale,self.geo,self.bird,self.mode)
        self.correlation_audit=[];self.dropped=[];candidates=list(num.columns[3:]);u=num.loc[d.drop_duplicates(['airport_id','year']).index,candidates]
        if candidates:
            pear=u.corr();spear=u.corr(method='spearman');kept=[]
            for c in candidates:
                reason=None
                if u[c].nunique(dropna=True)<2:reason='constant_in_training_airport_years'
                for k in kept:
                    rp=float(pear.loc[k,c]);rs=float(spear.loc[k,c]);flag=abs(rp)>.8 or abs(rs)>.8
                    self.correlation_audit.append({'feature_a':k,'feature_b':c,'pearson_r':rp,'spearman_r':rs,'n_training_airport_years':len(u),'flag_abs_gt_0_8':flag})
                    if flag and reason is None:reason='correlated_with_'+k
                if self.screen and reason:self.dropped.append({'feature':c,'reason':reason})
                else:kept.append(c)
            if self.screen:num=num.drop(columns=[r['feature'] for r in self.dropped])
        self.numeric=list(num);self.medians=num.median().fillna(0);clean=num.fillna(self.medians);self.means=clean.mean();self.sds=clean.std(ddof=0).where(lambda x:x>1e-10,1);self.missing=[c for c in num if num[c].isna().any()];self.categories={};self.references={};self.observed_raw={};self.retained_raw={}
        self.names=['Intercept']+self.numeric+[c+'_missing' for c in self.missing]
        for col in cat:
            counts=cat[col].value_counts();keep=set(counts[counts>=30].index.astype(str));self.observed_raw[col]=counts.index.astype(str).tolist();self.retained_raw[col]=sorted(keep);mapped=cat[col].where(cat[col].isin(keep),'Other');mc=mapped.value_counts();ref=str(mc.index[0]);mapped=mapped.where(~mapped.eq('Other') | (mc.get('Other',0)>=30),ref);levels=mapped.value_counts().index.astype(str).tolist();self.categories[col]=levels;self.references[col]=ref
            self.names += [col+'='+level for level in levels[1:]]
        self.training_events=len(d);self.training_airports=int(d.airport_id.nunique());self.training_year_min=int(d.year.min());self.training_year_max=int(d.year.max());return self
    def transform(self,d):
        num,cat=feature_frame(d,self.scale,self.geo,self.bird,self.mode);num=num[self.numeric];arr=[np.ones((len(d),1)),((num.fillna(self.medians)-self.means)/self.sds).to_numpy(float)]
        if self.missing:arr.append(num[self.missing].isna().to_numpy(float))
        for col,levels in self.categories.items():
            observed=getattr(self,'observed_raw',{}).get(col,levels);keep=getattr(self,'retained_raw',{}).get(col,levels);mapped=cat[col].where(cat[col].isin(keep),'Other');mapped=mapped.where(cat[col].isin(observed),'__UNSEEN__');mapped=mapped.where(~mapped.eq('Other') | ('Other' in levels),self.references[col])
            arr.extend([(mapped==level).to_numpy(float)[:,None] for level in levels[1:]])
        X=np.ascontiguousarray(np.hstack(arr));assert np.isfinite(X).all();return X
    def metadata(self):return {'training_correlation_audit':self.correlation_audit,'screening_enabled':self.screen,'dropped_features':self.dropped,'scale':self.scale,'geography':self.geo,'bird_adjustment':self.bird,'mode':self.mode,'numeric':self.numeric,'medians':self.medians.to_dict(),'means':self.means.to_dict(),'standard_deviations':self.sds.to_dict(),'missing_indicators':self.missing,'categories':self.categories,'reference_categories':self.references,'feature_names':self.names,'training_events':self.training_events,'training_airports':self.training_airports,'training_year_min':self.training_year_min,'training_year_max':self.training_year_max,'observed_raw_categories':getattr(self,'observed_raw',{}),'retained_raw_categories':getattr(self,'retained_raw',{}),'unseen_category_rule':'Truly unseen values use the reference encoding; observed rare values use Other only when pooled training count is at least 30, otherwise reference; fold QC reports unseen values'}
    def qc(self,d):
        num,cat=feature_frame(d,self.scale,self.geo,self.bird,self.mode)
        return {'n_rows':len(d),'numeric_missing':int(num.isna().sum().sum()),'unseen_category_cells':int(sum((~cat[c].isin(getattr(self,'observed_raw',{}).get(c,v))).sum() for c,v in self.categories.items())),'not_retained_category_cells':int(sum((~cat[c].isin(v)).sum() for c,v in self.categories.items())),'finite_matrix':bool(np.isfinite(self.transform(d)).all())}

class RandomInterceptLogit:
    def __init__(self,ridge=1e-4,maxiter=250):self.ridge=ridge;self.maxiter=maxiter
    def setup(self,X,y,groups):
        self.X=np.asarray(X,float);self.y=np.asarray(y,float);self.groups,self.g=np.unique(np.asarray(groups,dtype=str),return_inverse=True);self.G=len(self.groups);self.P=X.shape[1];self.penalty=np.ones(self.P);self.penalty[0]=0
        return self
    def mode(self,beta,rho):
        eta=self.X@beta;ivar=np.exp(-2*rho);b=np.zeros(self.G)
        for it in range(60):
            prob=expit(eta+b[self.g]);v=prob*(1-prob);u=np.bincount(self.g,weights=self.y-prob,minlength=self.G)-ivar*b;H=np.bincount(self.g,weights=v,minlength=self.G)+ivar;step=np.clip(u/H,-3,3);b+=step
            if np.max(np.abs(step))<1e-9:break
        prob=expit(eta+b[self.g]);v=prob*(1-prob);H=np.bincount(self.g,weights=v,minlength=self.G)+ivar
        return eta,b,prob,v,H,ivar
    def objective(self,theta,weights=None,return_scores=False):
        beta=theta[:-1];rho=theta[-1];eta,b,p,v,H,ivar=self.mode(beta,rho);w=v*(1-2*p);sw=np.bincount(self.g,weights=w,minlength=self.G)
        ll=np.bincount(self.g,weights=self.y*(eta+b[self.g])-np.logaddexp(0,eta+b[self.g]),minlength=self.G)-.5*ivar*b*b-rho-.5*np.log(H)
        score_event=self.y-p-.5*w/H[self.g]+.5*v*sw[self.g]/H[self.g]**2
        score_rho=ivar*b*b-1+ivar/H-ivar*sw*b/H**2
        weights=np.ones(self.G) if weights is None else np.asarray(weights,float)
        gradbeta=self.X.T@(score_event*weights[self.g]);grad=np.r_[gradbeta,weights@score_rho]
        value=weights@ll-.5*self.ridge*np.sum(self.penalty*beta**2);grad[:-1]-=self.ridge*self.penalty*beta
        if return_scores:
            S=np.zeros((self.G,self.P+1));np.add.at(S[:,:-1],self.g,self.X*score_event[:,None]);S[:,-1]=score_rho;return ll,S
        return -value,-grad
    def fit(self,X,y,groups,weights=None,start=None):
        self.setup(X,y,groups)
        if start is None:
            start=np.zeros(self.P+1);start[0]=logit(np.clip(np.mean(y),.001,.999));start[-1]=-.3
        res=minimize(self.objective,start,args=(weights,),jac=True,method='L-BFGS-B',bounds=[(None,None)]*self.P+[(-4,2)],options={'maxiter':self.maxiter,'ftol':1e-11,'gtol':1e-5,'maxls':40,'maxcor':20})
        if not res.success or np.max(np.abs(res.jac))>.02:
            res=minimize(self.objective,res.x,args=(weights,),jac=True,method='L-BFGS-B',bounds=[(None,None)]*self.P+[(-4,2)],options={'maxiter':self.maxiter,'ftol':1e-13,'gtol':1e-5,'maxls':40,'maxcor':30})
        self.theta=res.x;self.coef=res.x[:-1];self.sigma=float(np.exp(res.x[-1]));self.optim={'success':bool(res.success),'message':str(res.message),'iterations':int(res.nit),'max_abs_gradient':float(np.max(np.abs(res.jac))),'negative_loglik_penalized':float(res.fun),'sigma':self.sigma,'rho_boundary':bool(res.x[-1]<-3.99 or res.x[-1]>1.99)};self.b_mode=self.mode(self.coef,self.theta[-1])[1]
        return self
    def predict(self,X,order=30):
        z,w=hermgauss(order);return np.clip(expit((np.asarray(X)@self.coef)[:,None]+np.sqrt(2)*self.sigma*z)@(w/np.sqrt(np.pi)),1e-8,1-1e-8)
    def covariance(self):
        h=2e-4;theta=self.theta;p=len(theta);H=np.empty((p,p))
        for j in range(p):
            d=np.zeros(p);d[j]=h;H[:,j]=(self.objective(theta+d)[1]-self.objective(theta-d)[1])/(2*h)
        H=(H+H.T)/2;inv=np.linalg.pinv(H,rcond=1e-10);_,S=self.objective(theta,return_scores=True);S-=S.mean(0);cov=inv@(S.T@S)@inv*self.G/max(1,self.G-1)
        return cov,{'hessian_min_eigenvalue':float(np.linalg.eigvalsh(H).min()),'hessian_condition':float(np.linalg.cond(H)),'cluster_count':self.G}
    def adaptive_loglik(self,theta,order=15):
        eta,b,p,v,H,ivar=self.mode(theta[:-1],theta[-1]);z,w=hermgauss(order);nodes=b[:,None]+np.sqrt(2/H[:,None])*z;logs=np.empty((self.G,order))
        for j in range(order):
            t=eta+nodes[self.g,j];logs[:,j]=np.bincount(self.g,weights=self.y*t-np.logaddexp(0,t),minlength=self.G)-.5*ivar*nodes[:,j]**2-theta[-1]-.5*np.log(2*np.pi)+.5*np.log(2/H)+np.log(w[j])+z[j]**2
        return float(logsumexp(logs,axis=1).sum())
    def compact(self):
        for a in ['X','y','g','groups','G','P','penalty']:self.__dict__.pop(a,None)
        return self

class FixedInterceptLogit(RandomInterceptLogit):
    def objective(self,beta,weights=None,return_scores=False):
        eta=self.X@beta;b=np.zeros(self.G)
        for it in range(80):
            p=expit(eta+b[self.g]);v=p*(1-p);H=np.bincount(self.g,weights=v,minlength=self.G);u=np.bincount(self.g,weights=self.y-p,minlength=self.G);step=np.clip(u/np.maximum(H,1e-9),-3,3);b+=step
            if abs(step).max()<1e-9:break
        t=eta+b[self.g];p=expit(t);ll=np.bincount(self.g,weights=self.y*t-np.logaddexp(0,t),minlength=self.G);s=self.y-p;weights=np.ones(self.G) if weights is None else weights
        grad=self.X.T@(s*weights[self.g])-self.ridge*self.penalty*beta
        if return_scores:
            S=np.zeros((self.G,self.P));np.add.at(S,self.g,self.X*s[:,None]);return ll,S
        return -weights@ll+.5*self.ridge*np.sum(self.penalty*beta**2),-grad
    def fit(self,X,y,groups,weights=None,start=None):
        self.setup(X,y,groups);self.penalty=np.ones(self.P);start=np.zeros(self.P) if start is None else start
        res=minimize(self.objective,start,args=(weights,),jac=True,method='L-BFGS-B',options={'maxiter':300,'ftol':1e-12,'gtol':1e-5,'maxcor':30});self.theta=self.coef=res.x;self.optim={'success':bool(res.success),'iterations':int(res.nit),'max_abs_gradient':float(abs(res.jac).max()),'message':str(res.message)};return self

def fit_bundle(d,kind='glmm',scale=None,geo=True,bird=0,mode='level',params=None,screen=True):
    enc=Encoder(scale,geo,bird,mode,screen=screen).fit(d);X=enc.transform(d);y=d.damage_binary.to_numpy(float)
    if kind=='glmm':model=RandomInterceptLogit().fit(X,y,d.airport_id.to_numpy())
    elif kind=='logistic':model=LogisticRegression(C=(params or {}).get('C',1),max_iter=600,solver='lbfgs',fit_intercept=False,tol=1e-7).fit(X,y)
    elif kind=='hgb':model=HistGradientBoostingClassifier(**params,early_stopping=False,random_state=SEED).fit(X[:,1:],y)
    else:raise ValueError(kind)
    return {'encoder':enc,'model':model,'kind':kind,'params':params or {},'calibrator':None}
def predict_bundle(bundle,d,calibrated=False):
    X=bundle['encoder'].transform(d);m=bundle['model'];p=m.predict(X) if bundle['kind']=='glmm' else m.predict_proba(X[:,1:] if bundle['kind']=='hgb' else X)[:,1]
    if calibrated and bundle.get('calibrator') is not None:p=expit(bundle['calibrator'][0]+bundle['calibrator'][1]*logit(np.clip(p,1e-8,1-1e-8)))
    return np.clip(p,1e-8,1-1e-8)
def fit_calibrator(y,p):
    z=logit(np.clip(p,1e-8,1-1e-8));y=np.asarray(y,float)
    def obj(t):
        eta=t[0]+t[1]*z;q=expit(eta);return np.sum(np.logaddexp(0,eta)-y*eta)+.5e-4*np.sum(t*t),np.array([(q-y).sum(),(q-y)@z])+1e-4*t
    r=minimize(obj,[0,1],jac=True,method='L-BFGS-B',bounds=[(-10,10),(.05,5)],options={'ftol':1e-12,'gtol':1e-7});return r.x,{'success':bool(r.success),'intercept':float(r.x[0]),'slope':float(r.x[1]),'n':len(y),'damages':int(y.sum())}
