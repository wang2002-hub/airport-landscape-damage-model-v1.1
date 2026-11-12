from pathlib import Path
import json,hashlib
import numpy as np,pandas as pd

def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding="utf-8")
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def run(paths,O):
    sources=[paths["calibration_reference"],paths["membership_reference"]]
    saved=pd.read_csv(sources[0]);membership=pd.read_csv(sources[1]);checks=[];rows=[];gapdraw=[];overall=[];manifest={role:sha(p) for role,p in paths.items()}
    for label,files in [('geographic',[paths[f'geographic_predictions_{k}'] for k in range(1,6)]),('temporal_test',[paths['temporal_predictions']])]:
     frames=[]
     for p in files:
      frames.append(pd.read_parquet(p))
     raw=pd.concat(frames,ignore_index=True);raw=raw[raw.dataset=='national'].copy()
     assert not raw.event_id.duplicated().any()
     g=raw.assign(loss=(raw.damage_binary-raw.p_calibrated)**2).groupby('airport_id').agg(n=('event_id','size'),O=('damage_binary','sum'),E=('p_calibrated','sum'),loss=('loss','sum'))
     g['band']=pd.qcut(g.n,10,duplicates='drop');old=membership[membership.evaluation==label].set_index('airport_id').sort_index()
     assert set(old.index)==set(g.index)
     assert np.allclose(old[['n','O','E','loss']].to_numpy(dtype=float),g[['n','O','E','loss']].to_numpy(dtype=float),atol=1e-11)
     assert old.band.tolist()==g.band.astype(str).tolist()
     checks.append(label+': event-level aggregation and tie-preserving membership reproduced')
     for weight in ['airport_equal','report_weighted']:
      obs=(g.O/g.n).mean() if weight=='airport_equal' else g.O.sum()/g.n.sum()
      pred=(g.E/g.n).mean() if weight=='airport_equal' else g.E.sum()/g.n.sum()
      loss=(g.loss/g.n).mean() if weight=='airport_equal' else g.loss.sum()/g.n.sum()
      overall.append(dict(evaluation=label,weighting=weight,airports=len(g),reports=int(g.n.sum()),damage=int(g.O.sum()),observed=obs,predicted=pred,gap=obs-pred,brier=loss))
     rng=np.random.default_rng(20261105)
     for band,h in g.groupby('band',observed=True):
      n=h.n.to_numpy(dtype=float);o=h.O.to_numpy(dtype=float);e=h.E.to_numpy(dtype=float);G=len(h);idx=rng.integers(0,G,(2000,G))
      for weight in ['airport_equal','report_weighted']:
       s=saved[(saved.evaluation==label)&(saved.band==str(band))&(saved.weighting==weight)].iloc[0]
       if weight=='airport_equal':bo=(o/n)[idx].mean(1);bp=(e/n)[idx].mean(1)
       else:bo=o[idx].sum(1)/n[idx].sum(1);bp=e[idx].sum(1)/n[idx].sum(1)
       assert np.allclose(np.quantile(bo,[.025,.975]),[s.observed_low,s.observed_high],atol=1e-12)
       assert np.allclose(np.quantile(bp,[.025,.975]),[s.predicted_low,s.predicted_high],atol=1e-12)
       gap=bo-bp;row=s.to_dict();row.update(gap=s.observed-s.predicted,gap_low=np.quantile(gap,.025),gap_high=np.quantile(gap,.975))
       rows.append(row)
       gapdraw.extend(dict(evaluation=label,band=str(band),weighting=weight,replicate=j+1,gap=v) for j,v in enumerate(gap))
     checks.append(label+': all original marginal intervals replayed exactly')
    pd.DataFrame(rows).to_csv(O/'calibration_with_paired_gaps.csv',index=False)
    pd.DataFrame(gapdraw).to_csv(O/'paired_gap_draws.csv.gz',index=False,compression='gzip')
    pd.DataFrame(overall).to_csv(O/'overall_weighting.csv',index=False)
    save(O/'source_manifest.json',manifest);save(O/'analysis_verification.json',{'passed':True,'checks':checks,'new_model_fits':0,'resamples_per_band':2000,'new_independent_random_sequences':0})
    print(pd.DataFrame(overall).to_string(index=False))
    print(pd.DataFrame(rows).query('min_reports==1')[['evaluation','weighting','gap','gap_low','gap_high']].to_string(index=False))


if __name__=="__main__":
    from input_config import execute
    execute(run,['calibration_reference', 'membership_reference', 'geographic_predictions_1', 'geographic_predictions_2', 'geographic_predictions_3', 'geographic_predictions_4', 'geographic_predictions_5', 'temporal_predictions'])
