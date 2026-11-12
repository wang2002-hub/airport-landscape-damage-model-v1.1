"""Reconstruct airport-year environmental inputs from retained zonal measurements."""
from pathlib import Path
import argparse,json,traceback
import numpy as np
import pandas as pd
from run_support import prepare_output
GROUPS={'water':[11],'developed':[21,22,23,24],'forest':[41,42,43],'shrub':[52],'grassland':[71],'pasture':[81],'cropland':[82],'wetland':[90,95],'other':[12,31]}
ZONES=['r00_03','r03_08','r08_13','b03','b08','b13']
YEARS=list(range(2015,2026))

def require(condition,message):
    if not bool(condition):raise ValueError(message)

def validate(env,st,tr,points):
    key=['airport_id','year','zone']
    require(not env.duplicated(key).any(),'Duplicate environmental key.')
    accepted=points.loc[points.coordinate_accepted.eq(True),'airport_id']
    require(accepted.is_unique,'Duplicate accepted airport reference.')
    expected=pd.MultiIndex.from_product([accepted,YEARS,ZONES],names=key)
    actual=pd.MultiIndex.from_frame(env[key])
    require(len(actual)==len(expected) and actual.sort_values().equals(expected.sort_values()),'Incomplete airport-year-zone grid.')
    for name in ['landcover','impervious']:
        n=env[name+'_valid_pixels'].to_numpy(float);area=env.geometry_area_km2.to_numpy(float)
        require(np.isfinite(area).all() and (area>0).all(),'Invalid geometry area.')
        require(np.isfinite(n).all() and (n>=0).all() and (n==np.floor(n)).all(),'Invalid pixel count.')
        require(np.allclose(np.minimum(1,n*.0009/area),env[name+'_coverage'],atol=1e-12,rtol=0),'Coverage denominator mismatch.')
    fractions=env[[x+'_fraction' for x in GROUPS]]
    observed=env.landcover_valid_pixels.gt(0)
    require(fractions.loc[observed].notna().all().all(),'Incomplete observed composition.')
    require(np.allclose(fractions.loc[observed].sum(axis=1),1,atol=1e-12,rtol=0),'Composition closure mismatch.')
    require(fractions.loc[~observed].isna().all().all(),'Missing coverage requires missing fractions.')
    require(((fractions>=0)&(fractions<=1)|fractions.isna()).all().all(),'Composition outside unit interval.')
    for threshold in [90,95]:
        cover=(env.landcover_coverage.ge(threshold/100)&env.impervious_coverage.ge(threshold/100))
        require(env['coverage_pass'+str(threshold)].equals(cover),'Stored coverage flag mismatch.')
        require(env['eligible'+str(threshold)].equals(cover&~env.airport_id.eq('KDEN*')),'Stored eligibility flag mismatch.')
    require(env.loc[~env.year.isin([2015,2020,2025]),'canopy_mean_pct'].isna().all(),'Unobserved canopy years must stay missing.')
    require(env.impervious_mean_pct.dropna().between(0,100).all(),'Impervious percentage outside bounds.')
    require(not st.duplicated(key).any(),'Duplicate structure key.')
    structure_keys=pd.MultiIndex.from_frame(st.loc[st.airport_id.ne('KDEN_ALT'),key])
    expected_structure=pd.MultiIndex.from_product([accepted,YEARS,ZONES[3:]],names=key)
    require(structure_keys.sort_values().equals(expected_structure.sort_values()),'Incomplete structure grid.')
    tk=['airport_id','year_from','year_to','zone']
    require(not tr.duplicated(tk).any(),'Duplicate transition key.')
    pairs=[(y-1,y) for y in YEARS[1:]]+[(2015,2020),(2020,2025)]
    expected_tr=pd.MultiIndex.from_tuples([(a,y0,y1,z) for a in accepted for y0,y1 in pairs for z in ZONES],names=tk)
    actual_tr=pd.MultiIndex.from_frame(tr.loc[tr.airport_id.ne('KDEN_ALT'),tk])
    require(actual_tr.sort_values().equals(expected_tr.sort_values()),'Incomplete transition grid.')
    require(tr.marginals_verified.eq(True).all(),'Unverified transition marginals.')

def reconstruct(env,st,tr,points,output):

    changes=[]
    indexed=env.set_index(['airport_id','year','zone'])
    for row in tr.itertuples():
        if row.airport_id=='KDEN_ALT':continue
        a=indexed.loc[(row.airport_id,row.year_from,row.zone)];b=indexed.loc[(row.airport_id,row.year_to,row.zone)]
        out={'airport_id':row.airport_id,'year_from':row.year_from,'year_to':row.year_to,'zone':row.zone,'both_years_eligible95':bool(a.eligible95 and b.eligible95),'common_coverage':row.common_coverage,'changed_fraction':row.changed_fraction,'impervious_mean_delta_pp':b.impervious_mean_pct-a.impervious_mean_pct,'impervious_mean_delta_common_pp':row.impervious_mean_delta_common_pp}
        for k in GROUPS:out[k+'_delta_pp']=100*(b[k+'_fraction']-a[k+'_fraction']);out[k+'_delta_common_pp']=getattr(row,k+'_delta_common_pp')
        changes.append(out)
    ch=pd.DataFrame(changes);ch.to_parquet(output/'landscape_changes.parquet',index=False)
    keep=['airport_id','year','zone']+[k+'_fraction' for k in GROUPS]+['landcover_coverage','impervious_mean_pct','impervious_ge80_fraction','impervious_coverage','canopy_mean_pct','canopy_coverage','coverage_pass95','coverage_pass90','eligible95','eligible90']
    wide=env[keep].pivot(index=['airport_id','year'],columns='zone');wide.columns=[f'{var}__{zone}' for var,zone in wide.columns];wide=wide.reset_index()
    sw=st[st.airport_id!='KDEN_ALT'].drop(columns=['valid_n']).pivot(index=['airport_id','year'],columns='zone');sw.columns=[f'{v}__{z}' for v,z in sw.columns];wide=wide.merge(sw.reset_index(),on=['airport_id','year'],validate='one_to_one')
    cc=ch[ch.year_to-ch.year_from==1].drop(columns=['year_from']).rename(columns={'year_to':'year'});cw=cc.pivot(index=['airport_id','year'],columns='zone');cw.columns=[f'{v}__{z}' for v,z in cw.columns];wide=wide.merge(cw.reset_index(),on=['airport_id','year'],how='left',validate='one_to_one')
    points=points.query('coordinate_accepted')[['airport_id','airport_name','state','longitude','latitude','facility_flag']];wide=wide.merge(points,on='airport_id',validate='many_to_one')
    wide['all_rings_eligible95']=wide[[f'eligible95__{z}' for z in ZONES[:3]]].all(axis=1);wide['all_rings_eligible90']=wide[[f'eligible90__{z}' for z in ZONES[:3]]].all(axis=1)
    wide['all_rings_coverage95']=wide[[f'coverage_pass95__{z}' for z in ZONES[:3]]].all(axis=1);wide['all_rings_coverage90']=wide[[f'coverage_pass90__{z}' for z in ZONES[:3]]].all(axis=1)
    wide['reference_usable']=~wide.airport_id.eq('KDEN*')
    wide['landscape_year']=wide.year;wide['environment_timing']='same_year_retrospective';wide['is_den']=wide.airport_id.eq('KDEN')
    wide.to_parquet(output/'airport_year_environment.parquet',index=False)
    lag=wide[wide.year<=2024].copy();lag['year']=lag.year+1;lag['environment_timing']='previous_year_product_retroactively_available';lag.to_parquet(output/'airport_year_environment_lag1.parquet',index=False)


    require(not wide.duplicated(['airport_id','year']).any(),'Duplicate panel key.')
    require((lag.year-lag.landscape_year).eq(1).all(),'Invalid previous-year alignment.')
    require(wide.loc[wide.year.eq(2015),[c for c in wide if 'delta' in c]].isna().all().all(),'Unexpected first-year change.')
    return {'airports':int(wide.airport_id.nunique()),'airport_year_rows':len(wide),'columns':len(wide.columns),'lagged_rows':len(lag),'zonal_rows':len(env),'change_rows':len(ch),'complete_years':YEARS,'new_model_fits':0,'raw_raster_extraction':False}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--inputs',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
    manifest=Path(args.inputs).resolve(strict=True);config=json.loads(manifest.read_text(encoding='utf-8'))
    paths={k:(manifest.parent/Path(v)).resolve(strict=True) for k,v in config['paths'].items()}
    output=prepare_output(args.output,{'bindings':manifest,**paths},['results','logs'])
    try:
        env=pd.read_parquet(paths['zone_environment']);st=pd.read_csv(paths['structure']);tr=pd.read_csv(paths['transitions']);points=pd.read_csv(paths['airport_reference'])
        validate(env,st,tr,points)
        summary=reconstruct(env,st,tr,points,output/'results')
        (output/'results/environment_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
        print(json.dumps(summary),flush=True)
    except Exception:
        (output/'logs/failure.txt').write_text(traceback.format_exc(),encoding='utf-8');raise
if __name__=='__main__':main()
