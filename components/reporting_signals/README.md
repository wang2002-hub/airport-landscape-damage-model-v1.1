# Reporting signals (added in v1.1)

Code for the revised manuscript's reporting-system results, the D1 annual check and a
value audit. Every input is a bundled aggregate table under `supporting_data/` or
`components/*/inputs/`, checked against the SHA256 values in `inputs.json`. No model
is fitted and nothing is resampled.

Run each entry from this folder with a new output directory:

```
python d1_annual_damage_check.py   --output ../../../v11-results/d1
python verify_reported_values.py   --output ../../../v11-results/audit
python plot_reporting_signals.py   --output ../../../v11-results/fig02
python plot_coding_losses.py       --output ../../../v11-results/figS08
```

| Entry | Output | Manuscript use |
|---|---|---|
| d1_annual_damage_check.py | annual_damage_composition.csv, national_period_summary.csv, national_total_damage_contrasts.csv, target_year_restriction_OE.csv, target_annual_OE.csv, d1_summary.json | Section 4.5, 5.1 and 5.5 sentences on the 2015-2017 coding change; Table S21 national report and damage-percentage columns |
| verify_reported_values.py | manuscript_value_audit.csv/json | Checks 74 headline values against bundled files |
| plot_reporting_signals.py | fig02_reporting_signals (PNG/TIFF/PDF/SVG) and plotted values | Main-text Fig. 2 (panels A-D) |
| plot_coding_losses.py | figS08_coding_losses (PNG/TIFF/PDF/SVG) | Fig. S8 (former Fig. S9B-C) |

Notes

- Annual denominators in `annual_composition.csv` are cross-checked against
  `reporting_category_by_year.csv` and against the period totals in
  `population_counts.csv` (46,167 national and 5,936 target reports).
- The target-year restriction uses the frozen hierarchical EBL airport-year
  predictions in `annual_influence_by_year.csv` (total E = 275.64, the primary value).
  It removes evaluation years only; it is not a refit.
- Chi-square contrasts in `national_total_damage_contrasts.csv` are descriptive and are
  not reported in the manuscript.
- Not assessable with bundled files: national geographic calibration by year
  (outer-test predictions are external) and a categorical-year refit (the event-level
  cohort `analysis_events.parquet` is external). Log-scale subtype simultaneous intervals
  also require the 498 external `attempt_XXX_predictions.npz` files.

## Round-4 task scripts integrated with R5

`round4/` contains the four unchanged scripts from the supplied R5 task folder:
annual calibration, an optional year-specification patch, log-scale subtype
simultaneous intervals / zero-draw counts, and manifest regeneration.
All four are registered as `round4/<script>.py` entries in this component.
See `round4/README.md` for current commands, requirements and external-input limits.
The year patch has not been applied to the release model files.
