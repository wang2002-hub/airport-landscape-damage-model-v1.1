import numpy as np,pandas as pd
ENV=['water_fraction', 'wetland_fraction', 'cropland_fraction', 'grassland_fraction', 'pasture_fraction', 'impervious_mean_pct']

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
