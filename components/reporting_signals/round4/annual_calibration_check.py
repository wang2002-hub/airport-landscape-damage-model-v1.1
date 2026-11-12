"""National calibration by incident year (round-4 item I1).

Inputs : geographic_predictions_1..5.parquet (outer-test predictions, five folds) and,
         optionally, temporal_predictions.parquet. Columns used: event_id, airport_id,
         year, damage_binary, p_calibrated, dataset, model, family.
Output : annual_calibration.csv  one row per evaluation x year
         annual_calibration_summary.json
Method : O/E and observed-minus-predicted percentage by year for hierarchical EBL,
         with 2,000 airport-cluster bootstrap resamples within each year (predictions
         fixed). Calibration-in-the-large per year is the logit offset a solving
         sum(expit(logit(p) + a)) = O.
Usage  : python annual_calibration_check.py --geo DIR_WITH_FIVE_FILES [--temporal FILE] --output NEW_DIR
"""
import argparse, json
from pathlib import Path
import numpy as np, pandas as pd
from scipy.optimize import brentq
from scipy.special import expit, logit

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--geo', type=Path, required=True)
ap.add_argument('--temporal', type=Path)
ap.add_argument('--output', type=Path, required=True)
ap.add_argument('--model', default='EBL'); ap.add_argument('--family', default='glmm')
ap.add_argument('--boot', type=int, default=2000); ap.add_argument('--seed', type=int, default=20261112)
a = ap.parse_args()
if a.output.exists(): ap.error('choose a new output directory')
a.output.mkdir(parents=True)


def load(files):
    d = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    d = d[d.dataset == 'national']
    if 'model' in d: d = d[d.model == a.model]
    if 'family' in d: d = d[d.family == a.family]
    assert not d.event_id.duplicated().any(), 'duplicate events: check model/family filters'
    return d


def citl(y, p):
    lp = logit(np.clip(p, 1e-9, 1 - 1e-9)); O = y.sum()
    return brentq(lambda t: expit(lp + t).sum() - O, -10, 10)


sets = [('geographic', load(sorted(a.geo.glob('geographic_predictions_*.parquet'))))]
if a.temporal: sets.append(('temporal_test', load([a.temporal])))
rng = np.random.default_rng(a.seed); rows = []
for label, d in sets:
    for yr, g in d.groupby('year'):
        O, E, n = g.damage_binary.sum(), g.p_calibrated.sum(), len(g)
        by = g.groupby('airport_id').agg(O=('damage_binary', 'sum'), E=('p_calibrated', 'sum'), n=('event_id', 'size'))
        idx = rng.integers(0, len(by), size=(a.boot, len(by)))
        Ob, Eb, nb = by.O.to_numpy()[idx].sum(1), by.E.to_numpy()[idx].sum(1), by.n.to_numpy()[idx].sum(1)
        rows.append(dict(evaluation=label, year=yr, reports=n, airports=len(by), O=int(O), E=E, OE=O / E,
                         OE_low=np.quantile(Ob / Eb, .025), OE_high=np.quantile(Ob / Eb, .975),
                         gap_pp=100 * (O - E) / n, gap_low_pp=np.quantile(100 * (Ob - Eb) / nb, .025),
                         gap_high_pp=np.quantile(100 * (Ob - Eb) / nb, .975), citl=citl(g.damage_binary.to_numpy(), g.p_calibrated.to_numpy())))
res = pd.DataFrame(rows); res.to_csv(a.output / 'annual_calibration.csv', index=False)
geo = res[res.evaluation == 'geographic']
summary = dict(n_years=len(geo), years_interval_excludes_1=geo[(geo.OE_low > 1) | (geo.OE_high < 1)].year.tolist(),
               OE_2015_2016=float(geo[geo.year <= 2016].O.sum() / geo[geo.year <= 2016].E.sum()),
               OE_2017_2021=float(geo[geo.year.between(2017, 2021)].O.sum() / geo[geo.year.between(2017, 2021)].E.sum()),
               OE_2022_2025=float(geo[geo.year >= 2022].O.sum() / geo[geo.year >= 2022].E.sum()),
               note='Intervals are pointwise, airport-cluster, fixed predictions; not adjusted for 11 years.')
(a.output / 'annual_calibration_summary.json').write_text(json.dumps(summary, indent=2))
print(res.round(4).to_string(index=False)); print(json.dumps(summary, indent=2))
