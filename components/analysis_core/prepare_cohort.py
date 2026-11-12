"""Prepare the eligible report cohort using explicit source and lookup files."""
from pathlib import Path
import argparse
import json
import traceback
import pandas as pd
import numpy as np
from run_support import prepare_output, validate_events

parser = argparse.ArgumentParser(description=__doc__)
for flag in ['raw', 'taxa', 'airports', 'environment', 'folds', 'config', 'output']:
    parser.add_argument('--' + flag, required=True)
args = parser.parse_args()
inputs = {key: getattr(args, key) for key in ['raw','taxa','airports','environment','folds','config']}
W = prepare_output(args.output, inputs, ['processed','results','logs'])
P = json.loads(Path(args.config).read_text(encoding='utf-8'))
targets = P['target_airports']
try:
    d=pd.read_parquet(Path(args.raw));flow={'raw_all_years':len(d)}
    for col in d:
     if col not in ['source_row','record_completeness']:d[col]=d[col].astype('string[python]').str.strip().replace('',pd.NA)
    d['year']=pd.to_numeric(d.INCIDENT_YEAR,errors='coerce');d=d[d.year.between(2015,2025)].copy();flow['period_rows']=len(d)
    d['event_id']=d.INDEX_NR.str.replace(r'\.0$','',regex=True);d['updated']=pd.to_datetime(d.LUPDATE,errors='coerce')
    d[d.event_id.duplicated(False)].to_csv(W/'results/duplicate_records.csv',index=False)
    d=d.sort_values(['updated','record_completeness','source_row'],na_position='first').drop_duplicates('event_id',keep='last').copy();flow['unique_period']=len(d)
    assert not d.event_id.isna().any()
    d['airport_id']=d.AIRPORT_ID.str.upper()
    # Use the supplied species taxonomy and airport eligibility lookups.
    tax=pd.read_csv(Path(args.taxa));assert not tax.SPECIES.duplicated().any()
    d=d.merge(tax,on='SPECIES',how='left',validate='many_to_one');assert d.taxon.notna().all(),d.loc[d.taxon.isna(),'SPECIES'].unique()
    ap=pd.read_csv(Path(args.airports));assert not ap.airport_id.duplicated().any()
    d=d.merge(ap,on='airport_id',how='left',validate='many_to_one')
    h=pd.to_numeric(d.HEIGHT,errors='coerce');dist=pd.to_numeric(d.DISTANCE,errors='coerce');phase=d.PHASE_OF_FLIGHT
    valid=(h.isna()|h.between(0,3000))&(dist.isna()|dist.between(0,5))&~(d.HEIGHT.notna()&h.isna())&~(d.DISTANCE.notna()&dist.isna())
    d['bird']=d.taxon.eq('bird');d['carcass']=d.PERSON.str.casefold().eq('carcass found').fillna(False)
    d['near']=d.bird&d.airport_scope_ok.eq(True)&phase.isin(['Take-off Run','Landing Roll','Approach','Climb'])&valid&(phase.isin(['Take-off Run','Landing Roll'])|h.notna()|dist.notna())&~d.carcass
    d['damage_binary']=d.DAMAGE_LEVEL.map({'N':0,'M':1,'M?':1,'S':1,'D':1})
    parts=pd.DataFrame({col:pd.to_numeric(d[col],errors='coerce').eq(1)|d[col].str.upper().isin(['Y','YES','TRUE']) for col in d if col.startswith('DAM_')}).any(axis=1)
    ind=pd.to_numeric(d.INDICATED_DAMAGE,errors='coerce')
    d['conflict']=((d.damage_binary.eq(0)&(parts|ind.eq(1)))|(d.damage_binary.eq(1)&ind.eq(0))).fillna(False)
    d['eligible_pre_env']=d.near&d.damage_binary.notna()&~d.conflict
    ay=d.groupby(['airport_id','year']).agg(near=('near','sum'),known=('eligible_pre_env','sum')).reset_index();ay['label_completeness']=ay.known/ay.near.replace(0,np.nan)
    d=d.merge(ay[['airport_id','year','label_completeness']],on=['airport_id','year'],validate='many_to_one')
    e=pd.read_parquet(Path(args.environment));assert not e.duplicated(['airport_id','year']).any()
    zones=['b03','b08','b13','r00_03','r03_08','r08_13'];audit=[]
    for z in zones:
     cols=[f'{x}_fraction__{z}' for x in ['water','developed','forest','shrub','grassland','pasture','cropland','wetland','other']]
     v=e[cols];ok=v.notna().all(axis=1);err=(v.sum(axis=1)-1).abs();audit.append({'zone':z,'complete_rows':int(ok.sum()),'max_closure_error':float(err[ok].max()),'fraction_min':float(v.min().min()),'fraction_max':float(v.max().max())})
     assert err[ok].max()<1e-6
     assert v.min().min()>=0 and v.max().max()<=1
     assert e[f'impervious_mean_pct__{z}'].dropna().between(0,100).all()
    (W/'results/environment_audit.json').write_text(json.dumps(audit,indent=2))
    d=d.merge(e,on=['airport_id','year'],how='left',validate='many_to_one',suffixes=('','_env'));d['eligible']=d.eligible_pre_env&d.all_rings_eligible95.eq(True)&d.coordinate_accepted.eq(True)
    for flag in ['bird','near','eligible_pre_env','eligible']:flow[flag]=int(d[flag].sum())
    flow['unknown_damage_near']=int((d.near&d.damage_binary.isna()).sum());flow['conflicting_near']=int((d.near&d.conflict).sum())
    d['month']=pd.to_numeric(d.INCIDENT_MONTH,errors='coerce');dates=pd.to_datetime(d.INCIDENT_DATE,errors='coerce');assert dates[d.eligible].notna().all();assert (dates.dt.year[d.eligible]==d.year[d.eligible]).all();assert (dates.dt.month[d.eligible]==d.month[d.eligible]).all()
    d['month_sin']=np.sin(2*np.pi*d.month/12);d['month_cos']=np.cos(2*np.pi*d.month/12)
    for new,old in [('aircraft_mass_class','AC_MASS'),('phase','PHASE_OF_FLIGHT'),('bird_size_reported','SIZE'),('number_struck_category','NUM_STRUCK'),('faa_region','FAAREGION')]:d[new]=d[old].fillna('Unknown')
    base=['event_id','airport_id','year','month','month_sin','month_cos','damage_binary','DAMAGE_LEVEL','aircraft_mass_class','phase','bird_size_reported','number_struck_category','faa_region','label_completeness','SOURCE','PERSON','SPECIES','longitude','latitude']
    cols=base+[x for x in e if x not in base and x not in ['airport_id','year']]
    m=d.loc[d.eligible,cols].copy().reset_index(drop=True);m['year']=m.year.astype(int);m['damage_binary']=m.damage_binary.astype(int)
    folds=pd.read_csv(Path(args.folds));m=m.merge(folds[['airport_id','spatial_fold','overlap_component']],on='airport_id',how='left',validate='many_to_one');m['target']=m.airport_id.isin(targets)
    assert m.loc[~m.target,'spatial_fold'].notna().all(),m.loc[~m.target&m.spatial_fold.isna(),'airport_id'].unique()
    m['spatial_fold']=m.spatial_fold.fillna(0).astype(int)
    validate_events(m)
    m.to_parquet(W/'processed/analysis_events.parquet',index=False)
    ay=ay.merge(m.groupby(['airport_id','year']).agg(n=('event_id','size'),damage=('damage_binary','sum')).reset_index(),on=['airport_id','year'],how='left');ay.to_csv(W/'results/airport_year_audit.csv',index=False)
    s=m.groupby('airport_id').agg(n=('event_id','size'),damage=('damage_binary','sum'),years=('year','nunique'),region=('faa_region','first'),label_completeness=('label_completeness','mean')).reset_index();s.to_csv(W/'results/airport_summary.csv',index=False)
    m.groupby(['target','year']).agg(n=('event_id','size'),damage=('damage_binary','sum'),airports=('airport_id','nunique')).to_csv(W/'results/cohort_year_counts.csv')
    m.groupby(['target','DAMAGE_LEVEL']).size().to_csv(W/'results/damage_grade_counts.csv')
    flow.update(analysis_airports=int(m.airport_id.nunique()),damages=int(m.damage_binary.sum()),development_events=int((~m.target).sum()),development_airports=int(m.loc[~m.target,'airport_id'].nunique()),target_events=int(m.target.sum()),target_damages=int(m.loc[m.target,'damage_binary'].sum()))
    (W/'results/cohort_flow.json').write_text(json.dumps(flow,indent=2));print(json.dumps(flow,indent=2),flush=True);print(s[s.airport_id.isin(targets)].to_string(index=False),flush=True)
except Exception:
    (W / 'logs/cohort_failure.json').write_text(json.dumps({'traceback': traceback.format_exc()}, indent=2), encoding='utf-8')
    raise
