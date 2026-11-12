"""Verify archived landscape contrasts without fitting or resampling models."""
from pathlib import Path
import sys,json,hashlib,traceback,time
from datetime import datetime,timezone
import numpy as np
import pandas as pd
from artifact_inputs import Inputs
I=Inputs(__doc__);OUT=I.output/'results';inputs=[];checks=[];start=time.perf_counter()
A=['KDEN','KJFK','KMIA','KMSP','KBOS','KSFO','KSAT','KSTL']

def read(p):
    p=Path(p);inputs.append(dict(filename=p.name,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    if p.suffix=='.parquet':return pd.read_parquet(p)
    if p.suffix=='.json':return json.loads(p.read_text(encoding='utf-8'))
    return pd.read_csv(p)

def pair(a,b):
    keys=['event_id','airport_id','year']
    x=a.merge(b[keys+['damage_binary','p_calibrated']],on=keys,validate='one_to_one',suffixes=('_base','_aug'))
    assert len(x)==len(a)==len(b) and x.damage_binary_base.eq(x.damage_binary_aug).all()
    y=x.damage_binary_base.to_numpy();p=x.p_calibrated_base.to_numpy();q=x.p_calibrated_aug.to_numpy()
    assert ((p>0)&(p<1)&(q>0)&(q<1)).all()
    loss=lambda z:np.mean(-y*np.log(z)-(1-y)*np.log1p(-z))
    base=float(np.mean((p-y)**2));aug=float(np.mean((q-y)**2))
    return dict(n=len(x),damage=int(y.sum()),airports=x.airport_id.nunique(),base_brier=base,aug_brier=aug,
                delta_brier=float(np.mean((q-y)**2-(p-y)**2)),base_logloss=float(loss(p)),aug_logloss=float(loss(q)),
                delta_logloss=float(loss(q)-loss(p)),relative_brier_change_pct=100*(aug-base)/base)

def match(value,expected,label,tol=1e-12):
    error=abs(float(value)-float(expected));assert error<tol,(label,value,expected)
    checks.append(dict(check=label,absolute_error=error))

def run():
    saved=read(I.path('paired_gains'));performance=read(I.path('performance'))
    cohort=read(I.path('cohort'));national=[];local=[]
    for scheme in ['temporal','spatial']:
        for family in ['glmm','hgb']:
            models={}
            for block in ['E','EL','EB','EBL']:
                models[block]=pd.concat([read(I.path('national_results',f'{scheme}_{fold}_{family}_{block}_predictions.parquet'))
                                          for fold in ([0] if scheme=='temporal' else range(1,6))],ignore_index=True)
            for left,right in [('E','EL'),('EB','EBL')]:
                a=models[left];b=models[right]
                na=a[a.dataset=='national'];nb=b[b.dataset=='national']
                expected=cohort[~cohort.target&(cohort.year.ge(2024) if scheme=='temporal' else True)]
                assert set(na.event_id)==set(nb.event_id)==set(expected.event_id)
                m=pair(na,nb)
                row=saved[(saved.dataset=='national')&(saved.scheme==scheme)&(saved.family==family)&(saved.contrast==left+'_to_'+right)].iloc[0]
                for metric in ['delta_brier','delta_logloss']:match(m[metric],row[metric],f'{scheme}_{family}_{left}_{metric}')
                for block,prefix in [(left,'base'),(right,'aug')]:
                    r=performance[(performance.dataset=='national')&(performance.scheme==scheme)&(performance.family==family)&(performance.model==block)].iloc[0]
                    match(m[prefix+'_brier'],r.brier,f'{scheme}_{family}_{block}_absolute_brier')
                national.append(dict(scheme=scheme,family=family,contrast=left+'_to_'+right,**m,
                                     delta_brier_lo=row.delta_brier_lo,delta_brier_hi=row.delta_brier_hi,
                                     delta_logloss_lo=row.delta_logloss_lo,delta_logloss_hi=row.delta_logloss_hi,
                                     interval_scope='2000 airport resamples; frozen predictions; no model refitting'))
                if scheme=='temporal' and left=='EB':
                    for airport in A:
                        for period in ['all','2024_2025']:
                            aa=a[(a.airport_id==airport)&(a.dataset=='target')];bb=b[(b.airport_id==airport)&(b.dataset=='target')]
                            if period!='all':aa=aa[aa.year>=2024];bb=bb[bb.year>=2024]
                            m=pair(aa,bb)
                            row=saved[(saved.dataset=='target')&(saved.family==family)&(saved.airport==airport)&(saved.period==period)&(saved.contrast=='EB_to_EBL')].iloc[0]
                            match(m['delta_brier'],row.delta_brier,f'{airport}_{family}_{period}_brier')
                            local.append(dict(airport=airport,period=period,family=family,**m,
                                              delta_brier_lo=row.delta_brier_lo,delta_brier_hi=row.delta_brier_hi,
                                              interval_scope='2000 paired year resamples; frozen predictions; recent two-year intervals unavailable'))
    national=pd.DataFrame(national);national.to_csv(OUT/'landscape_national_verified.csv',index=False)
    pd.DataFrame(local).to_csv(OUT/'landscape_local_verified.csv',index=False)
    primary=national[national.contrast=='EB_to_EBL'].copy();primary.to_csv(OUT/'landscape_primary_panel.csv',index=False)

    values=read(I.path('pipeline_values'));summary=read(I.path('pipeline_summary'))
    successful=[];failures=[];selection=[]
    for rep in range(200):
        rec=read(I.path('pipeline_records',f'bootstrap_{rep:03d}.json'))
        if rec['success']:
            successful.append(rep);selection.append(dict(replicate=rep,scale=rec['selected']['EBL']))
            for row in rec['rows']:
                old=values[(values.replicate==rep)&(values.dataset==row['dataset'])&(values.airport==row['airport'])].iloc[0]
                match(row['delta_brier'],old.delta_brier,f'archived_draw_{rep}_{row["dataset"]}_{row["airport"]}')
        else:failures.append(dict(replicate=rep,error=rec.get('error','')))
    assert len(successful)==198 and len(failures)==2 and set(values.replicate)==set(successful)
    for row in summary.itertuples():
        g=values[(values.dataset==row.dataset)&(values.airport==row.airport)]
        assert len(g)==198
        for metric in ['delta_brier','delta_logloss']:
            for q,label in [(.025,'lo'),(.5,'median'),(.975,'hi')]:
                match(g[metric].quantile(q),getattr(row,metric+'_'+label),f'pipeline_{row.dataset}_{row.airport}_{metric}_{label}')
    summary.to_csv(OUT/'landscape_pipeline_intervals_verified.csv',index=False)
    pd.DataFrame(selection).to_csv(OUT/'landscape_pipeline_selected_scales.csv',index=False)
    (OUT/'landscape_pipeline_failure_inventory.json').write_text(json.dumps(failures,indent=2),encoding='utf-8')

    # Keep the distinct four-field archive and seven-field principal sensitivity identifiable.
    previous=read(I.path('canopy_contrasts'));extra=[]
    for family in ['glmm','hgb']:
        for label,left,right in [('annual_landcover','annual_base_EBL','annual_canopy_EBL'),
                                 ('fixed2015_landcover','fixed2015_base_EBL','fixed2015_canopy_EBL')]:
            a=read(I.path(f'canopy_{family}_{left}'));b=read(I.path(f'canopy_{family}_{right}'))
            m=pair(a[a.dataset=='national'],b[b.dataset=='national'])
            old=previous[(previous.family==family)&(previous.contrast==I.label('canopy_annual' if label=='annual_landcover' else 'canopy_fixed'))].iloc[0]
            match(m['delta_brier'],old.delta_brier,f'canopy_{family}_{label}')
            extra.append(dict(analysis='static_2015_canopy',family=family,contrast=label,**m,low=old.ci_low,high=old.ci_high))
    enhanced=read(I.path('enhanced_contrasts'))
    for family in ['glmm','hgb']:
        for left,right in [('E','EL'),('EB','EBL')]:
            a=read(I.path('enhanced_results',f'enhanced_{family}_{left}_predictions.parquet'));b=read(I.path('enhanced_results',f'enhanced_{family}_{right}_predictions.parquet'))
            m=pair(a[a.dataset=='national'],b[b.dataset=='national'])
            old=enhanced[(enhanced.family==family)&(enhanced.contrast==right+' minus '+left)].iloc[0]
            match(m['delta_brier'],old.delta,f'seven_field_{family}_{left}')
            extra.append(dict(analysis='seven_field_event_extension',family=family,contrast=left+'_to_'+right,**m,low=old.low,high=old.high))
    pd.DataFrame(extra).to_csv(OUT/'landscape_auxiliary_verified.csv',index=False)
    variation=read(I.path('landscape_variation'))
    assert variation.airports.eq(1375).all() and variation.airport_years.eq(15125).all()
    variation.to_csv(OUT/'landscape_variation_inventory.csv',index=False)
    resource=read(I.path('resource_measurement'))
    canopy=read(I.path('canopy_context'))
    scope=read(I.path('bootstrap_scope'))
    (OUT/'landscape_archived_support.json').write_text(json.dumps(dict(resource=resource,bootstrap_scope=scope,
           canopy_context=canopy.to_dict('records'),interpretation='Retained source measurements and scope; no new resource measurement.'),indent=2),encoding='utf-8')
    checks_data=dict(timestamp_utc=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.perf_counter()-start,
                     new_model_fits=0,new_bootstrap_draws=0,new_observations=0,national_primary_pairs=len(primary),
                     national_primary_n=primary[['scheme','family','n','damage']].to_dict('records'),
                     matched_prediction_membership=True,successful_pipeline_fits=198,failed_pipeline_replicates=[x['replicate'] for x in failures],
                     saved_values_checked=len(checks),maximum_absolute_arithmetic_error=max(x['absolute_error'] for x in checks),inputs=inputs)
    (OUT/'landscape_evidence_checks.json').write_text(json.dumps(checks_data,indent=2),encoding='utf-8')
    print(primary[['scheme','family','n','base_brier','aug_brier','delta_brier','relative_brier_change_pct']].to_string(index=False))
    print('Verified existing pipeline failures:',[x['replicate'] for x in failures])
    print(pd.DataFrame(extra)[['analysis','family','contrast','delta_brier','low','high']].to_string(index=False))

try:run()
except Exception:
    (OUT/'landscape_consolidation_failure.json').write_text(json.dumps({'traceback':traceback.format_exc(),'inputs':inputs},indent=2),encoding='utf-8');raise
