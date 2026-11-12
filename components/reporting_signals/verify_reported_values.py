"""Check headline values reported in the manuscript against bundled aggregate files.

Each row records the value as printed, the recomputed value, the source file and
whether the recomputed value rounds to the printed value. Values derived from a
rounded published ratio (e.g. mean predictions from O/E to three decimals) are
flagged 'derived' and checked against the rounding interval of that ratio.
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import pandas as pd
from signal_inputs import parse, resolve

ROLES = ['population_counts', 'national_performance', 'national_extent_dispersion', 'national_summary', 'national_profiles',
         'target_absolute', 'target_relative', 'extent_points', 'extent_intervals', 'extent_simultaneous',
         'report_volume_calibration', 'annual_composition', 'coding_model_benchmarks', 'period_model_scores',
         'coding_standardization', 'airport_comparisons']


def main():
    a = parse(__doc__)
    P, hashes = resolve(a.config, ROLES)
    out = a.output; out.mkdir(parents=True)
    rows = []

    def add(item, location, printed, value, source, decimals=None, kind='exact', lo=None, hi=None):
        if kind == 'derived':
            d = len(str(printed).split('.')[1])
            ok = round(lo, d) <= float(printed) <= round(hi, d)
            shown = f'{lo:.4f}–{hi:.4f}'
        else:
            d = decimals if decimals is not None else (len(str(printed).split('.')[1]) if '.' in str(printed) else 0)
            ok = round(float(value), d) == round(float(printed), d)
            shown = f'{float(value):.6g}'
        rows.append(dict(item=item, manuscript_location=location, printed=printed, recomputed=shown,
                         source=source, check=kind, status='match' if ok else 'MISMATCH'))

    pc = pd.read_csv(P['population_counts']).set_index('population')
    add('Eligible reports, national source', '2.2; Fig. 1', 46167, pc.loc['National all', 'n'], 'population_counts.csv')
    add('Damage outcomes, national source', '2.2; Fig. 1', 3096, pc.loc['National all', 'damage'], 'population_counts.csv')
    add('Eligible reports, eight targets', '2.2; Fig. 1', 5936, pc.loc['Targets', 'n'], 'population_counts.csv')
    add('Damage outcomes, eight targets', '2.2; Fig. 1', 309, pc.loc['Targets', 'damage'], 'population_counts.csv')
    geo_obs = 100 * pc.loc['National all', 'damage'] / pc.loc['National all', 'n']
    tmp_obs = 100 * pc.loc['Test', 'damage'] / pc.loc['Test', 'n']
    add('Geographic observed damage (%)', '4.1', 6.71, geo_obs, 'population_counts.csv')
    add('Temporal-test observed damage (%)', '4.1', 6.01, tmp_obs, 'population_counts.csv')
    npf = pd.read_csv(P['national_performance'])
    for ev, obs, printed in [('Geographic', geo_obs, 6.66), ('Temporal', tmp_obs, 6.17)]:
        oe = npf[(npf.Evaluation == ev) & (npf.Family == 'Hierarchical') & (npf.Block == 'EBL')]['O/E'].iloc[0]
        add(f'{ev} mean hierarchical EBL prediction (%)', '4.1', printed, obs / oe, 'national_performance.csv (O/E 3 d.p.)',
            kind='derived', lo=obs / (oe + 0.0005), hi=obs / (oe - 0.0005))

    disp = pd.read_csv(P['national_extent_dispersion']).set_index(['endpoint', 'subset'])
    add('Dispersion factor, any damage', 'Abstract; 4.5', 1.68, disp.loc[('any_damage', 'all_available'), 'pearson_mean'], 'national_extent_dispersion.csv')
    add('Dispersion factor, documented extent', 'Abstract; 4.5', 1.78, disp.loc[('documented_damage', 'all_available'), 'pearson_mean'], 'national_extent_dispersion.csv')
    add('Dispersion factor, conditional M?', '4.5', 1.08, disp.loc[('undetermined_given_damage', 'all_available'), 'pearson_mean'], 'national_extent_dispersion.csv')
    add('Damage-positive airports (conditional M?)', '4.5', 773, disp.loc[('undetermined_given_damage', 'all_available'), 'airports'], 'national_extent_dispersion.csv')
    add('Widening factor (Fig. 3B)', 'Fig. 3', 1.676, disp.loc[('any_damage', 'all_available'), 'pearson_mean'], 'national_extent_dispersion.csv')

    ns = pd.read_csv(P['national_summary']).query("display_set=='all' and label==998").iloc[0]
    add('Conditional 99.8% flags', '4.2', 6, ns.conditional_flags, 'national_summary.csv')
    add('Flags after widening (all airports)', '4.2', 2, ns.width_flags_phi_all, 'national_summary.csv')
    prof = pd.read_csv(P['national_profiles'])
    add('Airports with E >= 5', '4.2; Fig. 3', 144, (prof.E >= 5).sum(), 'national_profiles.csv')
    add('Zero-damage national airports', '4.2', 602, (prof.O == 0).sum(), 'national_profiles.csv')

    ta = pd.read_csv(P['target_absolute']).set_index('Airport')
    ac_ = pd.read_csv(P['airport_comparisons']).set_index('airport').loc['JFK']
    add('JFK observed damage', '4.3', 65, ac_.observed, 'airport_comparisons.csv')
    add('JFK expected damage', '4.3', 44.80, ac_.expected, 'airport_comparisons.csv')
    add('JFK O/E', '4.3', 1.45, ac_.absolute, 'airport_comparisons.csv')
    add('JFK pointwise lower', '4.3', 1.06, ac_.absolute_point_low, 'airport_comparisons.csv')
    add('JFK pointwise upper', '4.3', 1.84, ac_.absolute_point_high, 'airport_comparisons.csv')
    add('JFK simultaneous lower', '4.3', 0.97, ac_.absolute_sim_low, 'airport_comparisons.csv')
    add('JFK simultaneous upper', '4.3', 2.18, ac_.absolute_sim_high, 'airport_comparisons.csv')
    add('JFK relative to pool', '4.3', 1.29, ac_.relative, 'airport_comparisons.csv')
    pooled = ta.loc['Pooled', 'O/E [pointwise 95% interval]']
    pv = [float(x) for x in pooled.replace('[', ' ').replace(']', ' ').replace(',', ' ').split()]
    add('Pooled O/E', 'Abstract; 4.3', 1.12, pv[0], 'target_absolute_counts_and_intervals.csv')
    add('Pooled O/E lower', 'Abstract; 4.3', 0.91, pv[1], 'target_absolute_counts_and_intervals.csv')
    add('Pooled O/E upper', 'Abstract; 4.3', 1.31, pv[2], 'target_absolute_counts_and_intervals.csv')
    tr = pd.read_csv(P['target_relative']).set_index('Airport').loc['JFK']
    lo, hi = [float(x) for x in tr['Primary simultaneous 95% interval'].split('–')]
    add('JFK relative simultaneous lower', '4.3; Fig. 4', 0.9979, lo, 'target_relative_comparisons.csv')
    add('JFK relative simultaneous upper', '4.3; Fig. 4', 1.6786, hi, 'target_relative_comparisons.csv')

    ep = pd.read_csv(P['extent_points']).query("scheme=='year'").set_index('airport')
    add('Pooled M? observed', '4.5', 252, ep.loc['Pooled', 'O_undetermined'], 'extent_decomposition_points.csv')
    add('Pooled documented observed', '4.5', 57, ep.loc['Pooled', 'O_documented'], 'extent_decomposition_points.csv')
    add('Pooled M? expected', '4.5', 206.4, ep.loc['Pooled', 'E_undetermined'], 'extent_decomposition_points.csv')
    add('Pooled documented expected', '4.5', 69.3, ep.loc['Pooled', 'E_documented'], 'extent_decomposition_points.csv')
    add('JFK M? expected (all 810 reports)', '4.5', 33.5, ep.loc['KJFK', 'E_undetermined'], 'extent_decomposition_points.csv')
    add('JFK documented expected', '4.5', 11.3, ep.loc['KJFK', 'E_documented'], 'extent_decomposition_points.csv')
    docs = ep.drop(index='Pooled').O_documented
    add('Smallest airport documented-extent count', '3.6', 4, docs.min(), 'extent_decomposition_points.csv')
    add('Largest airport documented-extent count', '3.6', 12, docs.max(), 'extent_decomposition_points.csv')
    ei = pd.read_csv(P['extent_intervals']).query("scheme=='year' and airport=='Pooled'").set_index('metric')
    for m, est, l, h in [('OE_undetermined', 1.22, 0.988, 1.440), ('OE_documented', 0.82, 0.481, 1.117)]:
        add(f'Pooled {m}', 'Abstract; 4.5', est, ei.loc[m, 'estimate'], 'extent_decomposition_intervals.csv')
        add(f'Pooled {m} lower', 'Abstract; 4.5', l, ei.loc[m, 'low'], 'extent_decomposition_intervals.csv', decimals=3)
        add(f'Pooled {m} upper', 'Abstract; 4.5', h, ei.loc[m, 'high'], 'extent_decomposition_intervals.csv', decimals=3)
    es = pd.read_csv(P['extent_simultaneous']).set_index(['airport', 'metric'])
    add('JFK M? O/E', '4.5', 1.73, es.loc[('KJFK', 'OE_undetermined'), 'estimate'], 'extent_simultaneous_intervals.csv')
    add('JFK documented O/E', '4.5', 0.62, es.loc[('KJFK', 'OE_documented'), 'estimate'], 'extent_simultaneous_intervals.csv')
    add('JFK M? simultaneous lower', '4.5', 0.920, es.loc[('KJFK', 'OE_undetermined'), 'simultaneous_low'], 'extent_simultaneous_intervals.csv', decimals=3)
    add('JFK M? simultaneous upper', '4.5', 2.541, es.loc[('KJFK', 'OE_undetermined'), 'simultaneous_high'], 'extent_simultaneous_intervals.csv', decimals=3)
    add('JFK documented simultaneous upper', '4.5', 1.267, es.loc[('KJFK', 'OE_documented'), 'simultaneous_high'], 'extent_simultaneous_intervals.csv', decimals=3)
    zero_lows = int((es.xs('OE_documented', level='metric').simultaneous_low == 0).sum())
    add('Documented-extent simultaneous lower limits truncated at zero', '3.6; Fig. 6', 7, zero_lows, 'extent_simultaneous_intervals.csv')

    cs = pd.read_csv(P['coding_standardization']).query("scheme=='year' and period=='2015-2025' and minimum_national_damaged==1").set_index('population')
    add('JFK M? expected among 65 damage reports', '4.5', 49.1, cs.loc['KJFK', 'expected_M'], 'reporting_coding_standardization.csv')

    rv = pd.read_csv(P['report_volume_calibration']).query("weighting=='airport_equal' and min_reports==1").set_index('evaluation')
    add('Geographic 1–2-report airports', '4.1; Fig. 2A', 688, rv.loc['geographic', 'airports'], 'report_volume_calibration.csv')
    add('Geographic 1–2-report observed (%)', '4.1', 33.1, 100 * rv.loc['geographic', 'observed'], 'report_volume_calibration.csv')
    add('Geographic 1–2-report predicted (%)', '4.1', 22.8, 100 * rv.loc['geographic', 'predicted'], 'report_volume_calibration.csv')
    add('Geographic 1–2-report gap (pp)', '4.1; Table S8', 10.31, 100 * rv.loc['geographic', 'gap'], 'report_volume_calibration.csv')
    add('Geographic gap lower (pp)', 'Table S8', 7.47, 100 * rv.loc['geographic', 'gap_low'], 'report_volume_calibration.csv')
    add('Geographic gap upper (pp)', 'Table S8', 13.27, 100 * rv.loc['geographic', 'gap_high'], 'report_volume_calibration.csv')
    add('Temporal 1–2-report airports', '4.1; Fig. 2B', 404, rv.loc['temporal_test', 'airports'], 'report_volume_calibration.csv')
    add('Temporal 1–2-report gap (pp)', 'Table S8', 5.69, 100 * rv.loc['temporal_test', 'gap'], 'report_volume_calibration.csv')

    ac = pd.read_csv(P['annual_composition']).query("population=='National'").set_index('year')
    for y, pr in [(2015, 32.2), (2016, 51.8), (2017, 76.1)]:
        add(f'National M? share of damage {y} (%)', '4.5; Fig. 2C', pr, 100 * ac.loc[y, 'q'], 'annual_composition.csv')
    later = 100 * ac.loc[2018:2025, 'q']
    add('Later-year M? share minimum (%)', '4.5', 77.3, later.min(), 'annual_composition.csv')
    add('Later-year M? share maximum (%)', '4.5', 87.0, later.max(), 'annual_composition.csv')
    add('National 2023 M? share (%)', '4.5', 82.2, 100 * ac.loc[2023, 'q'], 'annual_composition.csv')

    cb = pd.read_csv(P['coding_model_benchmarks']).set_index(['population', 'model'])
    add('Target coding Brier, uncalibrated', '4.5', 0.133, cb.loc[('target_damaged', 'uncalibrated_EB'), 'brier'], 'coding_model_benchmarks.csv')
    add('Target coding Brier, calibrated', '4.5', 0.268, cb.loc[('target_damaged', 'calibrated_EB'), 'brier'], 'coding_model_benchmarks.csv')
    add('Target coding Brier, 2023 constant', '4.5', 0.150, cb.loc[('target_damaged', 'constant_national_2023'), 'brier'], 'coding_model_benchmarks.csv')
    add('National test M? share (%)', '4.5', 82.4, 100 * 551 / cb.loc[('national_test', 'calibrated_EB'), 'n'], 'coding_model_benchmarks.csv')
    pm = pd.read_csv(P['period_model_scores']).query("population=='target_period' and period=='2015–2022'").set_index('model')
    add('2015–2022 target damage reports', '4.5', 195, pm.loc['calibrated_EB', 'n'], 'period_model_scores.csv')
    add('2015–2022 calibrated Brier', '4.5', 0.366, pm.loc['calibrated_EB', 'brier'], 'period_model_scores.csv')
    add('2015–2022 uncalibrated Brier', '4.5', 0.153, pm.loc['uncalibrated_EB', 'brier'], 'period_model_scores.csv')
    add('2015–2022 calibrated mean (%)', '4.5', 34.2, 100 * pm.loc['calibrated_EB', 'mean_prediction'], 'period_model_scores.csv')
    add('2015–2022 observed M? (%)', '4.5', 76.9, 100 * pm.loc['calibrated_EB', 'observed'], 'period_model_scores.csv')

    df = pd.DataFrame(rows)
    df.to_csv(out / 'manuscript_value_audit.csv', index=False)
    (out / 'manuscript_value_audit.json').write_text(json.dumps(dict(inputs_sha256=hashes, checked=len(df),
        matched=int((df.status == 'match').sum()), mismatches=df[df.status != 'match'].to_dict('records')), indent=2), encoding='utf-8')
    print(f'{(df.status == "match").sum()} of {len(df)} checked values match')
    if (df.status != 'match').any():
        print(df[df.status != 'match'].to_string())


if __name__ == '__main__':
    main()
