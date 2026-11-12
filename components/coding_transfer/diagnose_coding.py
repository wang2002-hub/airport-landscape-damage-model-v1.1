from pathlib import Path
import json,hashlib
import numpy as np,pandas as pd
from scipy.special import expit
from coding_encoder import Encoder

def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding="utf-8")
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def run(paths,O):
    sources=[paths[k] for k in ['events', 'coding_fit', 'benchmarks', 'annual_reference', 'annual_extent', 'target_predictions']]
    d=pd.read_parquet(sources[0]);fit=json.loads(sources[1].read_text());dam=d[d.damage_binary.eq(1)].copy();dam['u']=dam.DAMAGE_LEVEL.eq('M?').astype(int)
    annual=[]
    for target,label in [(False,'National'),(True,'Eight targets')]:
     for year,v in d[d.target.eq(target)].groupby('year'):
      damage=int(v.damage_binary.sum());u=int(v.DAMAGE_LEVEL.eq('M?').sum())
      annual.append(dict(population=label,year=int(year),reports=len(v),damage=damage,undetermined=u,documented=damage-u,q=u/damage))
    annual=pd.DataFrame(annual);old=pd.read_csv(sources[4]);pd.testing.assert_frame_equal(annual,old,check_dtype=False,atol=1e-12)
    annual.to_csv(O/'annual_composition.csv',index=False)
    tr=dam[(~dam.target)&(dam.year<=2022)].reset_index(drop=True);enc=Encoder(None,False,1).fit(tr)
    assert enc.metadata()==fit['encoder']
    beta=np.array(fit['beta']);cal=np.array(fit['calibrator']);baseline=236/287
    dam['raw']=expit(enc.transform(dam)@beta);dam['calibrated']=expit(cal[0]+cal[1]*(enc.transform(dam)@beta));dam['constant']=baseline
    saved=pd.read_parquet(sources[5]);match=dam[dam.target].merge(saved[['event_id','q_undetermined']],on='event_id',validate='one_to_one')
    assert len(match)==309 and np.allclose(match.calibrated,match.q_undetermined,atol=1e-12)
    rows=[]
    def score(v,label,period):
     y=v.u.to_numpy(dtype=float)
     for model,col in [('calibrated_EB','calibrated'),('uncalibrated_EB','raw'),('constant_national_2023','constant')]:
      p=v[col].to_numpy(dtype=float)
      rows.append(dict(population=label,period=period,model=model,n=len(v),undetermined=int(y.sum()),observed=float(y.mean()),expected=float(p.sum()),mean_prediction=float(p.mean()),brier=float(np.mean((y-p)**2)),logloss=float(-np.mean(y*np.log(p)+(1-y)*np.log1p(-p)))))
    score(dam[(~dam.target)&(dam.year>=2024)],'national_test','2024–2025');score(dam[dam.target],'target_damaged','2015–2025')
    for lo,hi in [(2015,2022),(2023,2023),(2024,2025)]:score(dam[dam.target&dam.year.between(lo,hi)],'target_period',str(lo) if lo==hi else f'{lo}–{hi}')
    scores=pd.DataFrame(rows);scores.to_csv(O/'period_model_scores.csv',index=False)
    original=pd.read_csv(sources[2]);replay=scores[scores.population!='target_period']
    check=replay.merge(original,on=['population','model'],suffixes=('_replay','_saved'),validate='one_to_one')
    for col in ['n','undetermined','expected','brier','logloss']:assert np.allclose(check[col+'_replay'],check[col+'_saved'],atol=1e-12)
    annualpred=[]
    for (target,year),v in dam.groupby(['target','year']):
     row={'population':'Eight targets' if target else 'National','year':int(year),'damage':len(v),'undetermined':int(v.u.sum()),'observed':float(v.u.mean())}
     for col in ['raw','calibrated','constant']:
      row[col+'_mean']=float(v[col].mean());row[col+'_brier']=float(((v.u-v[col])**2).mean())
     annualpred.append(row)
    pd.DataFrame(annualpred).to_csv(O/'annual_prediction_diagnostics.csv',index=False)
    save(O/'replay_verification.json',{'passed':True,'encoder_metadata_exact':True,'original_scores_replayed':6,'target_predictions_replayed':309,'annual_rows':22,'new_model_fits':0,'new_resamples':0,'calibrator_intercept':cal[0],'calibrator_slope':cal[1]})
    print(scores[['population','period','model','n','observed','mean_prediction','brier']].to_string(index=False))


if __name__=="__main__":
    from input_config import execute
    execute(run,['events', 'coding_fit', 'benchmarks', 'annual_reference', 'annual_extent', 'target_predictions'])
