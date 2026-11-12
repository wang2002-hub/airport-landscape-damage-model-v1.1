"""Recalculate airport-level evidence using retained aggregate inputs only."""
from pathlib import Path
import argparse,csv,gzip,hashlib,json,math,statistics,sys,time,traceback

AIRPORTS=['KDEN','KJFK','KMIA','KMSP','KBOS','KSFO','KSAT','KSTL']

def quantile(values,p):
    v=sorted(values);pos=(len(v)-1)*p;i=int(pos)
    return v[i]+(pos-i)*(v[min(i+1,len(v)-1)]-v[i])

def read(root,name):
    p=root/'inputs'/name;op=gzip.open if p.suffix=='.gz' else open
    with op(p,'rt',encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def verify_manifest(root):
    with (root/'manifest_sha256.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    names=set()
    for row in rows:
        name=row['path'];p=(root/name).resolve()
        if name in names or not p.is_relative_to(root):raise ValueError('Invalid manifest path: '+name)
        names.add(name)
        if not p.is_file():raise ValueError('Missing package file: '+name)
        if hashlib.sha256(p.read_bytes()).hexdigest()!=row['sha256']:raise ValueError('Checksum mismatch: '+name)
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p.name!='manifest_sha256.csv' and '__pycache__' not in p.parts}
    if actual!=names:raise ValueError('Manifest coverage differs from the package file inventory')
    return len(rows)

def run(root,out):
    start=time.perf_counter();verified=verify_manifest(root);checks=0;maximum_error=0.
    def same(x,y,label,atol=1e-10):
        nonlocal checks,maximum_error
        x=float(x);y=float(y)
        if not math.isfinite(x) or not math.isfinite(y) or not math.isclose(x,y,rel_tol=1e-10,abs_tol=atol):
            raise ValueError(f'{label}: calculated {x}, retained {y}')
        checks+=1;maximum_error=max(maximum_error,abs(x-y))
    points={r['airport']:r for r in read(root,'target_counts.csv')}
    if set(points)!=set(AIRPORTS):raise ValueError('Target set differs')
    pooled_n=sum(int(r['n']) for r in points.values());pooled_o=sum(int(r['O']) for r in points.values());pooled_e=math.fsum(float(r['E']) for r in points.values())
    pooled_point=pooled_o/pooled_e
    same(pooled_n,5936,'target reports');same(pooled_o,309,'target damage')
    draws=read(root,'joint_draws.csv.gz');groups={};values={a:{} for a in AIRPORTS};counts={}
    for r in draws:
        a=r['airport'];key=(int(r['replicate']),int(r['sample']))
        if a not in values or key in values[a]:raise ValueError('Duplicate draw or unexpected airport')
        bias=float(r['bias_pp']);d=float(r['observed_minus_expected']);p=float(r['predicted'])
        if bias==0:raise ValueError('Zero bias prevents count reconstruction from this archive schema')
        n=-100*d/bias;e=n*p;o=e+d
        same(n,round(n),'integer report count',1e-7);same(o,round(o),'integer outcome count',1e-7)
        if not (n>0 and 0<=o<=n and e>0):raise ValueError('Invalid reconstructed count')
        same(o/e,r['oe'],'draw O/E')
        values[a][key]=r;groups.setdefault(key,[]).append((o,e));counts.setdefault(key[0],set()).add(key[1])
    if len(draws)!=79680 or len(groups)!=9960 or len(counts)!=498 or any(len(s)!=20 for s in counts.values()):raise ValueError('Unexpected joint resampling dimensions')
    keys=sorted(groups)
    if any(len(g)!=8 for g in groups.values()) or any(set(v)!=set(keys) for v in values.values()):raise ValueError('Unsynchronized airport draws')
    pool={k:math.fsum(x[0] for x in groups[k])/math.fsum(x[1] for x in groups[k]) for k in keys}
    pooled={'n':pooled_n,'O':pooled_o,'E':pooled_e,'OE':pooled_point,'low':quantile(pool.values(),.025),'high':quantile(pool.values(),.975)}
    saved_pool=read(root,'pooled_targets.csv')[0]
    for k,v in pooled.items():same(v,saved_pool[k],'pooled '+k)
    point_intervals=read(root,'pointwise_intervals.csv')
    for r in point_intervals:
        a=r['airport'];field=r['measure'];samples=[float(values[a][k][field]) for k in keys]
        same(quantile(samples,.025),r['low'],'pointwise lower');same(quantile(samples,.975),r['high'],'pointwise upper')
        q=points[a];n=float(q['n']);o=float(q['O']);e=float(q['E'])
        estimate={'oe':o/e,'bias_pp':100*(e-o)/n,'predicted':e/n,'observed_minus_expected':o-e}[field]
        same(estimate,r['estimate'],'pointwise estimate')
    if len(point_intervals)!=32:raise ValueError('Pointwise interval row count differs')
    logs={a:[math.log(float(values[a][k]['oe'])) for k in keys] for a in AIRPORTS}
    theta={a:math.log(float(points[a]['OE'])) for a in AIRPORTS};sd={a:statistics.stdev(logs[a]) for a in AIRPORTS}
    saved={(r['airport'],r['centering']):r for r in read(root,'target_comparisons.csv')};computed=[]
    for centering in ['fitted_estimate','bootstrap_mean']:
        centers={a:theta[a] if centering=='fitted_estimate' else statistics.fmean(logs[a]) for a in AIRPORTS}
        z={a:[(x-centers[a])/sd[a] for x in logs[a]] for a in AIRPORTS}
        critical=quantile([max(abs(z[a][j]) for a in AIRPORTS) for j in range(len(keys))],.95)
        p={a:(1+sum(abs(v)>=abs(theta[a]/sd[a]) for v in z[a]))/(len(keys)+1) for a in AIRPORTS}
        holm={};running=0.
        for i,a in enumerate(sorted(AIRPORTS,key=lambda a:p[a])):
            running=max(running,p[a]*(8-i));holm[a]=min(1.,running)
        for a in AIRPORTS:
            rel=[math.exp(logs[a][j])/pool[k] for j,k in enumerate(keys)]
            row={'airport':a,'centering':centering,'OE':math.exp(theta[a]),'relative_to_pooled':math.exp(theta[a])/pooled_point,'relative_low':quantile(rel,.025),'relative_high':quantile(rel,.975),'max_stat_low':math.exp(theta[a]-critical*sd[a]),'max_stat_high':math.exp(theta[a]+critical*sd[a]),'bootstrap_p':p[a],'holm_p':holm[a],'critical':critical,'log_ratio_sd':sd[a]}
            for field,val in row.items():
                if field not in ['airport','centering']:same(val,saved[a,centering][field],field)
            computed.append(row)
    national=read(root,'national_airport_counts.csv');models={}
    for r in national:
        models.setdefault(r['model'],[]).append(r)
        same(float(r['O'])/float(r['E']),r['OE'],'national O/E')
        for label in ['95','998']:
            flag=float(r['O'])<float(r['lower_count_'+label])-1e-9 or float(r['O'])>float(r['upper_count_'+label])+1e-9
            same(flag,r['conditional_flag_'+label]=='True','national conditional flag')
    if len(models)!=5 or any(len(g)!=1375 for g in models.values()):raise ValueError('National model or airport count differs')
    for g in models.values():
        same(sum(int(r['n']) for r in g),46167,'national reports');same(sum(int(r['O']) for r in g),3096,'national outcomes')
    factors={}
    for r in read(root,'dispersion_factors.csv'):
        g=[x for x in models[r['model']] if r['estimation_set']=='all' or (float(x['E'])>=5 if r['estimation_set']=='expected_ge5' else int(x['n'])>=100)]
        phi=max(1.,statistics.fmean(float(x['z'])**2 for x in g));same(phi,r['phi'],'dispersion factor');factors[r['model'],r['estimation_set']]=phi
    def widened(r,est,label):
        e=float(r['E']);phi=factors[r['model'],est];lo=max(0.,e+math.sqrt(phi)*(min(float(r['lower_count_'+label]),e)-e));hi=min(float(r['n']),e+math.sqrt(phi)*(max(float(r['upper_count_'+label]),e)-e))
        return float(r['O'])<lo-1e-9 or float(r['O'])>hi+1e-9
    summaries=read(root,'national_profile_summary.csv')
    for r in summaries:
        g=[x for x in models[r['model']] if r['display_set']=='all' or (float(x['E'])>=5 if r['display_set']=='expected_ge5' else int(x['n'])>=100)]
        label=r['label'];calc={'airports':len(g),'reports':sum(int(x['n']) for x in g),'observed_damage':sum(int(x['O']) for x in g),'zero_outcomes':sum(int(x['O'])==0 for x in g),'conditional_flags':sum(x['conditional_flag_'+label]=='True' for x in g),'conditional_expected_flags':math.fsum(float(x['conditional_tail_'+label]) for x in g),'nominal_upper_bound':len(g)*(.05 if label=='95' else .002)}
        calc.update({'width_flags_phi_'+est:sum(widened(x,est,label) for x in g) for est in ['all','expected_ge5','reports_ge100']})
        for k,v in calc.items():same(v,r[k],'national summary '+k)
    common={x['airport'] for x in models['glmm_EBL'] if float(x['E'])>=5};overlap=read(root,'reference_overlap.csv')
    for r in overlap:
        sets=[]
        for m in [r['model_a'],r['model_b']]:
            s={x['airport'] for x in models[m] if (x['conditional_flag_998']=='True' if r['control']=='conditional' else widened(x,r['control'],'998'))}
            if r['population']!='all':s&=common
            sets.append(s)
        a,b=sets;union=a|b;inter=a&b
        for k,v in {'flags_a':len(a),'flags_b':len(b),'intersection':len(inter),'union':len(union)}.items():same(v,r[k],'overlap '+k)
        if union:same(len(inter)/len(union),r['jaccard'],'overlap Jaccard')
        elif r['jaccard'] not in ['', 'nan','NaN']:raise ValueError('Empty-union Jaccard must remain undefined')
    decomposition=read(root,'damage_composition.csv');extent=read(root,'extent_restriction.csv');missing=read(root,'missing_labels.csv')
    for r in decomposition:
        same(float(r['O_undetermined'])+float(r['O_documented']),r['O'],'subtype observed sum');same(float(r['E_undetermined'])+float(r['E_documented']),r['E'],'subtype expected sum')
        for part in ['undetermined','documented']:same(float(r['O_'+part])/float(r['E_'+part]),r['OE_'+part],'subtype ratio')
    for r in extent:
        same(float(r['full_n'])-float(r['restricted_n']),float(r['full_O'])-float(r['restricted_O']),'extent population change')
        for prefix,obs in [('full','full_O'),('frozen_restricted','restricted_O'),('refitted_restricted','restricted_O')]:same(float(r[obs])/float(r[prefix+'_E']),r[prefix+'_OE'],'extent ratio')
    for r in missing:
        n=float(r['all_near_n']);o=float(r['known_damage']);m=float(r['unknown_n'])
        same(n,float(r['known_n'])+m,'unknown-label denominator');same(o/n,r['lower_damage_proportion'],'unknown lower');same((o+m)/n,r['upper_damage_proportion'],'unknown upper')
        same((n*float(r['known_reference_mean'])-o)/m,r['hypothetical_missing_rate_for_same_proportion'],'hypothetical completion')
    def dump(name,rows):
        with (out/name).open('w',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    dump('pooled_recomputed.csv',[pooled]);dump('target_comparisons_recomputed.csv',computed)
    record={'status':'passed','manifest_files':verified,'numeric_checks':checks,'maximum_absolute_error':maximum_error,'joint_rows':len(draws),'successful_development_fits':498,'year_samples_per_fit':20,'synchronized_draws':len(groups),'pointwise_interval_rows':len(point_intervals),'simultaneous_rows':len(computed),'national_airport_model_rows':len(national),'national_summary_rows':len(summaries),'reference_overlap_rows':len(overlap),'common_airport_subset':len(common),'damage_composition_rows':len(decomposition),'extent_rows':len(extent),'missing_label_rows':len(missing),'pooled':pooled,'new_model_fits':0,'new_random_draws':0,'elapsed_seconds':time.perf_counter()-start,'python':sys.version,'scope':'Aggregate arithmetic and saved-draw replay. Does not refit models or reconstruct raw reports, event-level losses, ranks or conditional probability mass functions.'}
    (out/'verification.json').write_text(json.dumps(record,indent=2),encoding='utf-8');return record

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
    root=Path(__file__).resolve().parent;out=args.output.resolve()
    if out==root or out.is_relative_to(root):parser.error('Choose an output directory outside this package')
    out.mkdir(parents=True,exist_ok=True)
    try:record=run(root,out)
    except Exception:
        (out/'failure.json').write_text(json.dumps({'status':'failed','traceback':traceback.format_exc()},indent=2),encoding='utf-8');raise
    print(json.dumps(record,indent=2))

if __name__=='__main__':main()
