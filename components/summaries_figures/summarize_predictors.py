"""Describe retained predictors and reconstruct saved partitions without model fitting."""
from pathlib import Path
import sys,json,hashlib,re
import numpy as np,pandas as pd
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
from artifact_inputs import Inputs
I=Inputs(__doc__);OUT=I.output/'results';R=OUT
input_paths=[I.path('cohort'),I.path('extended_cohort'),I.path('analysis_config'),I.path('simple_run')]
snapshot={'inputs':{p.name:sha(p) for p in input_paths}}
import traceback
try:
 d=pd.read_parquet(input_paths[0]);ex=pd.read_parquet(input_paths[1]);P=json.loads(input_paths[2].read_text())
 assert d.event_id.is_unique and ex.event_id.is_unique and set(d.event_id)==set(ex.event_id)
 ex=ex.set_index('event_id').loc[d.event_id].reset_index()
 for c in ['airport_id','year','damage_binary','target','spatial_fold']:assert d[c].astype(str).tolist()==ex[c].astype(str).tolist(),c
 nat=~d.target;tar=d.target;assert set(d.loc[tar,'airport_id'])==set(P['target_airports'])
 parts={'Train':nat&(d.year<=2022),'Calibration':nat&d.year.eq(2023),'Test':nat&(d.year>=2024),'Targets':tar,'Recent targets':tar&(d.year>=2024),'National all':nat}
 parts.update({a[1:]:d.airport_id.eq(a) for a in P['target_airports']});parts.update({f'Outer fold {i}':nat&d.spatial_fold.eq(i) for i in range(1,6)})
 main=['Train','Calibration','Test','Targets']
 def count(mask):
  s=d.loc[mask];return {'n':len(s),'damage':int(s.damage_binary.sum()),'airports':int(s.airport_id.nunique()),'year_min':int(s.year.min()),'year_max':int(s.year.max())}
 counts=pd.DataFrame([dict(population=k,**count(v)) for k,v in parts.items()]);counts.to_csv(OUT/'population_counts.csv',index=False)
 assert counts.set_index('population').loc[main,'n'].tolist()==[30427,4616,11124,5936]
 assert sum(counts.set_index('population').loc[main,'damage'])==3405
 cat_defs=[('aircraft_mass_class','AC_MASS','Aircraft mass class'),('phase','PHASE_OF_FLIGHT','Flight phase'),('bird_size_reported','SIZE','Bird size'),('number_struck_category','NUM_STRUCK','Number struck'),('TIME_OF_DAY','TIME_OF_DAY','Time of day'),('AC_CLASS','AC_CLASS','Aircraft class'),('TYPE_ENG','TYPE_ENG','Engine type'),('NUM_ENGS','NUM_ENGS','Engine count')]
 catvals={};rawmissing={};unknown={};invalid={};metadata=[]
 for field,raw,label in cat_defs:
  s=ex[raw].astype('string').str.strip();m=s.isna()|s.eq('').fillna(False);u=s.str.casefold().eq('unknown').fillna(False)&~m
  values=s.mask(m,'Unknown')
  if field in d:assert values.tolist()==d[field].astype('string').tolist(),field
  catvals[field]=values;rawmissing[field]=m;unknown[field]=u;invalid[field]=pd.Series(False,index=d.index)
  metadata.append(dict(field=field,label=label,kind='categorical',raw_field=raw,unit='recorded category',block='Primary' if field in d else 'Seven-field extension'))
 nums={};nraw={}
 for field,label in [('year','Incident year'),('month_sin','Month sine'),('month_cos','Month cosine')]:
  nums[field]=pd.to_numeric(d[field],errors='coerce').astype(float);nraw[field]=d[field]
  metadata.append(dict(field=field,label=label,kind='numeric',raw_field=field,unit='year' if field=='year' else 'unitless',block='Primary'))
 for scale,radius in [('b03','3 km'),('b08','8 km'),('b13','13 km')]:
  for v,label in [('water_fraction','Water'),('wetland_fraction','Wetland'),('cropland_fraction','Cropland'),('grassland_fraction','Grassland'),('pasture_fraction','Pasture'),('impervious_mean_pct','Imperviousness')]:
   field=v+'__'+scale;nums[field]=d[field]*(1 if v.endswith('pct') else 100);nraw[field]=d[field]
   metadata.append(dict(field=field,label=label+' '+radius,kind='numeric',raw_field=field,unit='percent',block='Landscape candidate'))
 for zone,ring in [('r00_03','0–3 km'),('r03_08','3–8 km'),('r08_13','8–13 km')]:
  for field,label,value in [('water_wetland__'+zone,'Water plus wetland',100*(d['water_fraction__'+zone]+d['wetland_fraction__'+zone])),('cropland__'+zone,'Cropland',100*d['cropland_fraction__'+zone])]:
   nums[field]=value;nraw[field]=value;metadata.append(dict(field=field,label=label+' '+ring,kind='numeric',raw_field=field,unit='percent',block='Landscape candidate'))
 for field,label,unit in [('HEIGHT','Height','ft'),('DISTANCE','Distance','nautical miles'),('SPEED','Speed','indicated knots')]:
  s=ex[field];v=pd.to_numeric(s,errors='coerce').astype(float)
  if field=='SPEED':v=v.where(v.between(0,400))
  nums[field]=v;nraw[field]=s;metadata.append(dict(field=field,label=label,kind='numeric',raw_field=field,unit=unit,block='Seven-field extension'))
 for field,v in nums.items():
  s=nraw[field];rawmissing[field]=s.isna()|s.astype('string').str.strip().eq('').fillna(False);unknown[field]=pd.Series(False,index=d.index)
  invalid[field]=~rawmissing[field]&~np.isfinite(v);nums[field]=v.where(np.isfinite(v))
 assert len(metadata)==38
 missing=[];numeric=[];categorical=[]
 for pop,mask in parts.items():
  n=int(mask.sum())
  for x in metadata:
   c=x['field'];m=int(rawmissing[c][mask].sum());u=int(unknown[c][mask].sum());bad=int(invalid[c][mask].sum())
   missing.append(dict(population=pop,field=c,label=x['label'],n=n,source_missing=m,explicit_unknown=u,invalid_numeric=bad,unavailable=m+u+bad,unavailable_pct=100*(m+u+bad)/n))
   if c in nums:
    a=nums[c][mask].dropna();quant=a.quantile([.25,.5,.75]);numeric.append(dict(population=pop,field=c,label=x['label'],unit=x['unit'],n=n,valid=len(a),q1=quant.loc[.25],median=quant.loc[.5],q3=quant.loc[.75],minimum=a.min(),maximum=a.max()))
   else:
    vc=catvals[c][mask].value_counts(dropna=False)
    for level in sorted(catvals[c].unique()):categorical.append(dict(population=pop,field=c,label=x['label'],level=level,n=n,count=int(vc.get(level,0)),percent=100*int(vc.get(level,0))/n))
 mf=pd.DataFrame(missing);nf=pd.DataFrame(numeric);cf=pd.DataFrame(categorical)
 mf.to_csv(OUT/'predictor_missingness_by_population.csv',index=False);nf.to_csv(OUT/'numeric_distributions_by_population.csv',index=False);cf.to_csv(OUT/'categorical_distributions_by_population.csv',index=False)
 assert (cf.groupby(['population','field'])['count'].sum()==cf.groupby(['population','field']).n.first()).all()
 for c in nums:
  assert (nf[nf.field.eq(c)].set_index('population').valid+mf[mf.field.eq(c)].set_index('population').unavailable==counts.set_index('population').n).all()
 airport=[]
 for x in metadata:
  c=x['field'];tmp=pd.DataFrame({'airport':d.airport_id,'missing':rawmissing[c].astype(int),'unknown':unknown[c].astype(int),'invalid':invalid[c].astype(int)})
  g=tmp.groupby('airport').agg(n=('airport','size'),source_missing=('missing','sum'),explicit_unknown=('unknown','sum'),invalid_numeric=('invalid','sum')).reset_index();g['field']=c;g['unavailable']=g.source_missing+g.explicit_unknown+g.invalid_numeric;airport.append(g)
 af=pd.concat(airport,ignore_index=True);assert len(af)==1383*38;af.to_csv(OUT/'predictor_missingness_all_airports.csv',index=False)
 pd.DataFrame(metadata).to_csv(OUT/'predictor_dictionary.csv',index=False)
 pairs=[];pair_masks={}
 def pair(name,tr,va):
  assert not (tr&va).any();a=count(tr);b=count(va);pairs.append(dict(pair=name,train_n=a['n'],train_damage=a['damage'],train_airports=a['airports'],evaluation_n=b['n'],evaluation_damage=b['damage'],evaluation_airports=b['airports']));pair_masks[name]=(tr,va)
 for yr in P['inner_temporal_years']:pair(f'Temporal {yr}',nat&(d.year<yr),nat&d.year.eq(yr))
 for fold in range(1,6):
  train=nat&d.spatial_fold.ne(fold);test=nat&d.spatial_fold.eq(fold);pair(f'Outer {fold}',train,test)
  for inner in sorted(d.loc[train,'spatial_fold'].unique()):pair(f'Outer {fold} inner {inner}',train&d.spatial_fold.ne(inner),train&d.spatial_fold.eq(inner))
 assert len(pairs)==29;pd.DataFrame(pairs).to_csv(OUT/'validation_partition_pairs.csv',index=False)
 checks=[];config_paths=[]
 for path in sorted(I.path('national_results').glob('*_config.json')):
  if not re.match(r'(temporal_0|spatial_[1-5])_(glmm|hgb)_(E|EL|EB|EBL)_config.json',path.name):continue
  config_paths.append(path);j=json.loads(path.read_text());fold=j['fold'];temporal=j['scheme']=='temporal';training=parts['Train'] if temporal else nat&d.spatial_fold.ne(fold)
  for fit in j['fits']:
   if fit['label']=='final':mask=training
   else:
    ix=int(fit['label'].rsplit('inner',1)[1]);mask=pair_masks[f'Temporal {P["inner_temporal_years"][ix]}'][0] if temporal else pair_masks[f'Outer {fold} inner {sorted(d.loc[training,"spatial_fold"].unique())[ix]}'][0]
   c=count(mask)
   for key in ['n','damage','airports']:assert fit[key]==c[key],(path.name,fit['label'],key)
   checks.append(dict(config=path.name,label=fit['label'],n=c['n'],damage=c['damage'],airports=c['airports']))
 assert len(config_paths)==48 and len(checks)==768
 simple=json.loads((I.path('simple_run')).read_text())
 for fit in simple['fits']:
  label=fit['label']
  if label=='temporal_final':mask=parts['Train']
  else:
   m=re.match(r'spatial_(\d+)_(final|inner_(\d+))',label);f=int(m[1]);mask=nat&d.spatial_fold.ne(f) if m[2]=='final' else pair_masks[f'Outer {f} inner {m[3]}'][0]
  c=count(mask)
  for key in ['n','damage','airports']:assert fit[key]==c[key]
  checks.append(dict(config='simple_run.json',label=label,**{k:c[k] for k in ['n','damage','airports']}))
 enhanced_fits=0
 for path in sorted(I.path('enhanced_results').glob('enhanced_*_config.json')):
  config_paths.append(path);j=json.loads(path.read_text())
  for fit in j['fits']:
   mask=parts['Train'] if fit['label']=='final' else pair_masks[f'Temporal {fit["label"][-4:]}'][0]
   c=count(mask);assert fit['n']==c['n'];enhanced_fits+=1
   checks.append(dict(config=path.name,label=fit['label'],n=c['n'],damage=c['damage'],airports=c['airports']))
 pd.DataFrame(checks).to_csv(OUT/'saved_fit_population_checks.csv',index=False)
 # Input provenance contains names and digests, never copies of event-level records.
 snapshot['model_configs']={p.name:sha(p) for p in config_paths}
 (R/'predictor_reporting_input_snapshot.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2),encoding='utf-8')
 summary={'populations':len(parts),'predictors':len(metadata),'numeric_predictors':len(nums),'categorical_predictors':len(catvals),'primary_fits_checked':768,'simple_fits_checked':len(simple['fits']),'enhanced_fits_checked':enhanced_fits,'partition_pairs':29,'all_airport_missingness_rows':len(af),'primary_landscape_unavailable_cells':int(mf[mf.field.str.contains('__')].unavailable.sum()),'main_missingness':mf[mf.population.isin(main)&mf.unavailable.gt(0)].to_dict('records'),'new_model_fits':0,'new_random_draws':0,'event_level_outputs':False}
 (R/'predictor_reporting_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({k:v for k,v in summary.items() if k!='main_missingness'},indent=2));print(mf[mf.population.isin(main)&mf.unavailable.gt(0)][['population','label','source_missing','explicit_unknown','invalid_numeric','unavailable_pct']].to_string(index=False))
except Exception:
 (I.output/'logs/predictor_failure.json').write_text(json.dumps({'traceback':traceback.format_exc()},indent=2),encoding='utf-8')
 raise
