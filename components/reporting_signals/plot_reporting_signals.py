"""Figure 2: reporting-system signals in national bird-strike damage records.

A, B  Airport-averaged observed minus predicted damage proportion by eligible-report
      group (hierarchical EBL; geographic validation and temporal test), with paired
      pointwise 95% airport-resampling intervals (Table S8).
C     M? share among damage reports by incident year, national source airports and
      the eight held-out airports (Table S21).
D     National damage reports per 100 eligible reports, split into undetermined
      (M?) and documented extent; the label gives the total (Table S21).
Saved aggregates only; no fitting or resampling.
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from signal_inputs import parse, resolve

ROLES = ['report_volume_calibration', 'annual_composition']
BLUE = '#266B8D'; INK = '#38454C'; PURPLE = '#77598B'; ORANGE = '#A9692A'; GUIDE = '#8B949B'


def label_band(r):
    lo, hi = int(r.min_reports), int(r.max_reports)
    return f'{lo:,}–{hi:,}' if lo != hi else f'{lo:,}'


def main():
    a = parse(__doc__)
    P, hashes = resolve(a.config, ROLES)
    out = a.output; out.mkdir(parents=True)
    plt.rcParams.update({'font.family': 'sans-serif', 'font.sans-serif': ['Arial', 'Liberation Sans', 'DejaVu Sans'],
                         'font.size': 7, 'axes.titlesize': 7.5, 'axes.labelsize': 7, 'xtick.labelsize': 6.5,
                         'ytick.labelsize': 6.5, 'legend.fontsize': 6.5, 'axes.spines.top': False,
                         'axes.spines.right': False, 'axes.linewidth': .7, 'legend.frameon': False,
                         'pdf.fonttype': 42, 'svg.fonttype': 'none', 'savefig.facecolor': 'white'})
    rv = pd.read_csv(P['report_volume_calibration']).query("weighting=='airport_equal'")
    comp = pd.read_csv(P['annual_composition'])
    nat = comp[comp.population == 'National'].set_index('year'); tgt = comp[comp.population != 'National'].set_index('year')
    assert len(rv) == 12 and nat.reports.sum() == 46167 and tgt.reports.sum() == 5936

    fig = plt.figure(figsize=(7.2, 5.6))
    gs = fig.add_gridspec(2, 2, left=.085, right=.985, top=.95, bottom=.085, hspace=.55, wspace=.22)
    axA = fig.add_subplot(gs[0, 0]); axB = fig.add_subplot(gs[0, 1], sharey=axA)
    axC = fig.add_subplot(gs[1, 0]); axD = fig.add_subplot(gs[1, 1])

    for ax, ev, title in [(axA, 'geographic', 'Geographic validation, 2015–2025'), (axB, 'temporal_test', 'Temporal test, 2024–2025')]:
        g = rv[rv.evaluation == ev].sort_values('min_reports')
        x = np.arange(len(g)); y = 100 * g.gap.to_numpy()
        lo = 100 * g.gap_low.to_numpy(); hi = 100 * g.gap_high.to_numpy()
        ax.axhline(0, color=GUIDE, lw=.8, ls='--', zorder=0)
        ax.errorbar(x, y, yerr=[y - lo, hi - y], fmt='o', color=BLUE, ms=4, capsize=2.2, lw=1)
        for xi, n, h in zip(x, g.airports, hi):
            ax.text(xi, h + .6, f'{int(n)}', ha='center', va='bottom', fontsize=5.8, color='0.35')
        ax.set_xticks(x, [label_band(r) for r in g.itertuples()])
        ax.set_xlabel('Eligible reports per airport'); ax.set_title(title, loc='left'); ax.margins(x=.06)
    axA.set_ylabel('Observed − predicted\ndamage proportion (pp)'); axA.set_ylim(-4, 16); axA.set_yticks([0, 5, 10, 15])
    plt.setp(axB.get_yticklabels(), visible=False)

    yrs = nat.index.to_numpy()
    axC.plot(yrs, 100 * nat.undetermined / nat.damage, '-o', color=INK, ms=3.5, lw=1.2, label='National source airports')
    axC.plot(yrs, 100 * tgt.undetermined / tgt.damage, '-s', color=PURPLE, ms=3, lw=1, label='Eight held-out airports')
    axC.set(ylim=(0, 105), xticks=yrs, xlabel='Incident year', ylabel='M? among damage reports (%)')
    axC.set_xticklabels([f"'{str(y)[2:]}" for y in yrs])
    axC.set_title('Undetermined-extent share of damage', loc='left'); axC.legend(loc='lower right'); axC.margins(x=.03)

    m = 100 * nat.undetermined / nat.reports; d = 100 * nat.documented / nat.reports; tot = m + d
    axD.bar(yrs, d, color=BLUE, width=.68, label='Documented extent')
    axD.bar(yrs, m, bottom=d, color=ORANGE, width=.68, label='Undetermined extent (M?)')
    for xi, v in zip(yrs, tot):
        axD.text(xi, v + .15, f'{v:.1f}', ha='center', va='bottom', fontsize=5.6, color='0.25')
    axD.set(ylim=(0, 9.5), xticks=yrs, xlabel='Incident year', ylabel='Damage reports per 100\neligible reports')
    axD.set_xticklabels([f"'{str(y)[2:]}" for y in yrs])
    axD.set_title('National damage by extent category', loc='left')
    h, l = axD.get_legend_handles_labels(); axD.legend(h[::-1], l[::-1], loc='upper right', ncol=1)
    for ax, letter in zip([axA, axB, axC, axD], 'ABCD'):
        ax.text(-.16 if ax in (axA, axC) else -.06, 1.06, letter, transform=ax.transAxes, fontsize=9, fontweight='bold', va='bottom')

    stem = out / 'fig02_reporting_signals'
    for ext, kw in [('png', {'dpi': 600}), ('tiff', {'dpi': 600, 'pil_kwargs': {'compression': 'tiff_lzw'}}), ('pdf', {}), ('svg', {})]:
        fig.savefig(stem.with_suffix('.' + ext), **kw)
    fig.savefig(out / 'fig02_reporting_signals_preview.png', dpi=200)
    plt.close(fig)
    values = pd.DataFrame({'year': yrs, 'national_reports': nat.reports.values, 'national_damage_per100': tot.values,
                           'national_undetermined_per100': m.values, 'national_documented_per100': d.values,
                           'national_Mq_share_pct': (100 * nat.undetermined / nat.damage).values,
                           'target_Mq_share_pct': (100 * tgt.undetermined / tgt.damage).values})
    values.to_csv(out / 'fig02_plotted_values.csv', index=False)
    rv.to_csv(out / 'fig02_report_volume_values.csv', index=False)
    (out / 'fig02_build.json').write_text(json.dumps({'inputs_sha256': hashes, 'new_model_fits': 0, 'new_random_draws': 0}, indent=2))
    print('Exported Figure 2 (reporting-system signals).')


if __name__ == '__main__':
    main()
