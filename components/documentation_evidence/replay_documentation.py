"""Recompute documentation contrasts from saved aggregate counts and joint draws.

This verifies summaries conditional on the supplied predictions and draws. It
does not fit models, reconstruct the source cohort, or validate prospective use.
"""
from pathlib import Path
import argparse
import hashlib
import json
import platform
import time
import traceback

AIRPORTS = ['KDEN', 'KJFK', 'KMIA', 'KMSP', 'KBOS', 'KSFO', 'KSAT', 'KSTL']


def run(inputs, output):
    import numpy as np
    import pandas as pd
    start = time.perf_counter()
    output.mkdir(parents=True, exist_ok=True)
    checks = []
    hashes = {}

    def read(name):
        p = inputs / name
        hashes[name] = hashlib.sha256(p.read_bytes()).hexdigest()
        return pd.read_csv(p)

    def check(label, actual, expected, atol=1e-10):
        a, e = np.asarray(actual, dtype=float), np.asarray(expected, dtype=float)
        if a.shape != e.shape or not np.isfinite(a).all() or not np.isfinite(e).all():
            raise ValueError(label + ': shape or finite-value check failed')
        error = float(np.max(np.abs(a-e))) if a.size else 0.0
        if not np.allclose(a, e, rtol=1e-10, atol=atol):
            raise ValueError(f'{label}: maximum absolute error {error}')
        checks.append(dict(label=label, values=int(a.size), max_absolute_error=error))

    def compare(name, actual, keys):
        saved = read(name).sort_values(keys).reset_index(drop=True)
        actual = actual.sort_values(keys).reset_index(drop=True)
        if saved[keys].to_dict('records') != actual[keys].to_dict('records'):
            raise ValueError(name + ': keys differ')
        for col in actual.columns:
            if col not in keys:
                check(name + ':' + col, actual[col], saved[col])
        actual.to_csv(output/name, index=False)

    points = read('extent_decomposition_points.csv')
    draws = read('extent_joint_draws.csv.gz')
    if draws.duplicated(['scheme', 'replicate', 'sample', 'airport']).any():
        raise ValueError('Duplicate joint draw keys')
    if set(points.scheme) != {'year', 'year_source', 'constant'}:
        raise ValueError('Unexpected allocation schemes')
    for scheme, g in draws.groupby('scheme'):
        if len(g) != 9960*9 or set(g.airport) != set(AIRPORTS+['Pooled']):
            raise ValueError('Incomplete synchronized draw family')
        expected_keys = {(r, j) for r in range(500) if r not in {224, 336} for j in range(20)}
        for airport, h in g.groupby('airport'):
            if set(zip(h.replicate, h['sample'])) != expected_keys:
                raise ValueError('Unexpected successful-fit or year-resampling membership')
        summed = g[g.airport != 'Pooled'].groupby(['replicate', 'sample'])
        pool = g[g.airport == 'Pooled'].set_index(['replicate', 'sample']).sort_index()
        for col in ['n', 'O', 'E', 'O_undetermined', 'E_undetermined', 'O_documented', 'E_documented']:
            check(scheme+':pooled:'+col, summed[col].sum().sort_index(), pool[col])
    for label, frame in [('point', points), ('draw', draws)]:
        check(label+':partition O', frame.O, frame.O_undetermined+frame.O_documented)
        check(label+':partition E', frame.E, frame.E_undetermined+frame.E_documented)
        check(label+':OE', frame.OE, frame.O/frame.E)
        for subtype in ['undetermined', 'documented']:
            check(label+':OE_'+subtype, frame['OE_'+subtype], frame['O_'+subtype]/frame['E_'+subtype])
            check(label+':difference_'+subtype, frame['difference_'+subtype], frame['O_'+subtype]-frame['E_'+subtype])
    for scheme, g in points.groupby('scheme'):
        for col in ['n', 'O', 'E', 'O_undetermined', 'E_undetermined', 'O_documented', 'E_documented']:
            check(scheme+':point pooled:'+col, g[g.airport!='Pooled'][col].sum(), g[g.airport=='Pooled'][col].iloc[0])
    intervals = []
    for (scheme, airport), g in draws.groupby(['scheme', 'airport']):
        pt = points[(points.scheme == scheme) & (points.airport == airport)].iloc[0]
        for metric in ['OE', 'OE_undetermined', 'OE_documented', 'difference_undetermined', 'difference_documented']:
            lo, hi = np.quantile(g[metric], [.025, .975])
            row = dict(scheme=scheme, airport=airport, metric=metric, estimate=pt[metric], low=lo, high=hi,
                       draws=len(g), development_fits=g.replicate.nunique())
            for tag, h in [('first', g[g.replicate<250]), ('second', g[g.replicate>=250])]:
                row[tag+'_low'], row[tag+'_high'] = np.quantile(h[metric], [.025, .975])
            intervals.append(row)
    compare('extent_decomposition_intervals.csv', pd.DataFrame(intervals), ['scheme', 'airport', 'metric'])
    annual = draws[draws.scheme=='year']
    matrix = annual[annual.airport!='Pooled'].pivot(index=['replicate', 'sample'], columns='airport', values='OE')[AIRPORTS]
    pool = annual[annual.airport=='Pooled'].set_index(['replicate', 'sample']).OE
    x = np.log(matrix.div(pool, axis=0).to_numpy())
    pts = points[points.scheme=='year'].set_index('airport')
    theta = np.log(pts.loc[AIRPORTS, 'OE'].to_numpy()/pts.loc['Pooled', 'OE'])
    sd = x.std(axis=0, ddof=1)
    relative = []
    for tag, center in [('fitted_estimate', theta), ('bootstrap_mean', x.mean(axis=0))]:
        z = (x-center)/sd
        critical = np.quantile(np.abs(z).max(axis=1), .95)
        p = (1+(np.abs(z)>=np.abs(theta/sd)).sum(axis=0))/(len(x)+1)
        order = np.argsort(p)
        holm = np.empty(8)
        holm[order] = np.minimum(1, np.maximum.accumulate(p[order]*(8-np.arange(8))))
        for i, airport in enumerate(AIRPORTS):
            lo, hi = np.quantile(np.exp(x[:, i]), [.025, .975])
            relative.append(dict(airport=airport, centering=tag, estimate=np.exp(theta[i]), point_low=lo, point_high=hi,
                simultaneous_low=np.exp(theta[i]-critical*sd[i]), simultaneous_high=np.exp(theta[i]+critical*sd[i]),
                log_sd=sd[i], critical=critical, p_exploratory=p[i], holm_p=holm[i], draws=len(x)))
    compare('relative_airport_simultaneous.csv', pd.DataFrame(relative), ['centering', 'airport'])
    family = [(a, m) for m in ['OE_undetermined', 'OE_documented'] for a in AIRPORTS]
    local = annual[annual.airport!='Pooled']
    xx = np.column_stack([local.pivot(index=['replicate', 'sample'], columns='airport', values=m)[a] for a,m in family])
    tt = np.array([pts.loc[a,m] for a,m in family])
    ss = xx.std(axis=0, ddof=1)
    critical = np.quantile(np.abs((xx-tt)/ss).max(axis=1), .95)
    subtype = [dict(airport=a, metric=m, estimate=tt[i], simultaneous_low=max(0,tt[i]-critical*ss[i]),
        simultaneous_high=tt[i]+critical*ss[i], critical=critical, sd=ss[i], family_size=16) for i,(a,m) in enumerate(family)]
    compare('extent_simultaneous_intervals.csv', pd.DataFrame(subtype), ['metric', 'airport'])
    profiles = read('national_extent_profiles.csv')
    check('national OE', profiles.OE, profiles.O/profiles.E)
    check('national z', profiles.z, (profiles.O-profiles.E)/np.sqrt(profiles.variance))
    common = set(profiles[profiles.endpoint=='undetermined_given_damage'].airport)
    dispersion = []
    for endpoint,g in profiles.groupby('endpoint'):
        for label,h in [('all_available',g), ('damage_positive_airports',g[g.airport.isin(common)]), ('endpoint_expected_ge5',g[g.E>=5])]:
            value = float(np.mean(h.z**2))
            dispersion.append(dict(endpoint=endpoint, subset=label, airports=len(h), reports=h.n.sum(), O=h.O.sum(), E=h.E.sum(),
                zero_outcomes=int(h.O.eq(0).sum()), pearson_mean=value, factor_max_one=max(1,value), median_z2=float(np.median(h.z**2))))
    compare('national_extent_dispersion.csv', pd.DataFrame(dispersion), ['endpoint', 'subset'])
    result = dict(passed=True, verification_scope='Recalculation from saved aggregate profiles and joint draws; no event-level prediction or model-fit replay.',
        python=platform.python_version(), numpy=np.__version__, pandas=pd.__version__,
        checks=checks, input_sha256=hashes, point_rows=len(points), joint_draw_rows=len(draws),
        new_model_fits=0, new_random_draws=0, excluded_failed_attempts=[224,336], elapsed_seconds=time.perf_counter()-start)
    (output/'verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in {'checks','input_sha256'}}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, default=Path(__file__).resolve().parent/'inputs')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.inputs.resolve() == args.output.resolve():
        parser.error('Use a separate output directory to preserve the supplied evidence.')
    try:
        run(args.inputs.resolve(), args.output.resolve())
    except Exception:
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output/'failure.txt').write_text(traceback.format_exc(), encoding='utf-8')
        raise


if __name__ == '__main__':
    main()
