"""Audit conditional airport count limits and multiplicative-width sensitivities."""
from pathlib import Path
import sys, json, hashlib, itertools, time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from scipy.signal import fftconvolve

import argparse,traceback
from profile_inputs import configure,valid_predictions,validate_events
args,out=configure(argparse.ArgumentParser(description=__doc__),['profiles'])
OUT=out/'results' 
TOL = 1e-9
start = time.perf_counter()
inputs = []

def read(path):
    path = Path(path)
    inputs.append({'filename': path.name,
                   'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    return pd.read_parquet(path) if path.suffix == '.parquet' else pd.read_csv(path)

def pmf_recurrence(p):
    f = np.ones(1)
    for v in p:
        g = np.zeros(len(f) + 1)
        g[:-1] += f * (1-v)
        g[1:] += f * v
        f = g
    assert abs(f.sum()-1) < 1e-11
    return f

def pmf_fft(p):
    nodes = [np.array([1-v, v]) for v in p]
    while len(nodes) > 1:
        nodes = [fftconvolve(nodes[i], nodes[i+1]) if i+1<len(nodes) else nodes[i]
                 for i in range(0, len(nodes), 2)]
    return nodes[0]

def outside(o, lo, hi):
    return (o < lo-TOL) | (o > hi+TOL)

try:
 old = read(args.profiles)
 cohort = read(args.data)
 validate_events(cohort)
 targets = ['KDEN','KJFK','KMIA','KMSP','KBOS','KSFO','KSAT','KSTL']
 national_ids = set(cohort.loc[~cohort.airport_id.isin(targets), 'event_id'])
 models = {}
 for family, block in [('glmm','EB'),('glmm','EBL'),('hgb','EB'),('hgb','EBL')]:
     d = pd.concat([read(Path(args.national_dir)/f'spatial_{k}_{family}_{block}_predictions.parquet')
                    for k in range(1,6)], ignore_index=True)
     models[family+'_'+block] = d[d.dataset.eq('national')].copy()
 d = read(args.simple)
 models['ordinary_EB'] = d[d.scheme.eq('spatial') & d.dataset.eq('national')].copy()
 local = read(args.reference)
 local = local[local.dataset.eq('target')].copy()
 for frame in list(models.values())+[local]:valid_predictions(frame)
 
 # Exhaustive enumeration validates the recurrence on a small heterogeneous vector.
 p_test = np.array([.01,.14,.27,.66,.94])
 enum = np.zeros(6)
 for bits in itertools.product([0,1], repeat=5):
     bits = np.array(bits)
     enum[bits.sum()] += np.prod(np.where(bits, p_test, 1-p_test))
 assert np.max(abs(enum-pmf_recurrence(p_test))) < 1e-14
 
 checks = []
 rows = []
 for model, d in models.items():
     assert len(d)==46167 and set(d.event_id)==national_ids and not d.event_id.duplicated().any()
     c = d.merge(cohort[['event_id','damage_binary']], on='event_id', validate='one_to_one', suffixes=('','_check'))
     assert c.damage_binary.eq(c.damage_binary_check).all()
     largest = d.groupby('airport_id').size().nlargest(2).index
     prior = old[old.model.eq(model)].set_index('airport')
     for a,g in d.groupby('airport_id'):
         p = g.p_calibrated.to_numpy()
         assert np.isfinite(p).all() and ((p>=0)&(p<=1)).all()
         f = pmf_recurrence(p); cdf = np.cumsum(f); cdf[-1] = 1
         o = int(g.damage_binary.sum()); e = float(p.sum()); v=float((p*(1-p)).sum())
         r = dict(model=model,airport=a,n=len(p),O=o,E=e,OE=o/e,V=v,z=(o-e)/np.sqrt(v))
         assert o==prior.loc[a,'O'] and abs(e-prior.loc[a,'E'])<1e-10
         for alpha,label in [(.05,'95'),(.002,'998')]:
             lo=int(np.searchsorted(cdf,alpha/2));hi=int(np.searchsorted(cdf,1-alpha/2))
             tail=float(f[:lo].sum()+f[hi+1:].sum())
             assert tail<=alpha+1e-12
             assert lo==round(prior.loc[a,'low_'+label]*e)
             assert hi==round(prior.loc[a,'high_'+label]*e)
             r.update({f'lower_count_{label}':lo,f'upper_count_{label}':hi,
                       f'conditional_flag_{label}':bool(outside(o,lo,hi)),
                       f'conditional_tail_{label}':tail})
         if a in largest:
             f2=pmf_fft(p);err=float(np.max(abs(f-f2)))
             assert err<1e-10
             checks.append(dict(model=model,airport=a,n=len(p),independent_fft_max_error=err))
         rows.append(r)
     print(model, 'audited', flush=True)
 
 base=pd.DataFrame(rows)
 sens=[]; factors=[]
 for model,g in base.groupby('model'):
     for selection,h in [('all',g),('expected_ge5',g[g.E>=5]),('reports_ge100',g[g.n>=100])]:
         raw_phi=float(np.mean(h.z**2));phi=max(1,raw_phi)
         factors.append(dict(model=model,estimation_set=selection,estimation_airports=len(h),raw_phi=raw_phi,phi=phi))
         for label in ['95','998']:
             # The benchmark belongs to the widened envelope, including rare discrete endpoint cases.
             lower=np.minimum(g['lower_count_'+label].to_numpy(),g.E.to_numpy())
             upper=np.maximum(g['upper_count_'+label].to_numpy(),g.E.to_numpy())
             lo=np.maximum(0,g.E.to_numpy()+np.sqrt(phi)*(lower-g.E.to_numpy()))
             hi=np.minimum(g.n.to_numpy(),g.E.to_numpy()+np.sqrt(phi)*(upper-g.E.to_numpy()))
             assert (lo<=g['lower_count_'+label]+TOL).all() and (hi>=g['upper_count_'+label]-TOL).all()
             flagged=outside(g.O.to_numpy(),lo,hi)
             assert (~flagged | g['conditional_flag_'+label].to_numpy()).all()
             for i,(_,r) in enumerate(g.iterrows()):
                 sens.append(dict(model=model,airport=r.airport,estimation_set=selection,label=label,
                                  phi=phi,lower_count=lo[i],upper_count=hi[i],flag=bool(flagged[i])))
 base.to_csv(OUT/'national_funnel_limit_audit.csv',index=False)
 sens=pd.DataFrame(sens);sens.to_csv(OUT/'national_funnel_width_sensitivity.csv',index=False)
 factors=pd.DataFrame(factors);factors.to_csv(OUT/'funnel_dispersion_factors.csv',index=False)
 
 summary=[]
 for model,g in base.groupby('model'):
     for selection,h in [('all',g),('expected_ge5',g[g.E>=5]),('reports_ge100',g[g.n>=100])]:
         for label,alpha in [('95',.05),('998',.002)]:
             row=dict(model=model,display_set=selection,label=label,airports=len(h),reports=int(h.n.sum()),
                      observed_damage=int(h.O.sum()),zero_outcomes=int(h.O.eq(0).sum()),
                      conditional_flags=int(h['conditional_flag_'+label].sum()),
                      conditional_expected_flags=float(h['conditional_tail_'+label].sum()),
                      nominal_upper_bound=alpha*len(h))
             for est in ['all','expected_ge5','reports_ge100']:
                 z=sens[(sens.model==model)&(sens.estimation_set==est)&(sens.label==label)&sens.airport.isin(h.airport)]
                 row['width_flags_phi_'+est]=int(z.flag.sum())
             summary.append(row)
 summary=pd.DataFrame(summary);summary.to_csv(OUT/'national_funnel_summary.csv',index=False)
 
 overlay=[]
 phi=float(factors[(factors.model=='glmm_EBL')&(factors.estimation_set=='all')].phi.iloc[0])
 assert len(local)==5936 and set(local.airport_id)==set(targets)
 for a,g in local.groupby('airport_id'):
     p=g.p_calibrated.to_numpy();f=pmf_recurrence(p);cdf=np.cumsum(f);cdf[-1]=1;e=p.sum();o=int(g.damage_binary.sum())
     r=dict(airport=a,n=len(g),O=o,E=e,OE=o/e,phi_national=phi,prediction_design='frozen temporal model; full-period held-out target')
     for alpha,label in [(.05,'95'),(.002,'998')]:
         lo=int(np.searchsorted(cdf,alpha/2));hi=int(np.searchsorted(cdf,1-alpha/2))
         wl=max(0,e+np.sqrt(phi)*(min(lo,e)-e));wh=min(len(g),e+np.sqrt(phi)*(max(hi,e)-e))
         r.update({f'lower_count_{label}':lo,f'upper_count_{label}':hi,
                   f'conditional_flag_{label}':bool(outside(o,lo,hi)),
                   f'width_lower_count_{label}':wl,f'width_upper_count_{label}':wh,
                   f'width_flag_{label}':bool(outside(o,wl,wh))})
     overlay.append(r)
 overlay=pd.DataFrame(overlay);overlay.to_csv(OUT/'target_funnel_limit_audit.csv',index=False)
 
 overlap=[]
 for est in ['conditional','all','expected_ge5','reports_ge100']:
     for selection,ids in [('all',set(base.airport)),('primary_expected_ge5',set(base[(base.model=='glmm_EBL')&(base.E>=5)].airport))]:
         sets={}
         for model in models:
             if est=='conditional':
                 z=base[(base.model==model)&base.conditional_flag_998]
             else:
                 z=sens[(sens.model==model)&(sens.estimation_set==est)&(sens.label=='998')&sens.flag]
             sets[model]=set(z.airport)&ids
         for a,b in itertools.combinations(sorted(models),2):
             union=sets[a]|sets[b];intersection=sets[a]&sets[b]
             overlap.append(dict(control=est,population=selection,model_a=a,model_b=b,
                                 flags_a=len(sets[a]),flags_b=len(sets[b]),intersection=len(intersection),
                                 union=len(union),jaccard=len(intersection)/len(union) if union else np.nan))
 pd.DataFrame(overlap).to_csv(OUT/'reference_flag_overlap_sensitivity.csv',index=False)
 
 audit=dict(timestamp_utc=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.perf_counter()-start,
            models=len(models),national_airports=1375,national_reports=46167,target_airports=8,target_reports=5936,
            enumeration_check='passed',old_quantiles_and_counts='matched',tail_probability_bound='passed',
            widened_envelope_nesting='passed',new_flags_after_widening=0,count_scale_tolerance=TOL,
            independent_checks=checks,inputs=inputs,
            interpretation='Conditional probability limits and exploratory multiplicative widths; neither includes shared model estimation uncertainty or proves airport safety differences.')
 (OUT/'funnel_audit_checks.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
 print(summary[(summary.model=='glmm_EBL')&(summary.label=='998')].to_string(index=False))
 print(overlay[['airport','OE','conditional_flag_998','width_flag_998']].to_string(index=False))
except Exception:
 (out/'logs/count_limit_failure.json').write_text(json.dumps({'traceback':traceback.format_exc()},indent=2),encoding='utf-8')
 raise
