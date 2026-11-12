"""Summarize landscape context, report composition and frozen annual influence."""
from pathlib import Path
import argparse,json,traceback
import pandas as pd
import numpy as np
from run_support import prepare_output,validate_events

parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--inputs',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
manifest=args.inputs.resolve(strict=True);cfg=json.loads(manifest.read_text(encoding='utf-8'))
paths={k:(manifest.parent/Path(v)).resolve(strict=True) for k,v in cfg['paths'].items()}
D=prepare_output(args.output,{'bindings':manifest,**paths},['results','logs'])
def save(name,x):x.to_csv(D/'results'/name,index=False,encoding='utf-8-sig')
try:
 e=pd.read_parquet(paths['environment']);d=pd.read_parquet(paths['analysis_events']);validate_events(d)
 if e.duplicated(['airport_id','year']).any():raise ValueError('Duplicate environment airport-year.')
 if not e.year.between(2015,2025).all():raise ValueError('Environment year outside the study window.')
 n=d[~d.target];t=d[d.target];targets=t.airport_id.unique()
 can=pd.read_csv(paths['canopy']);can=can[can.airport_id.isin(targets)&can.zone.eq('b13')].copy()
 if len(can)!=24 or can.duplicated(['airport_id','year']).any() or set(can.year)!={2015,2020,2025}:raise ValueError('Incomplete or duplicate target canopy records.')
 if not can.groupby('airport_id').year.nunique().eq(3).all():raise ValueError('Incomplete target canopy years.')
 pred=pd.read_parquet(paths['frozen_predictions']);pred=pred[pred.dataset.eq('target')].copy()
 if not pred.event_id.is_unique or set(pred.event_id)!=set(t.event_id):raise ValueError('Frozen prediction identifiers differ from target reports.')
 for col in ['airport_id','year','damage_binary']:
  if not t.set_index('event_id')[col].sort_index().equals(pred.set_index('event_id')[col].sort_index()):raise ValueError('Frozen prediction labels or population differ: '+col)
 if not pred.p_calibrated.between(0,1,inclusive='neither').all():raise ValueError('Invalid frozen probability.')
except Exception:
 (D/'logs/input_failure.txt').write_text(traceback.format_exc(),encoding='utf-8');raise
try:
 save('canopy_target_context.csv',can)
 national=e[e.airport_id.isin(n.airport_id.unique())].copy()
 good=national.groupby('airport_id').filter(lambda z:len(z)==11 and z.year.nunique()==11 and z.all_rings_eligible95.all())
 fields=['water_fraction__b13','wetland_fraction__b13','cropland_fraction__b13','grassland_fraction__b13','pasture_fraction__b13','impervious_mean_pct__b13']
 variation=[];targetenv=e[e.airport_id.isin(targets)][['airport_id','year']+fields].copy()
 for c in fields:
  factor=1 if c.startswith('impervious') else 100
  grouped=good.groupby('airport_id')[c]
  span=(grouped.max()-grouped.min())*factor
  variation.append(dict(field=c,airports=good.airport_id.nunique(),airport_years=len(good),
    between_airport_sd_pp=grouped.mean().std(ddof=1)*factor,
    within_airport_sd_pp=np.sqrt(grouped.var(ddof=1).mean())*factor,
    median_full_period_range_pp=span.median(),percent_airports_range_below_1pp=100*span.lt(1).mean()))
  targetenv[c]*=factor
 save('landscape_variation.csv',pd.DataFrame(variation));save('target_landscape_context.csv',targetenv)

 # Full-period reference outcomes are descriptive, not held-out predictions.
 strata=['phase','aircraft_mass_class','bird_size_reported']
 ref=n.groupby(strata,dropna=False).agg(reference_n=('event_id','size'),reference_airports=('airport_id','nunique'),reference_damage=('damage_binary','sum')).reset_index()
 ref['reference_proportion']=ref.reference_damage/ref.reference_n
 ref['supported']=ref.reference_n.ge(20)&ref.reference_airports.ge(5)
 save('standardization_reference_strata.csv',ref)
 st=[]
 for aid,sub in t.groupby('airport_id'):
  q=sub.merge(ref,on=strata,how='left',validate='many_to_one');s=q[q.supported.fillna(False)].copy()
  assert len(s)>0
  st.append(dict(airport=aid[1:],target_n=len(q),supported_n=len(s),unsupported_n=len(q)-len(s),
   support_pct=100*len(s)/len(q),national_observed_pct=100*n.damage_binary.mean(),
   standardized_reference_pct=100*s.reference_proportion.mean(),
   supported_target_observed_pct=100*s.damage_binary.mean(),target_observed_pct=100*q.damage_binary.mean(),
   supported_strata=len(s[strata].drop_duplicates())))
 save('case_mix_standardization.csv',pd.DataFrame(st))
 assert set(pred.event_id)==set(t.event_id)
 rows=[];annual=[]
 for aid,sub in pred.groupby('airport_id'):
  for yr,part in sub.groupby('year'):
   annual.append(dict(airport=aid[1:],year=int(yr),reports=len(part),damage=int(part.damage_binary.sum()),observed_pct=100*part.damage_binary.mean(),predicted_pct=100*part.p_calibrated.mean(),bias_pp=100*(part.p_calibrated.mean()-part.damage_binary.mean())))
   q=sub[sub.year.ne(yr)]
   rows.append(dict(airport=aid[1:],omitted_year=int(yr),retained_n=len(q),retained_damage=int(q.damage_binary.sum()),bias_pp=100*(q.p_calibrated.mean()-q.damage_binary.mean()),oe=q.damage_binary.sum()/q.p_calibrated.sum()))
 save('local_annual_predictions.csv',pd.DataFrame(annual));save('leave_one_year_out.csv',pd.DataFrame(rows))
 loo=pd.DataFrame(rows).groupby('airport').agg(bias_min_pp=('bias_pp','min'),bias_max_pp=('bias_pp','max'),oe_min=('oe','min'),oe_max=('oe','max')).reset_index();save('leave_one_year_out_summary.csv',loo)
 coords=d.groupby('airport_id').agg(longitude=('longitude','first'),latitude=('latitude','first'),target=('target','first'),reports=('event_id','size'),region=('faa_region','first')).reset_index();save('map_airports.csv',coords)

 summary={'scope':'Descriptive report and environmental context using frozen predictions. No fitted effect, confidence interval or causal adjustment is estimated.',
          'national_environment_airports':int(good.airport_id.nunique()),'national_environment_years':len(good),
          'national_reports':len(n),'target_reports':len(t),'target_damage':int(t.damage_binary.sum()),
          'tables_written':9,'new_model_fits':0,'new_random_draws':0}
 (D/'results/context_scope.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
 print(json.dumps(summary),flush=True)
except Exception:
 (D/'logs/failure.txt').write_text(traceback.format_exc(),encoding='utf-8');raise
