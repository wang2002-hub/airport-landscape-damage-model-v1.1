"""Descriptive report-source and reporter-role diagnostics using frozen probabilities."""
from pathlib import Path
import sys,json,hashlib,time,traceback
from datetime import datetime,timezone
import numpy as np
import pandas as pd
import argparse
from run_support import prepare_output
parser=argparse.ArgumentParser(description='Report-source composition and supported-population coding diagnostics.')
for key in ['data','near','raw','reference','source-benchmark','year-benchmark','output']:
    parser.add_argument('--'+key,required=True)
args=parser.parse_args()
OUT=prepare_output(args.output,{key:getattr(args,key) for key in ['data','near','raw','reference','source_benchmark','year_benchmark']},['results','logs'])/'results'
inputs=[];start=time.perf_counter()
A=['KDEN','KJFK','KMIA','KMSP','KBOS','KSFO','KSAT','KSTL']
FIELDS=['SOURCE','PERSON']

def read(p,columns=None):
    p=Path(p);inputs.append(dict(filename=p.name,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    return pd.read_parquet(p,columns=columns) if p.suffix=='.parquet' else pd.read_csv(p)

def clean(s):
    return s.astype('string').str.strip().replace('',pd.NA).fillna('Missing')

def populations(d):
    yield 'National',d[~d.airport_id.isin(A)]
    yield 'Eight targets',d[d.airport_id.isin(A)]
    for a in A: yield a,d[d.airport_id.eq(a)]

def divide(a,b): return float(a/b) if b else np.nan

def run():
    d=read(Path(args.data))
    near=read(Path(args.near))
    raw=read(Path(args.raw),columns=['INDEX_NR','INCIDENT_YEAR','LUPDATE','SOURCE','PERSON','record_completeness','source_row'])
    assert len(d)==52103 and len(near)==65254
    assert not d.event_id.duplicated().any() and not near.event_id.duplicated().any()
    assert int(near.known.sum())==54919 and int((~near.known).sum())==10335
    assert set(d.event_id)<=set(near.loc[near.known,'event_id'])
    damage=near.DAMAGE_LEVEL.map({'N':0,'M':1,'M?':1,'S':1,'D':1})
    components=pd.DataFrame({col:pd.to_numeric(near[col],errors='coerce').eq(1)|near[col].astype('string').str.upper().isin(['Y','YES','TRUE'])
                             for col in near if col.startswith('DAM_')}).any(axis=1)
    indicated=pd.to_numeric(near.INDICATED_DAMAGE,errors='coerce')
    conflict=((damage.eq(0)&(components|indicated.eq(1)))|(damage.eq(1)&indicated.eq(0))).fillna(False)
    assert near.known.eq(damage.notna()&~conflict).all() and int(conflict.sum())==0
    label_match=d[['event_id','damage_binary']].merge(pd.DataFrame({'event_id':near.event_id,'raw_damage':damage}),on='event_id',validate='one_to_one')
    assert label_match.damage_binary.eq(label_match.raw_damage).all()
    for obj in [d,near]:
        for field in FIELDS:obj[field]=clean(obj[field])
    raw['event_id']=raw.INDEX_NR.astype('string').str.strip().str.replace(r'\.0$','',regex=True)
    raw['year']=pd.to_numeric(raw.INCIDENT_YEAR,errors='coerce')
    raw=raw[raw.year.between(2015,2025)].copy()
    raw['updated']=pd.to_datetime(raw.LUPDATE,errors='coerce')
    raw=raw.sort_values(['updated','record_completeness','source_row'],na_position='first').drop_duplicates('event_id',keep='last')
    assert len(raw)==186398
    for field in FIELDS:raw[field]=clean(raw[field])
    # Verify report fields against the deduplicated source records.
    for label,obj in [('final',d),('near',near)]:
        match=obj[['event_id']+FIELDS].merge(raw[['event_id']+FIELDS],on='event_id',validate='one_to_one',suffixes=('','_raw'))
        assert len(match)==len(obj)
        for field in FIELDS:assert match[field].eq(match[field+'_raw']).all(),(label,field)
    assert not d.PERSON.str.casefold().eq('carcass found').any()
    assert not near.PERSON.str.casefold().eq('carcass found').any()
    assert not d.SOURCE.eq('Missing').any()
    levels={f:sorted(set(near[f])|set(d[f])|{'Missing'}) for f in FIELDS}

    audits=[];composition=[];annual=[]
    panels=[('final','known',d),('near','known',near[near.known]),('near','unresolved',near[~near.known])]
    for panel,label,frame in panels:
        for pop,g in populations(frame):
            audits.append(dict(panel=panel,label=label,population=pop,n=len(g),airports=g.airport_id.nunique(),
                               source_missing=int(g.SOURCE.eq('Missing').sum()),person_missing=int(g.PERSON.eq('Missing').sum())))
            for period,v in [('2015-2025',g),('2024-2025',g[g.year>=2024])]:
                for field in FIELDS:
                    for level in levels[field]:
                        h=v[v[field].eq(level)]
                        record=dict(panel=panel,label=label,population=pop,period=period,field=field,level=level,n=len(h),
                                    population_n=len(v),share=divide(len(h),len(v)))
                        if panel=='final':
                            o=int(h.damage_binary.sum());u=int(h.DAMAGE_LEVEL.eq('M?').sum())
                            record.update(O=o,M_undetermined=u,documented_damage=o-u,damage_proportion=divide(o,len(h)),M_share_among_damage=divide(u,o))
                        composition.append(record)
            for year,v in g.groupby('year'):
                for field in FIELDS:
                    for level in levels[field]:
                        h=v[v[field].eq(level)]
                        annual.append(dict(panel=panel,label=label,population=pop,year=int(year),field=field,level=level,
                                           n=len(h),population_n=len(v),share=divide(len(h),len(v))))
    audits=pd.DataFrame(audits);composition=pd.DataFrame(composition);annual=pd.DataFrame(annual)
    for frame,keys in [(composition,['panel','label','population','period','field']),(annual,['panel','label','population','year','field'])]:
        q=frame.groupby(keys).agg(total=('n','sum'),denominator=('population_n','first'))
        assert q.total.eq(q.denominator).all()
    audits.to_csv(OUT/'reporting_population_audit.csv',index=False)
    composition.to_csv(OUT/'reporting_category_composition.csv',index=False)
    annual.to_csv(OUT/'reporting_category_by_year.csv',index=False)

    pred=read(Path(args.reference))
    assert not pred.event_id.duplicated().any()
    x=pred.merge(d[['event_id','SOURCE','PERSON','DAMAGE_LEVEL','damage_binary']],on='event_id',validate='one_to_one',suffixes=('','_check'))
    assert x.damage_binary.eq(x.damage_binary_check).all()
    assert len(x[x.dataset.eq('national')])==11124 and x.loc[x.dataset.eq('national'),'year'].ge(2024).all()
    assert len(x[x.dataset.eq('target')])==5936
    strata=[];totals=[]
    for period,g in [('2015-2025',x[x.dataset.eq('target')]),('2024-2025',x[x.year>=2024])]:
        for pop,v in populations(g):
            if not len(v):continue
            totals.append(dict(period=period,population=pop,n=len(v),O=int(v.damage_binary.sum()),E=v.p_calibrated.sum(),
                               OE=v.damage_binary.sum()/v.p_calibrated.sum(),M_undetermined=int(v.DAMAGE_LEVEL.eq('M?').sum()),
                               reference='frozen temporal hierarchical EBL'))
            for field in FIELDS:
                for level in levels[field]:
                    h=v[v[field].eq(level)];o=int(h.damage_binary.sum());u=int(h.DAMAGE_LEVEL.eq('M?').sum());e=float(h.p_calibrated.sum())
                    strata.append(dict(period=period,population=pop,field=field,level=level,n=len(h),population_n=len(v),O=o,E=e,
                                       OE=divide(o,e),O_minus_E=o-e,M_undetermined=u,documented_damage=o-u,
                                       M_share_among_damage=divide(u,o),sparse_damaged_count=bool(o<5),
                                       empty_stratum=not len(h),reference='frozen temporal hierarchical EBL'))
    strata=pd.DataFrame(strata);totals=pd.DataFrame(totals)
    q=strata.groupby(['period','population','field'])[['n','O','E','M_undetermined']].sum().reset_index()
    q=q.merge(totals,on=['period','population'],suffixes=('','_total'),validate='many_to_one')
    for col in ['n','O','E','M_undetermined']:assert np.allclose(q[col],q[col+'_total'],atol=1e-10,rtol=1e-12)
    old=read(Path(args.source_benchmark))
    chk=strata[(strata.period=='2015-2025')&(strata.field=='SOURCE')&(strata.population.isin(A))&~strata.empty_stratum]
    chk=chk.merge(old,left_on=['population','level'],right_on=['airport','source'],validate='one_to_one',suffixes=('','_old'))
    assert len(chk)==len(old) and (chk.n==chk.n_old).all() and np.allclose(chk.E,chk.expected,atol=1e-10)
    strata.to_csv(OUT/'reporting_stratified_oe.csv',index=False)
    totals.to_csv(OUT/'reporting_prediction_populations.csv',index=False)

    # Descriptive standardization, with supported numerator and denominator kept together.
    nat=d[(~d.airport_id.isin(A))&d.damage_binary.eq(1)].copy()
    tar=d[d.airport_id.isin(A)&d.damage_binary.eq(1)].copy()
    nat['u']=nat.DAMAGE_LEVEL.eq('M?').astype(int);tar['u']=tar.DAMAGE_LEVEL.eq('M?').astype(int)
    cells=[];bench=[]
    for scheme,keys in [('year',['year']),('year_source',['year','SOURCE']),('year_person',['year','PERSON'])]:
        ref=nat.groupby(keys).agg(national_damaged=('event_id','size'),national_M=('u','sum')).reset_index()
        ref['national_fraction']=ref.national_M/ref.national_damaged
        for period,frame in [('2015-2025',tar),('2024-2025',tar[tar.year>=2024])]:
            for pop,g in populations(frame):
                if pop=='National' or not len(g):continue
                z=g.groupby(keys).agg(target_damaged=('event_id','size'),target_M=('u','sum')).reset_index()
                z=z.merge(ref,on=keys,how='left',validate='one_to_one')
                z['expected_M']=z.target_damaged*z.national_fraction
                z['population']=pop;z['period']=period;z['scheme']=scheme
                z['supported']=z.national_damaged.fillna(0).gt(0)
                z['small_reference_cell']=z.national_damaged.fillna(0).lt(5)
                cells.extend(z.to_dict('records'))
                for minimum in [1,5]:
                    v=z[z.national_damaged.fillna(0)>=minimum]
                    supported_n=int(v.target_damaged.sum());u=int(v.target_M.sum());e=float(v.expected_M.sum())
                    bench.append(dict(scheme=scheme,period=period,population=pop,minimum_national_damaged=minimum,
                                      total_target_damaged=len(g),total_target_M=int(g.u.sum()),supported_target_damaged=supported_n,
                                      supported_target_M=u,excluded_target_damaged=len(g)-supported_n,
                                      excluded_target_M=int(g.u.sum())-u,expected_M=e,descriptive_OE=divide(u,e),
                                      difference_pp=100*divide(u-e,supported_n),
                                      supported_target_damage_share=divide(supported_n,len(g)),
                                      supported_cells=len(v),small_reference_target_damage=int(v.loc[v.small_reference_cell,'target_damaged'].sum())))
    bench=pd.DataFrame(bench);cells=pd.DataFrame(cells)
    previous=read(Path(args.year_benchmark))
    y=bench[(bench.scheme=='year')&(bench.period=='2015-2025')&(bench.minimum_national_damaged==1)]
    for a in A:
        assert abs(y.loc[y.population.eq(a),'expected_M'].iloc[0]-previous.loc[previous.airport.eq(a),'expected_by_national_year'].iloc[0])<1e-10
    assert (bench.supported_target_damaged+bench.excluded_target_damaged==bench.total_target_damaged).all()
    assert (bench.supported_target_M+bench.excluded_target_M==bench.total_target_M).all()
    bench.to_csv(OUT/'reporting_coding_standardization.csv',index=False)
    cells.to_csv(OUT/'reporting_coding_support_cells.csv',index=False)
    checks=dict(timestamp_utc=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.perf_counter()-start,
                original_fields_verified_against_raw=True,unique_event_ids=True,final_reports=len(d),near_reports=len(near),
                original_damage_label_rule='recomputed and matched; zero conflicts',
                final_source_missing=int(d.SOURCE.eq('Missing').sum()),final_person_missing=int(d.PERSON.eq('Missing').sum()),
                category_denominators='passed',stratum_sums='passed',existing_target_source_results='matched',
                existing_year_only_M_benchmarks='matched',supported_population_accounting='passed',
                new_model_fits=0,inputs=inputs,levels=levels,
                limitations='Descriptive strata and composition benchmarks; no causal source effect, reporting probability, or prospective effectiveness estimate.')
    (OUT/'reporting_strata_checks.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
    print('Prediction populations\n',totals.to_string(index=False))
    print('JFK and pooled coding benchmarks\n',bench[(bench.population.isin(['KJFK','Eight targets']))&(bench.period=='2015-2025')].to_string(index=False))

try:run()
except Exception:
    (OUT/'reporting_strata_failure.json').write_text(json.dumps({'timestamp_utc':datetime.now(timezone.utc).isoformat(),'traceback':traceback.format_exc(),'inputs':inputs},indent=2),encoding='utf-8')
    raise
