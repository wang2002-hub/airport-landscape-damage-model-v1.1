# Review periods and local performance

The CSV files reproduce five retained source tables without new fitting or resampling. Recent model comparisons concern 2024–2025 and overlap the full 2015–2025 population. Hierarchical and boosting EBL predictions remain frozen. Full-period ordinary and EBL losses are evaluated on the same reports within each airport.

`recent_primary_magnitudes.csv` reproduces manuscript Table 2 panel B. `local_ebl_performance.csv` retains Brier loss, log loss, ROC AUC, average precision and diagnostic calibration slopes for both EBL families. `local_ordinary_reference.csv` retains ordinary logistic EB counts, expectations and losses. `annual_deletion_ranges.csv` records descriptive ranges rather than confidence intervals. Full definitions and original notes are in `review_period_source_tables.json`.

Printed decimals retain the source precision. Differences in the paired contrast table were computed before rounding; subtracting printed absolute scores can differ in the final digit. These summaries accompany the underlying analysis code and retained predictions. The current package has not yet been publicly released.
