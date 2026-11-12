"""Figure S8: conditional coding-model losses on matched damage reports.

Draws the two loss panels formerly shown as Figure S9B-C (v1.0 numbering) from the
saved benchmark table, with identical styling to
components/supplement_figures/draw_reporting_coding.py. The former panel A
(annual M? share) duplicated main-text Figure 2C and is omitted. No model is
evaluated again: the benchmark values were recomputed and checked against saved
predictions in draw_reporting_coding.py, which needs event-level inputs.
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


def main():
    a = parse(__doc__)
    P, hashes = resolve(a.config, ['coding_model_benchmarks'])
    out = a.output; out.mkdir(parents=True)
    scores = pd.read_csv(P['coding_model_benchmarks'])
    assert len(scores) == 6
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9, 'axes.titlesize': 10, 'pdf.fonttype': 42, 'svg.fonttype': 'none'})
    fig = plt.figure(figsize=(6.5, 3.05))
    gs = fig.add_gridspec(1, 2, left=.18, right=.98, top=.88, bottom=.27, wspace=.35)
    models = ['calibrated_EB', 'uncalibrated_EB', 'constant_national_2023']; labels = ['Calibrated', 'Uncalibrated', '2023 constant']
    for k, (metric, title) in enumerate([('brier', 'A  Conditional coding Brier loss'), ('logloss', 'B  Conditional coding log loss')]):
        ax = fig.add_subplot(gs[0, k]); yy = np.arange(3)
        for offset, pop, color, label in [(-.14, 'national_test', '#236783', 'National test (n = 669)'), (.14, 'target_damaged', '#b34b35', 'Targets (n = 309)')]:
            z = scores[scores.population == pop].set_index('model').loc[models]
            ax.barh(yy + offset, z[metric], height=.24, color=color, label=label)
            for i, r in enumerate(z.itertuples()):
                ax.text(getattr(r, metric) + (.004 if metric == 'brier' else .012), i + offset, f'{getattr(r, metric):.3f}', va='center', fontsize=7)
        ax.set(yticks=yy, yticklabels=labels, xlabel='Loss in original units', title=title,
               xlim=(0, .33 if metric == 'brier' else 1.02), ylim=(2.5, -.5))
        ax.tick_params(axis='y', labelsize=8); ax.grid(axis='x', alpha=.12)
        if k == 1: ax.set_yticklabels([])
        if k == 0: handles, legendlabels = ax.get_legend_handles_labels()
    fig.legend(handles, legendlabels, loc='lower center', bbox_to_anchor=(.5, .015), ncol=2, fontsize=8, frameon=False)
    stem = out / 'figS08_coding_losses'
    for ext in ['pdf', 'svg', 'png', 'tiff']:
        kw = {'dpi': 600}
        if ext == 'tiff': kw['pil_kwargs'] = {'compression': 'tiff_lzw'}
        fig.savefig(stem.with_suffix('.' + ext), **kw)
    fig.savefig(out / 'figS08_coding_losses_preview.png', dpi=160); plt.close(fig)
    scores.to_csv(out / 'figS08_plotted_values.csv', index=False)
    (out / 'figS08_build.json').write_text(json.dumps({'inputs_sha256': hashes, 'new_model_fits': 0}, indent=2))
    print('Exported Figure S8 (coding losses).')


if __name__ == '__main__':
    main()
