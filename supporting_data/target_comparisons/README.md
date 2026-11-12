# Target comparison supporting data

These files preserve the displayed numerical summaries for eligible 2015–2025 reports at eight held-out airports. Values are retained from saved analysis outputs; they are not a new fit or a new bootstrap.

`target_absolute_counts_and_intervals.csv` duplicates the values in manuscript Table 2, panel A. `target_absolute_multiplicity.csv` retains both centering choices and their approximate and Holm-adjusted probabilities. `target_relative_comparisons.csv` contains the separate eight-airport relative family. `jfk_centering_and_draw_sensitivity.csv` records split-half sensitivity within that family. `target_uncertainty_full.csv` retains mean probability, predicted-minus-observed difference in percentage points, and O/E under development-only, joint-year and joint-block uncertainty.

Each bracketed value is an estimate followed by its interval. The full table definitions, units and interpretation notes are in `target_comparison_source_tables.json`. These summary files accompany the analysis code and are not replacements for the underlying predictions or joint draws. The exact current package has not yet been publicly released.
