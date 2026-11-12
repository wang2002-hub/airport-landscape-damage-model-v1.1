# Common-airport reference comparisons

Run `python compare_references.py --config analysis_inputs.json --output new-comparisons`.
Run `python plot_reference_comparison.py --config figure_inputs.json --output new-figures`.
Each output directory must be new. Input paths resolve against the config file.
The included inputs are aggregate airport profiles and reference comparisons.
All hashes are checked before use. No event-level records or paper text are included.

Five fixed references cover the same 1,375 national airports. The common display
subset contains 144 airports with hierarchical EBL expected damage at least five.
All references use that same subset. Highest-decile membership uses ceil(0.1*n)
and includes all ties at the cutoff. Every pair reports set sizes, intersection,
union and Jaccard overlap. Conditional flags retain the supplied exact limits.
The full 1,375-airport rank matrix remains in the numerical output.

Figure 4 pairs ordinary EB and hierarchical EBL ratios and shows all ten pairs
of highest-decile and conditional flag-set overlaps. Both log axes require
positive values. These are descriptive summaries of saved predictions, not
sampling intervals, calibration tests, or proof of airport safety equivalence.
No model fitting, new observations or random draws occur. Existing results were
viewed before this packaging verification.

The two supplied drawing inputs equal the corresponding analysis outputs.
To draw from regenerated outputs, change the figure config paths and retain or
recompute their SHA256 hashes after numerical verification. PDF and SVG retain
editable text; PNG and TIFF are exported at 600 dpi. The render-time alignment
audit writes its report before export. Final PDF collision and text audits belong
to release verification; successful rendering alone does not establish visual QA.
