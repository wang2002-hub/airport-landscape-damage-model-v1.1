"""Match retained surface weather to target reports using frozen model probabilities."""
from pathlib import Path
import argparse,json,re,traceback
import pandas as pd,numpy as np
from run_support import prepare_output,validate_events
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--inputs',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
manifest=Path(args.inputs).resolve(strict=True);config=json.loads(manifest.read_text(encoding='utf-8'))
paths={k:(manifest.parent/Path(v)).resolve(strict=True) for k,v in config['paths'].items()}
weather={a:[(manifest.parent/Path(p)).resolve(strict=True) for p in ps] for a,ps in config['weather_files'].items()}
files=[p for ps in weather.values() for p in ps]
if len(files)!=len(set(files)):raise ValueError('Duplicate weather input file.')
expected={'KDEN','KJFK','KMIA','KMSP','KBOS','KSFO','KSAT','KSTL'}
if set(weather)!=expected or any(len(ps)!=11 for ps in weather.values()):raise ValueError('Eight airports and eleven weather files per airport are required.')
D=prepare_output(args.output,{'bindings':manifest,**paths,**{f'weather_{a}_{i:02d}':p for a,ps in weather.items() for i,p in enumerate(ps)}},['processed','results','logs'])
try:
 d=pd.read_parquet(paths['analysis_events']);validate_events(d);d=d[d.target].copy()
 pr=pd.read_parquet(paths['frozen_predictions']);pr=pr[pr.dataset.eq('target')].copy()
 if not pr.event_id.is_unique or set(pr.event_id)!=set(d.event_id):raise ValueError('Frozen prediction identifiers do not match target reports.')
 for column in ['airport_id','year','damage_binary']:
  left=d.set_index('event_id')[column].sort_index();right=pr.set_index('event_id')[column].sort_index()
  if not left.equals(right):raise ValueError('Frozen prediction labels or population differ: '+column)
 if not pr.p_calibrated.between(0,1,inclusive='neither').all():raise ValueError('Invalid frozen probability.')
 d=d.merge(pr[['event_id','p_calibrated']],on='event_id',validate='one_to_one')
except Exception:
 (D/'logs/input_failure.txt').write_text(traceback.format_exc(),encoding='utf-8');raise
try:
 tz={'KDEN':'America/Denver','KJFK':'America/New_York','KMIA':'America/New_York','KMSP':'America/Chicago','KBOS':'America/New_York','KSFO':'America/Los_Angeles','KSAT':'America/Chicago','KSTL':'America/Chicago'}
 audit=[];joined=[];tzrows=[]
 for a,v in d.groupby('airport_id'):
  v=v.copy();parts=[]
  for p in weather[a]:
   q=pd.read_csv(p,usecols=['station','valid','tmpf','sknt','p01i','metar'],low_memory=False);t=pd.to_datetime(q.valid,errors='coerce',format='mixed')
   stamp=q.metar.astype('string').str.extract(r'\b(\d{2})(\d{2})(\d{2})Z\b').apply(pd.to_numeric,errors='coerce')
   comparable=t.notna()&stamp.notna().all(axis=1);matches=(t.dt.day.eq(stamp[0])&t.dt.hour.eq(stamp[1])&t.dt.minute.eq(stamp[2]))
   tzrows.append(dict(airport=a,file=p.name,rows=len(q),metar_comparable=int(comparable.sum()),utc_stamp_matches=int((comparable&matches).sum()),utc_match_pct=100*matches[comparable].mean()))
   assert comparable.sum()>100 and matches[comparable].mean()>=.99,(a,p.name,'timezone not established')
   q['weather_utc']=t.dt.tz_localize('UTC');q=q[q.station.eq(a[1:])&q.weather_utc.notna()].copy()
   for c in ['tmpf','sknt','p01i']:q[c]=pd.to_numeric(q[c],errors='coerce')
   q['tmpf']=q.tmpf.where(q.tmpf.between(-100,140));q['sknt']=q.sknt.where(q.sknt.between(0,200));q['p01i']=q.p01i.where(q.p01i.between(0,20))
   parts.append(q[['weather_utc','tmpf','sknt','p01i']])
  q=pd.concat(parts,ignore_index=True);dups=int(q.duplicated('weather_utc').sum());conflict=q.groupby('weather_utc')[['tmpf','sknt','p01i']].nunique(dropna=False).max(axis=1)>1
  bad=conflict[conflict].index;q=q[~q.weather_utc.isin(bad)].drop_duplicates('weather_utc').sort_values('weather_utc')
  # Raw FAA TIME is HH:MM or HHMM, local civil time. Ambiguous/nonexistent DST times excluded.
  st=v.TIME.astype('string').str.strip().str.replace(r'\.0$','',regex=True);colon=st.str.extract(r'^(\d{1,2}):(\d{2})(?::00)?$');compact=st.str.extract(r'^(\d{1,2})(\d{2})$');hours=pd.to_numeric(colon[0].fillna(compact[0]),errors='coerce');mins=pd.to_numeric(colon[1].fillna(compact[1]),errors='coerce')
  valid=hours.between(0,23)&mins.between(0,59);naive=pd.to_datetime(v.INCIDENT_DATE,errors='coerce').dt.normalize()+pd.to_timedelta(hours.where(valid),unit='h')+pd.to_timedelta(mins.where(valid),unit='m')
  local=naive.dt.tz_localize(tz[a],ambiguous='NaT',nonexistent='NaT');v['event_utc']=local.dt.tz_convert('UTC');v['clock_parse_ok']=valid
  eligible=v[v.event_utc.notna()].sort_values('event_utc');j=pd.merge_asof(eligible,q[['weather_utc']],left_on='event_utc',right_on='weather_utc',direction='backward',tolerance=pd.Timedelta('60min'));j['lag_min']=(j.event_utc-j.weather_utc).dt.total_seconds()/60
  # A high-frequency wind-only record must not mask a valid recent temperature observation.
  # Match each quantity independently to its latest nonmissing observation within the same window.
  for c in ['tmpf','sknt','p01i']:
   tcol=c+'_utc';right=q.loc[q[c].notna(),['weather_utc',c]].rename(columns={'weather_utc':tcol})
   j=pd.merge_asof(j,right,left_on='event_utc',right_on=tcol,direction='backward',tolerance=pd.Timedelta('60min'));j[c+'_lag_min']=(j.event_utc-j[tcol]).dt.total_seconds()/60
  # Preserve unmatched and missing-time reports explicitly.
  absent=v[v.event_utc.isna()].copy();j=pd.concat([j,absent],ignore_index=True);joined.append(j)
  audit.append(dict(airport=a,reports=len(v),valid_clock=int(valid.sum()),utc_event_time=int(v.event_utc.notna().sum()),dst_or_date_exclusions=int((valid&v.event_utc.isna()).sum()),surface_rows=sum(len(x) for x in parts),duplicate_rows=dups,conflicting_time_keys=len(bad),matched=int(j.weather_utc.notna().sum()),temperature_n=int(j.tmpf.notna().sum()),wind_n=int(j.sknt.notna().sum()),precip_n=int(j.p01i.notna().sum()),median_lag_min=float(j.lag_min.median()),max_lag_min=float(j.lag_min.max())))
  print('WEATHER',audit[-1],flush=True)
 out=pd.concat(joined,ignore_index=True);assert len(out)==5936 and out.event_id.nunique()==5936
 out.to_parquet(D/'processed/target_weather_matched.parquet',index=False)
 pd.DataFrame(audit).to_csv(D/'results/weather_match_audit.csv',index=False);pd.DataFrame(tzrows).to_csv(D/'results/timezone_evidence.csv',index=False)
 out['season']=out.month.map({12:'DJF',1:'DJF',2:'DJF',3:'MAM',4:'MAM',5:'MAM',6:'JJA',7:'JJA',8:'JJA',9:'SON',10:'SON',11:'SON'})
 out['temperature']=np.where(out.tmpf.isna(),'Missing',np.where(out.tmpf.lt(32),'Below 0 C','At least 0 C'))
 out['wind']=np.where(out.sknt.isna(),'Missing',np.where(out.sknt.ge(10),'At least 10 kt','Below 10 kt'))
 out['rain']=np.where(out.p01i.isna(),'Missing',np.where(out.p01i.gt(0),'Positive reported amount','Explicit zero'))
 rows=[];rng=np.random.default_rng(20261028)
 for period,v in [('all',out),('recent',out[out.year.ge(2024)])]:
  for a,w in [('pooled',v)]+list(v.groupby('airport_id')):
   for field in ['season','temperature','wind','rain','SKY','PRECIPITATION']:
    for level,u in w.groupby(field,dropna=False):
     y=u.damage_binary;p=u.p_calibrated;row=dict(period=period,airport=a,field=field,level=str(level),n=len(u),damage=int(y.sum()),mean_prediction=float(p.mean()),observed=float(y.mean()),bias_pp=100*float((p-y).mean()),oe=float(y.sum()/p.sum()))
     # Descriptive strata only; no multiplicity tests or fitted weather effects.
     rows.append(row)
 pd.DataFrame(rows).to_csv(D/'results/residual_strata.csv',index=False)
 (D/'results/weather_methods.json').write_text(json.dumps({'timezone':'FAA local civil time converted with airport IANA zone; DST ambiguous/nonexistent excluded. CSV UTC verified against each file embedded METAR DDHHMMZ.', 'matching':'Each variable matched independently to most recent nonmissing nonconflicting same-station observation no more than 60 min before event. No future observations. Duplicate conflicting timestamps excluded for all three variables.', 'precipitation':'p01i from matched surface record only, not standalone XLSX hourly series. This is the reported accumulation, not rain at impact. Trace/non-numeric missing, not zero.', 'limits':'Post hoc, fixed predictions, target-only associations; no national model input or causal interpretation. Standalone precipitation time basis not established; audited but not merged.'},indent=2),encoding='utf-8')
except Exception:
 (D/'logs/processing_failure.txt').write_text(traceback.format_exc(),encoding='utf-8');raise
