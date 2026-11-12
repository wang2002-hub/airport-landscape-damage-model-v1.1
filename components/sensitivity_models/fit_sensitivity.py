"""Outcome, report-collection, map-timing and spatial sensitivity analyses."""
from pathlib import Path
import argparse,json,traceback
from model_core import *
from model_fitting import checked_fit
from run_support import prepare_output,validate_events

SCENARIOS=['exclude_M_question','label70','label80','contemporary2016','lagged','fixed2015','ilr','buffer50']
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--data',required=True)
parser.add_argument('--environment',required=True)
parser.add_argument('--output',required=True)
parser.add_argument('--scenario',choices=['all']+SCENARIOS,default='all')
parser.add_argument('--block',choices=['all','E','EL','EB','EBL'],default='all')
args=parser.parse_args()
W=prepare_output(args.output,{'analysis_events':args.data,'environment':args.environment},['results','logs'])
d=pd.read_parquet(args.data);env=pd.read_parquet(args.environment)
try:
 validate_events(d)
 if env.duplicated(['airport_id','year']).any():raise ValueError('Duplicate environment key.')
 if env[['airport_id','year']].isna().any().any():raise ValueError('Missing environment key.')
 if not env.year.between(2015,2025).all():raise ValueError('Unexpected environment year.')
except Exception:
 (W/'logs/input_failure.txt').write_text(traceback.format_exc(),encoding='utf-8');raise
cols=[f'{part}_fraction__{zone}' for part in ['water','developed','forest','shrub','grassland','pasture','cropland','wetland','other'] for zone in ['b03','b08','b13','r00_03','r03_08','r08_13']]+[f'impervious_mean_pct__{zone}' for zone in ['b03','b08','b13','r00_03','r03_08','r08_13']]
def maps(data,which):
 a=data.copy();ref=env[['airport_id','year','all_rings_eligible95']+cols].copy().rename(columns={'all_rings_eligible95':'source_map_eligible'})
 if which=='lagged':ref['year']+=1
 elif which=='fixed2015':
  ref=ref[ref.year.eq(2015)].drop(columns='year');a=a.drop(columns=cols).merge(ref,on='airport_id',how='left',validate='many_to_one');return a
 return a.drop(columns=cols).merge(ref,on=['airport_id','year'],how='left',validate='many_to_one')
aps=d[['airport_id','longitude','latitude','target']].drop_duplicates('airport_id');tar=aps[aps.target];lat=np.deg2rad(aps.latitude.to_numpy(float));lon=np.deg2rad(aps.longitude.to_numpy(float));dist=[]
for r in tar.itertuples():
 dl=lat-np.deg2rad(r.latitude);do=lon-np.deg2rad(r.longitude);dist.append(6371*2*np.arcsin(np.sqrt(np.sin(dl/2)**2+np.cos(lat)*np.cos(np.deg2rad(r.latitude))*np.sin(do/2)**2)))
aps['min_target_distance_km']=np.min(dist,axis=0);aps.to_csv(W/'results/target_distance_audit.csv',index=False);near=set(aps.loc[~aps.target&aps.min_target_distance_km.lt(50),'airport_id'])
scenarios={'exclude_M_question':d[~d.DAMAGE_LEVEL.eq('M?')], 'label70':d[d.label_completeness.ge(.7)],'label80':d[d.label_completeness.ge(.8)],'contemporary2016':d[d.year.ge(2016)],'lagged':maps(d[d.year.ge(2016)],'lagged'),'fixed2015':maps(d[d.year.ge(2016)],'fixed2015'),'ilr':d,'buffer50':d[~d.airport_id.isin(near)]}
# All three map comparisons use the intersection of complete measurement rows.
ids=set(scenarios['contemporary2016'].event_id)
for name in ['contemporary2016','lagged','fixed2015']:
 eligible=scenarios[name].get('source_map_eligible',scenarios[name].all_rings_eligible95)
 ids&=set(scenarios[name].loc[scenarios[name][cols].notna().all(axis=1)&eligible.eq(True),'event_id'])
for name in ['contemporary2016','lagged','fixed2015']:scenarios[name]=scenarios[name][scenarios[name].event_id.isin(ids)]
membership=[]
for scenario,x in scenarios.items():
 for dataset,part in [('train',x[~x.target&x.year.le(2022)]),('calibration',x[~x.target&x.year.eq(2023)]),('national_test',x[~x.target&x.year.ge(2024)]),('target',x[x.target])]:
  ids_sorted=sorted(part.event_id.astype(str))
  import hashlib
  membership.append({'scenario':scenario,'dataset':dataset,'n':len(part),'damage':int(part.damage_binary.sum()),'airports':int(part.airport_id.nunique()),'event_id_sha256':hashlib.sha256('\n'.join(ids_sorted).encode()).hexdigest()})
(W/'results/scenario_membership.json').write_text(json.dumps(membership,indent=2),encoding='utf-8')
statuses=[]
for name,x in scenarios.items():
 if args.scenario not in ['all',name]:continue
 for block in ['E','EL','EB','EBL']:
  if args.block not in ['all',block]:continue
  tag=f'sensitivity_{name}_{block}';out=W/'results'/f'{tag}.parquet'
  if out.exists():raise FileExistsError('Task output already exists: '+tag)
  records=[]
  try:
   n=x[~x.target];train=n[n.year.le(2022)];cal=n[n.year.eq(2023)];test=n[n.year.ge(2024)];target=x[x.target];scale='b03' if 'L' in block else None;mode='ilr' if name=='ilr' else 'level'
   b=checked_fit(train,'glmm',scale,int('B' in block),None,records,'final',mode=mode,screen=name!='ilr');b['calibrator'],cr=fit_calibrator(cal.damage_binary.to_numpy(),predict_bundle(b,cal));assert cr['success'];outs=[]
   for ds,sub in [('national',test),('target',target)]:
    o=sub[['event_id','airport_id','year','damage_binary']].copy();o['p_calibrated']=predict_bundle(b,sub,True);o['dataset']=ds;o['model']=block;o['family']='glmm';o['scenario']=name;outs.append(o)
   pd.concat(outs).to_parquet(out,index=False);(W/'results'/f'{tag}.json').write_text(json.dumps({'train_n':len(train),'cal_n':len(cal),'test_n':len(test),'target_n':len(target),'fits':records,'calibration':cr,'encoder':b['encoder'].metadata(),'excluded_near_target_airports':sorted(near) if name=='buffer50' else []},indent=2,default=str));statuses.append({'scenario':name,'block':block,'success':True});print('DONE',tag,flush=True)
  except Exception:
   (W/'logs'/f'{tag}_failure.txt').write_text(traceback.format_exc(),encoding='utf-8');statuses.append({'scenario':name,'block':block,'success':False});print('FAILED',tag,flush=True)

(W/'run_status.json').write_text(json.dumps({'tasks':statuses,'success':all(x['success'] for x in statuses)},indent=2),encoding='utf-8')
if any(not x['success'] for x in statuses):raise SystemExit(1)
