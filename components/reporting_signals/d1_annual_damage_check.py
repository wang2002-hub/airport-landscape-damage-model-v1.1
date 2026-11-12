"""Annual total, undetermined-extent (M?) and documented-extent damage proportions.

Reviewer item D1 asks whether the 2015-2017 rise in the M? share among damage
reports came with a rise in the total damage proportion. This script uses only
bundled aggregates: annual eligible-report and damage counts
(annual_composition.csv), cross-checked against the annual report denominators
in reporting_category_by_year.csv, and the frozen hierarchical EBL target
airport-year predictions (annual_influence_by_year.csv).

No model is fitted and nothing is resampled. Chi-square tests are descriptive
two-period contrasts, not trend or change-point tests, and they are not reported
in the manuscript.
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency
from signal_inputs import parse, resolve

ROLES = ['annual_composition', 'reporting_category_by_year', 'annual_influence_by_year', 'population_counts']


def main():
    a = parse(__doc__)
    paths, hashes = resolve(a.config, ROLES)
    out = a.output
    out.mkdir(parents=True)

    comp = pd.read_csv(paths['annual_composition'])
    comp['population'] = comp['population'].replace({'Eight targets': 'Targets'})
    assert set(comp.population) == {'National', 'Targets'} and len(comp) == 22
    assert (comp.undetermined + comp.documented == comp.damage).all()

    # Cross-check the annual denominators against the independent reporting file.
    rc = pd.read_csv(paths['reporting_category_by_year'])
    den = (rc[(rc.panel == 'final') & (rc.label == 'known') & (rc.field == 'SOURCE')]
           .groupby(['population', 'year']).population_n.first().reset_index())
    den['population'] = den.population.replace({'Eight targets': 'Targets'})
    chk = comp.merge(den, on=['population', 'year'], how='left', validate='one_to_one')
    assert (chk.reports == chk.population_n).all(), 'annual denominators disagree'

    pc = pd.read_csv(paths['population_counts']).set_index('population')
    for pop, key in [('National', 'National all'), ('Targets', 'Targets')]:
        g = comp[comp.population == pop]
        assert g.reports.sum() == pc.loc[key, 'n'] and g.damage.sum() == pc.loc[key, 'damage']

    t = comp.copy()
    t['damage_pct'] = 100 * t.damage / t.reports
    t['undetermined_per100'] = 100 * t.undetermined / t.reports
    t['documented_per100'] = 100 * t.documented / t.reports
    t['undetermined_share_of_damage_pct'] = 100 * t.undetermined / t.damage
    t = t.drop(columns=['q'])
    t.to_csv(out / 'annual_damage_composition.csv', index=False)

    nat = t[t.population == 'National'].set_index('year')
    d_u = nat.loc[2017, 'undetermined_per100'] - nat.loc[2015, 'undetermined_per100']
    d_d = nat.loc[2017, 'documented_per100'] - nat.loc[2015, 'documented_per100']
    d_t = nat.loc[2017, 'damage_pct'] - nat.loc[2015, 'damage_pct']
    change = dict(undetermined_change_pp=d_u, documented_change_pp=d_d, total_change_pp=d_t,
                  documented_offset_share_of_undetermined_rise=-d_d / d_u)

    def period(g, y0, y1):
        s = g.loc[y0:y1]
        return dict(period=f'{y0}-{y1}', reports=int(s.reports.sum()), damage=int(s.damage.sum()),
                    damage_pct=100 * s.damage.sum() / s.reports.sum(),
                    undetermined_per100=100 * s.undetermined.sum() / s.reports.sum(),
                    documented_per100=100 * s.documented.sum() / s.reports.sum())
    periods = pd.DataFrame([period(nat, 2015, 2016), period(nat, 2017, 2021), period(nat, 2022, 2025), period(nat, 2015, 2025)])
    periods.to_csv(out / 'national_period_summary.csv', index=False)

    rows = []
    def contrast(label, g1, g2):
        tab = np.array([[g1.damage.sum(), g1.reports.sum() - g1.damage.sum()],
                        [g2.damage.sum(), g2.reports.sum() - g2.damage.sum()]])
        chi2, p, _, _ = chi2_contingency(tab, correction=True)
        p1, p2 = tab[0, 0] / tab[0].sum(), tab[1, 0] / tab[1].sum()
        se = np.sqrt(p1 * (1 - p1) / tab[0].sum() + p2 * (1 - p2) / tab[1].sum())
        rows.append(dict(contrast=label, first_pct=100 * p1, second_pct=100 * p2, difference_pp=100 * (p2 - p1),
                         diff_low_pp=100 * (p2 - p1 - 1.96 * se), diff_high_pp=100 * (p2 - p1 + 1.96 * se),
                         chi2_yates=chi2, p_descriptive=p))
    for y in range(2015, 2025):
        contrast(f'{y} vs {y+1}', nat.loc[[y]], nat.loc[[y + 1]])
    contrast('2015-2016 vs 2017-2021', nat.loc[2015:2016], nat.loc[2017:2021])
    contrast('2017-2021 vs 2022-2025', nat.loc[2017:2021], nat.loc[2022:2025])
    pd.DataFrame(rows).to_csv(out / 'national_total_damage_contrasts.csv', index=False)

    # Evaluation-side sensitivity under the frozen hierarchical EBL predictions.
    ai = pd.read_csv(paths['annual_influence_by_year'])
    ai['E'] = ai.reports * ai.predicted_pct / 100
    assert ai.reports.sum() == 5936 and ai.damage.sum() == 309 and abs(ai.E.sum() - 275.6399) < 1e-3
    sens = []
    for label, keep in [('2015-2025', lambda y: y >= 2015), ('2017-2025 (exclude 2015-2016)', lambda y: y >= 2017),
                        ('2018-2025 (exclude 2015-2017)', lambda y: y >= 2018)]:
        s = ai[ai.year.map(keep)]
        for ap, g in list(s.groupby('airport')) + [('Pooled', s)]:
            sens.append(dict(years=label, airport=ap, reports=int(g.reports.sum()), O=int(g.damage.sum()),
                             E=g.E.sum(), OE=g.damage.sum() / g.E.sum()))
    sens = pd.DataFrame(sens)
    sens.to_csv(out / 'target_year_restriction_OE.csv', index=False)
    pooled = sens[sens.airport == 'Pooled'].set_index('years')

    tgt = t[t.population == 'Targets'].set_index('year')
    tgt_annual = ai.groupby('year').agg(reports=('reports', 'sum'), O=('damage', 'sum'), E=('E', 'sum'))
    tgt_annual['OE'] = tgt_annual.O / tgt_annual.E
    tgt_annual.to_csv(out / 'target_annual_OE.csv')
    assert (tgt_annual.O == tgt.damage).all()

    summary = dict(
        inputs_sha256=hashes,
        national_2015_2017=nat.loc[2015:2017, ['reports', 'damage', 'undetermined', 'documented', 'damage_pct',
                                                 'undetermined_per100', 'documented_per100']].round(4).to_dict('index'),
        change_2015_to_2017=change,
        total_damage_pct_range_2018_2021=[nat.loc[2018:2021, 'damage_pct'].min(), nat.loc[2018:2021, 'damage_pct'].max()],
        total_damage_pct_range_2022_2025=[nat.loc[2022:2025, 'damage_pct'].min(), nat.loc[2022:2025, 'damage_pct'].max()],
        pooled_target_OE=pooled[['O', 'E', 'OE']].round(4).to_dict('index'),
        model_year_term='Event block uses a single linear year term, (year - 2020) / 5 (components/analysis_core/model_core.py).',
        not_assessed=['national geographic calibration by year (geographic outer-test predictions not bundled)',
                      'categorical-year refit (event-level cohort not bundled)'],
        new_model_fits=0, new_random_draws=0)
    (out / 'd1_summary.json').write_text(json.dumps(summary, indent=2, default=float), encoding='utf-8')
    print(json.dumps({k: summary[k] for k in ['change_2015_to_2017', 'total_damage_pct_range_2018_2021',
                                               'total_damage_pct_range_2022_2025', 'pooled_target_OE']}, indent=1, default=float))


if __name__ == '__main__':
    main()
