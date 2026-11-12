"""Retrospective damage-extent benchmarks and paired airport-profile diagnostics."""
from pathlib import Path
import argparse, json, sys, hashlib, time, traceback
from datetime import datetime, timezone

def run(paths, bootstrap, out):
    import numpy as np
    import pandas as pd
    start = time.perf_counter()
    out.mkdir(parents=True, exist_ok=True)
    manifest = []
    def read(role):
        p = paths[role]
        manifest.append({'role': role, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()})
        return pd.read_parquet(p) if p.suffix == '.parquet' else pd.read_csv(p)
    a = ['KDEN','KJFK','KMIA','KMSP','KBOS','KSFO','KSAT','KSTL']
    years = np.arange(2015,2026)
    d = read('events')
    d['u'] = d.DAMAGE_LEVEL.eq('M?').astype(int)
    d['SOURCE'] = d.SOURCE.astype('string').str.strip().fillna('Missing')
    nat = d[~d.target].copy()
    assert len(nat)==46167 and int(nat.damage_binary.sum())==3096
    temporal = read('temporal_predictions')
    tar = temporal[temporal.dataset.eq('target')].merge(
        d[['event_id','DAMAGE_LEVEL','u','SOURCE']],on='event_id',validate='one_to_one')
    assert len(tar)==5936 and int(tar.u.sum())==252
    national_ids = sorted(nat.airport_id.unique())
    channels = sorted(set(nat.SOURCE)|set(tar.SOURCE))
    year_ix = {int(y):i for i,y in enumerate(years)}
    source_ix = {s:i for i,s in enumerate(channels)}
    # Counts retain whole airport histories, matching the original model bootstrap.
    totals = np.zeros((len(national_ids),11,len(channels),2), dtype=float)
    id_ix = {s:i for i,s in enumerate(national_ids)}
    damaged = nat[nat.damage_binary.eq(1)]
    for (airport,year,source),g in damaged.groupby(['airport_id','year','SOURCE']):
        totals[id_ix[airport],year_ix[year],source_ix[source]] = [len(g),g.u.sum()]
    annual = []
    for pop,v in [('National',nat),('Eight targets',d[d.target])]:
        for y,g in v.groupby('year'):
            o=int(g.damage_binary.sum());u=int(g.u.sum())
            annual.append(dict(population=pop,year=y,reports=len(g),damage=o,
                               undetermined=u,documented=o-u,q=u/o))
    pd.DataFrame(annual).to_csv(out/'annual_damage_extent.csv',index=False)
    ti=np.array([year_ix[y] for y in tar.year]);ci=np.array([source_ix[s] for s in tar.SOURCE])
    ai=np.array([a.index(s) for s in tar.airport_id]);flat=ai*11+ti
    def proportions(counts, scheme):
        yr=counts.sum(axis=1);overall=yr[:,1].sum()/yr[:,0].sum()
        qy=np.divide(yr[:,1],yr[:,0],out=np.full(11,overall),where=yr[:,0]>0)
        if scheme=='constant':return np.full(len(tar),overall),0
        if scheme=='year':return qy[ti],int((yr[ti,0]==0).sum())
        cells=counts[ti,ci];q=np.divide(cells[:,1],cells[:,0],out=qy[ti].copy(),where=cells[:,0]>0)
        return q,int((cells[:,0]==0).sum())
    def group_target(p,q):
        values=[np.ones(len(tar)),tar.damage_binary.to_numpy(),p,
                tar.u.to_numpy(),p*q,tar.damage_binary.to_numpy()-tar.u.to_numpy(),p*(1-q)]
        return np.stack([np.bincount(flat,weights=x,minlength=88).reshape(8,11) for x in values],axis=-1)
    cols=['n','O','E','O_undetermined','E_undetermined','O_documented','E_documented']
    base={};points=[];all_counts=totals.sum(axis=0)
    for scheme in ['year','year_source','constant']:
        q,fallback=proportions(all_counts,scheme);g=group_target(tar.p_calibrated.to_numpy(),q).sum(axis=1)
        g=np.vstack([g,g.sum(axis=0)]);base[scheme]=g
        for label,x in zip(a+['Pooled'],g):
            row=dict(scheme=scheme,airport=label,**dict(zip(cols,x)),fallback_target_reports=fallback)
            for s in ['undetermined','documented']:
                row['OE_'+s]=row['O_'+s]/row['E_'+s]
                row['difference_'+s]=row['O_'+s]-row['E_'+s]
            row['OE']=row['O']/row['E'];points.append(row)
    point=pd.DataFrame(points)
    point.to_csv(out/'extent_decomposition_points.csv',index=False)
    protocol_path=paths['analysis_protocol']
    seed=json.loads(protocol_path.read_text())['seed']
    manifest.append({'role':'analysis_protocol','sha256':hashlib.sha256(protocol_path.read_bytes()).hexdigest()})
    draws=[];fallbacks=[];failed=[];prediction_hashes=[]
    for rep in range(500):
        meta_path=bootstrap[rep]['metadata']
        meta=json.loads(meta_path.read_text())
        prediction_hashes.append({'replicate':rep,'metadata_sha256':hashlib.sha256(meta_path.read_bytes()).hexdigest(),'success':meta['success']})
        if not meta['success']:failed.append(rep);continue
        f=bootstrap[rep]['predictions']
        prediction_hashes[-1]['prediction_sha256']=hashlib.sha256(f.read_bytes()).hexdigest()
        z=np.load(f,allow_pickle=True);ix=pd.Index(z['event_id']).get_indexer(tar.event_id)
        assert ix.min()>=0 and len(set(ix))==5936
        p=z['p'][ix];assert np.isfinite(p).all() and ((p>0)&(p<1)).all()
        sampled=np.random.default_rng(seed+rep).choice(national_ids,len(national_ids),replace=True)
        weights=np.bincount([id_ix[s] for s in sampled],minlength=len(national_ids))
        counts=np.einsum('a,aysk->ysk',weights,totals)
        rng=np.random.default_rng(83720+rep)
        sequences=[rng.integers(0,11,11) for _ in range(20)]
        for scheme in ['year','year_source','constant']:
            q,fallback=proportions(counts,scheme)
            fallbacks.append(dict(replicate=rep,scheme=scheme,target_reports=fallback))
            g=group_target(p,q)
            for j,idx in enumerate(sequences):
                h=g[:,idx].sum(axis=1);h=np.vstack([h,h.sum(axis=0)])
                for label,x in zip(a+['Pooled'],h):
                    draws.append(dict(scheme=scheme,replicate=rep,sample=j,airport=label,**dict(zip(cols,x))))
        if rep%100==0:print('Completed saved replicate',rep,flush=True)
    assert failed==[224,336]
    v=pd.DataFrame(draws)
    assert np.allclose(v.E,v.E_undetermined+v.E_documented,atol=1e-10)
    assert np.array_equal(v.O,v.O_undetermined+v.O_documented)
    for s in ['undetermined','documented']:
        v['OE_'+s]=v['O_'+s]/v['E_'+s]
        v['difference_'+s]=v['O_'+s]-v['E_'+s]
    v['OE']=v.O/v.E
    old=read('joint_draw_reference')
    check=v[(v.scheme=='year')&(v.airport!='Pooled')].merge(old,on=['replicate','sample','airport'],validate='one_to_one')
    error=float(np.max(abs(check.OE-check.oe)));assert len(check)==79680 and error<1e-12
    v.to_csv(out/'extent_joint_draws.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    pd.DataFrame(fallbacks).to_csv(out/'coding_stratum_fallbacks.csv',index=False)
    intervals=[]
    for (scheme,airport),g in v.groupby(['scheme','airport']):
        pt=point[(point.scheme==scheme)&(point.airport==airport)].iloc[0]
        for metric in ['OE','OE_undetermined','OE_documented','difference_undetermined','difference_documented']:
            lo,hi=np.quantile(g[metric],[.025,.975])
            row=dict(scheme=scheme,airport=airport,metric=metric,estimate=pt[metric],low=lo,high=hi,draws=len(g),development_fits=g.replicate.nunique())
            for label,h in [('first',g[g.replicate<250]),('second',g[g.replicate>=250])]:
                row[label+'_low'],row[label+'_high']=np.quantile(h[metric],[.025,.975])
            intervals.append(row)
    pd.DataFrame(intervals).to_csv(out/'extent_decomposition_intervals.csv',index=False)
    # Relative airport contrasts preserve the shared pooled denominator.
    m=v[(v.scheme=='year')&(v.airport!='Pooled')].pivot(index=['replicate','sample'],columns='airport',values='OE')[a]
    pool=v[(v.scheme=='year')&(v.airport=='Pooled')].set_index(['replicate','sample']).OE
    x=np.log(m.div(pool,axis=0).to_numpy())
    pts=base['year'];theta=np.log((pts[:8,1]/pts[:8,2])/(pts[8,1]/pts[8,2]));se=x.std(axis=0,ddof=1)
    relative=[]
    for tag,center in [('fitted_estimate',theta),('bootstrap_mean',x.mean(axis=0))]:
        t=(x-center)/se;c=np.quantile(np.max(abs(t),axis=1),.95)
        p=(1+(abs(t)>=abs(theta/se)).sum(axis=0))/(len(x)+1)
        order=np.argsort(p);holm=np.empty(8);holm[order]=np.minimum(1,np.maximum.accumulate(p[order]*(8-np.arange(8))))
        for i,label in enumerate(a):
            lo,hi=np.quantile(np.exp(x[:,i]),[.025,.975])
            relative.append(dict(airport=label,centering=tag,estimate=np.exp(theta[i]),point_low=lo,point_high=hi,
                simultaneous_low=np.exp(theta[i]-c*se[i]),simultaneous_high=np.exp(theta[i]+c*se[i]),
                log_sd=se[i],critical=c,p_exploratory=p[i],holm_p=holm[i],draws=len(x)))
    pd.DataFrame(relative).to_csv(out/'relative_airport_simultaneous.csv',index=False)
    # Exploratory natural-scale family avoids undefined log ratios at zero subtype counts.
    family=[(airport,metric) for metric in ['OE_undetermined','OE_documented'] for airport in a]
    vv=v[(v.scheme=='year')&(v.airport!='Pooled')]
    pt=point[(point.scheme=='year')&(point.airport!='Pooled')].set_index('airport')
    xx=np.column_stack([vv.pivot(index=['replicate','sample'],columns='airport',values=metric)[airport]
                        for airport,metric in family])
    tt=np.array([pt.loc[airport,metric] for airport,metric in family]);ss=xx.std(axis=0,ddof=1)
    cc=np.quantile(abs((xx-tt)/ss).max(axis=1),.95)
    simultaneous=[dict(airport=airport,metric=metric,estimate=tt[i],simultaneous_low=max(0,tt[i]-cc*ss[i]),
                       simultaneous_high=tt[i]+cc*ss[i],critical=cc,sd=ss[i],family_size=16)
                  for i,(airport,metric) in enumerate(family)]
    pd.DataFrame(simultaneous).to_csv(out/'extent_simultaneous_intervals.csv',index=False)
    # National coding proportions never include the evaluated geographic fold.
    geo=pd.concat([read(f'geographic_predictions_{k}') for k in range(1,6)],ignore_index=True)
    geo=geo[geo.dataset=='national'].merge(nat[['event_id','u','SOURCE']],on='event_id',validate='one_to_one')
    assert len(geo)==46167 and not geo.event_id.duplicated().any()
    profiles=[];qtable=[]
    for fold,g in geo.groupby('spatial_fold'):
        train=geo[(geo.spatial_fold!=fold)&geo.damage_binary.eq(1)]
        yr=train.groupby('year').agg(O=('event_id','size'),u=('u','sum'))
        assert set(yr.index)==set(years)
        for y,r in yr.iterrows():qtable.append(dict(heldout_fold=fold,year=y,national_damage=r.O,national_undetermined=r.u,q=r.u/r.O))
        q=g.year.map(yr.u/yr.O).to_numpy();p=g.p_calibrated.to_numpy()
        for endpoint,obs,prob,mask in [
            ('any_damage',g.damage_binary.to_numpy(),p,np.ones(len(g),bool)),
            ('documented_damage',g.damage_binary.to_numpy()-g.u.to_numpy(),p*(1-q),np.ones(len(g),bool)),
            ('undetermined_damage',g.u.to_numpy(),p*q,np.ones(len(g),bool)),
            ('undetermined_given_damage',g.u.to_numpy(),q,g.damage_binary.eq(1).to_numpy())]:
            frame=pd.DataFrame({'airport':g.airport_id.to_numpy(),'o':obs,'p':prob,'v':prob*(1-prob)})[mask]
            for airport,h in frame.groupby('airport'):
                o=h.o.sum();e=h.p.sum();var=h.v.sum()
                profiles.append(dict(endpoint=endpoint,airport=airport,fold=fold,n=len(h),O=o,E=e,variance=var,OE=o/e,z=(o-e)/np.sqrt(var)))
    prof=pd.DataFrame(profiles);prof.to_csv(out/'national_extent_profiles.csv',index=False)
    pd.DataFrame(qtable).to_csv(out/'national_crossfit_coding_rates.csv',index=False)
    common=set(prof[prof.endpoint=='undetermined_given_damage'].airport)
    dispersion=[]
    for endpoint,g in prof.groupby('endpoint'):
        for subset,h in [('all_available',g),('damage_positive_airports',g[g.airport.isin(common)]),('endpoint_expected_ge5',g[g.E>=5])]:
            dispersion.append(dict(endpoint=endpoint,subset=subset,airports=len(h),reports=h.n.sum(),O=h.O.sum(),E=h.E.sum(),zero_outcomes=int(h.O.eq(0).sum()),pearson_mean=float(np.mean(h.z**2)),factor_max_one=max(1,float(np.mean(h.z**2))),median_z2=float(np.median(h.z**2))))
    pd.DataFrame(dispersion).to_csv(out/'national_extent_dispersion.csv',index=False)
    # Tie-preserving volume bands: never assign equal-sized airports to arbitrary bins.
    volume=[];membership=[]
    for label,frame in [('geographic',geo),('temporal_test',temporal[temporal.dataset=='national'])]:
        grouped=frame.assign(loss=(frame.damage_binary-frame.p_calibrated)**2).groupby('airport_id').agg(n=('event_id','size'),O=('damage_binary','sum'),E=('p_calibrated','sum'),loss=('loss','sum'))
        grouped['band']=pd.qcut(grouped.n,10,duplicates='drop')
        membership.append(grouped.reset_index().assign(evaluation=label))
        rng=np.random.default_rng(20261105)
        for band,g in grouped.groupby('band',observed=True):
            n=g.n.to_numpy();o=g.O.to_numpy();e=g.E.to_numpy();G=len(g)
            idx=rng.integers(0,G,(2000,G))
            for weight in ['airport_equal','report_weighted']:
                if weight=='airport_equal':
                    ob=(o/n).mean();pr=(e/n).mean();brier=(g.loss/g.n).mean();bo=(o/n)[idx].mean(axis=1);bp=(e/n)[idx].mean(axis=1)
                else:
                    ob=o.sum()/n.sum();pr=e.sum()/n.sum();brier=g.loss.sum()/g.n.sum();bo=o[idx].sum(axis=1)/n[idx].sum(axis=1);bp=e[idx].sum(axis=1)/n[idx].sum(axis=1)
                volume.append(dict(evaluation=label,band=str(band),min_reports=n.min(),max_reports=n.max(),airports=G,reports=n.sum(),damage=o.sum(),zero_damage_airports=int((o==0).sum()),weighting=weight,observed=ob,predicted=pr,brier=brier,observed_low=np.quantile(bo,.025),observed_high=np.quantile(bo,.975),predicted_low=np.quantile(bp,.025),predicted_high=np.quantile(bp,.975)))
    pd.DataFrame(volume).to_csv(out/'report_volume_calibration.csv',index=False)
    pd.concat(membership).to_csv(out/'report_volume_membership.csv',index=False)
    (out/'input_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    (out/'saved_fit_manifest.json').write_text(json.dumps(prediction_hashes,indent=2),encoding='utf-8')
    summary=dict(completed=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.perf_counter()-start,
        saved_development_fits=498,failed_attempts=failed,draws_per_fit=20,new_damage_model_fits=0,
        joint_total_replay_max_error=error,target_event_alignment='one-to-one',decomposition_identities='passed',
        nationwide_profile_count=1375,conditional_coding_airports=len(common),
        interpretation='Exploratory retrospective decomposition; annual coding proportions include later national years. No causal attribution to coding or reporting selection.')
    (out/'verification.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2),flush=True)
    print(pd.DataFrame(intervals).query("scheme=='year' and airport in ['KJFK','Pooled']").to_string(index=False))
    print(pd.DataFrame(relative).query("airport=='KJFK'").to_string(index=False))
    print(pd.DataFrame(dispersion).to_string(index=False))

def load_inputs(config_path):
    """Resolve explicit input roles and verify all file hashes before loading NPZ."""
    config=json.loads(config_path.read_text(encoding='utf-8'))
    def resolve(entry):
        p=Path(entry['path'])
        p=(config_path.parent/p).resolve() if not p.is_absolute() else p.resolve()
        if not p.is_file():raise FileNotFoundError(p)
        if hashlib.sha256(p.read_bytes()).hexdigest()!=entry['sha256']:
            raise ValueError('Input checksum mismatch: '+str(p))
        return p
    roles=['events','temporal_predictions','analysis_protocol','joint_draw_reference']
    roles += [f'geographic_predictions_{k}' for k in range(1,6)]
    if set(config['inputs'])!=set(roles):raise ValueError('Input role set differs')
    paths={k:resolve(v) for k,v in config['inputs'].items()}
    bootstrap={}
    for row in config['bootstrap']:
        rep=row['replicate']
        if rep in bootstrap:raise ValueError('Duplicate bootstrap attempt')
        metadata=resolve(row['metadata'])
        success=json.loads(metadata.read_text())['success']
        if success != ('predictions' in row):raise ValueError('Prediction availability differs from fit status')
        bootstrap[rep]={'metadata':metadata}
        if success:bootstrap[rep]['predictions']=resolve(row['predictions'])
    if set(bootstrap)!=set(range(500)):raise ValueError('Expected all 500 attempt records')
    return paths,bootstrap

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--config',type=Path,required=True,help='JSON input roles, file paths and SHA256 values')
    ap.add_argument('--output',type=Path,required=True,help='A new output directory')
    args=ap.parse_args()
    if args.output.exists():ap.error('Choose a new output directory to preserve prior runs.')
    try:
        paths,bootstrap=load_inputs(args.config.resolve())
        run(paths,bootstrap,args.output.resolve())
    except Exception:
        args.output.mkdir(parents=True,exist_ok=True)
        (args.output/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise
