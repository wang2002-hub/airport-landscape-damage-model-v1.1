"""Log-scale simultaneous intervals for the sixteen airport-by-subtype O/E ratios
(round-4 items I2 and m1).

Input  : extent_joint_draws.csv.gz written by components/documentation_partition/
         analyze_partition.py, and the bundled
         supporting_data/extent_partition/extent_decomposition_points.csv
         (optionally extent_simultaneous_intervals.csv for comparison).
Output : extent_simultaneous_intervals_log.csv  (log-scale family, continuity c = 0.5)
         zero_draw_counts.csv                    (draws with O = 0 per airport/subtype; item m1)
         natural_vs_log_comparison.csv           (side by side with the natural-scale family)
Method : x = log((O + c) / (E + c)) per draw; centred on the fitted point
         log((O0 + c)/(E0 + c)); scale = draw SD; critical value = 95% quantile of the
         maximum |t| over the 16 ratios (the max-statistic logic used for the absolute and
         relative families in analyze_partition.py). Interval = exp(x0 +/- crit * sd).
Usage  : python log_scale_subtype_intervals.py --draws extent_joint_draws.csv.gz \
             --points extent_decomposition_points.csv --natural extent_simultaneous_intervals.csv --output NEW_DIR
"""
import argparse
from pathlib import Path
import numpy as np, pandas as pd

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--draws', type=Path, required=True); ap.add_argument('--points', type=Path, required=True)
ap.add_argument('--natural', type=Path); ap.add_argument('--output', type=Path, required=True)
ap.add_argument('--c', type=float, default=0.5)
a = ap.parse_args()
if a.output.exists(): ap.error('choose a new output directory')
a.output.mkdir(parents=True)

v = pd.read_csv(a.draws); v = v[(v.scheme == 'year') & (v.airport != 'Pooled')]
pt = pd.read_csv(a.points).query("scheme=='year' and airport!='Pooled'").set_index('airport')
airports = ['KDEN', 'KJFK', 'KMIA', 'KMSP', 'KBOS', 'KSFO', 'KSAT', 'KSTL']
family = [(ap_, s) for s in ['undetermined', 'documented'] for ap_ in airports]
cols, x0, zeros = [], [], []
for ap_, s in family:
    g = v[v.airport == ap_].sort_values(['replicate', 'sample'])
    cols.append(np.log((g['O_' + s].to_numpy() + a.c) / (g['E_' + s].to_numpy() + a.c)))
    x0.append(np.log((pt.loc[ap_, 'O_' + s] + a.c) / (pt.loc[ap_, 'E_' + s] + a.c)))
    zeros.append(dict(airport=ap_, subtype=s, draws=len(g), zero_draws=int((g['O_' + s] == 0).sum()),
                      zero_share=float((g['O_' + s] == 0).mean())))
X = np.column_stack(cols); x0 = np.array(x0); sd = X.std(axis=0, ddof=1)
assert X.shape[1] == 16 and len(X) == 9960, X.shape
crit = np.quantile(np.abs((X - x0) / sd).max(axis=1), .95)
out = pd.DataFrame([dict(airport=ap_, subtype=s, corrected_ratio=np.exp(x0[i]), log_sd=sd[i], critical=crit,
                         simultaneous_low=np.exp(x0[i] - crit * sd[i]), simultaneous_high=np.exp(x0[i] + crit * sd[i]),
                         raw_OE=pt.loc[ap_, 'O_' + s] / pt.loc[ap_, 'E_' + s]) for i, (ap_, s) in enumerate(family)])
out.to_csv(a.output / 'extent_simultaneous_intervals_log.csv', index=False)
pd.DataFrame(zeros).to_csv(a.output / 'zero_draw_counts.csv', index=False)
if a.natural:
    nat = pd.read_csv(a.natural); nat['subtype'] = nat.metric.str.replace('OE_', '')
    cmp_ = out.merge(nat[['airport', 'subtype', 'simultaneous_low', 'simultaneous_high', 'critical']],
                     on=['airport', 'subtype'], suffixes=('_log', '_natural'))
    cmp_['both_include_1'] = ((cmp_.simultaneous_low_log <= 1) & (cmp_.simultaneous_high_log >= 1) &
                             (cmp_.simultaneous_low_natural <= 1) & (cmp_.simultaneous_high_natural >= 1))
    cmp_.to_csv(a.output / 'natural_vs_log_comparison.csv', index=False)
    print(cmp_.round(3).to_string(index=False))
print('critical', round(crit, 4)); print(pd.DataFrame(zeros).to_string(index=False))
