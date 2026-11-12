# Bird-strike uncertainty and reporting diagnostics

These entries use explicit data paths and write to new output directories. They share the numerical core and dependency versions with the cohort and national-reference component. Python 3.12.14 and the packages in `requirements.txt` were used for same-host verification. Input data are distributed separately.

## National development resampling

```text
python joint_uncertainty.py --data DATA/analysis_events.parquet --config analysis_config.json --output OUTPUT/bootstrap --workers 2
```

The default attempts IDs 0–499. Each attempt resamples national airport histories. Repeated airports receive distinct intercept identifiers. Landscape selection repeats the original forward validation, followed by fitting through 2022 and calibration on 2023. The target airports remain outside fitting and calibration. Numerical threads are limited to one per worker.

Use `--replicates 0,1,249,250,499,224,336` for the documented subset replay. Every requested attempt writes a status file. Successful attempts also write target probabilities. Completion means that the requested attempts were recorded; it does not mean that every fit converged. `run_status.json` identifies failures and whether the full 500-attempt set was requested. Failed attempts are retained and excluded from probability summaries. Existing output directories with contents are rejected.

New NPZ outputs store event identifiers as string arrays. Their probabilities can be read with NumPy's default object-pickle protection enabled.

## Paired year draws and intervals

```text
python summarize_joint_uncertainty.py --reference DATA/temporal_0_glmm_EBL_predictions.parquet --bootstrap-dir OUTPUT/bootstrap/results --output OUTPUT/intervals
```

The input directory must contain all 500 attempt-status files and predictions for each successful attempt. Retained NPZ inputs with object-array identifiers require the explicit `--trusted-object-arrays` option. Use it only for the trusted retained study files. The supplied hashes identify those inputs. Newly generated string-array files do not need this option.

The entry reproduces five scopes: development-only variation, joint independent-year resampling, joint circular two-year blocks, and two fixed-prediction year schemes. Each successful development attempt contributes 20 synchronized samples to each joint scheme. All eight airports share the same sampled year sequence within a draw. The 498 successful development fits therefore yield 9,960 dependent combinations in the primary joint scheme. They are not 9,960 independent model fits.

The outputs include 195,344 draw rows and 160 interval rows for the retained study inputs. These row totals cover all five schemes. The primary joint independent-year scheme contains 79,680 airport rows. The companion aggregate-replay component computes pooled comparisons and simultaneous intervals from those primary draws. `sum_worker_seconds` in the aggregation summary comes from the supplied attempt records; it is not the duration of aggregation.

## Damage-extent coding diagnostics

```text
python coding_diagnostics.py --data DATA/analysis_events.parquet --reference DATA/temporal_0_glmm_EBL_predictions.parquet --restriction DATA/local_extent_complete.csv --labels DATA/target_label_completeness.csv --output OUTPUT/coding
```

The conditional model estimates the probability of FAA code M? among known damage reports. M? records damage with undetermined extent. Training uses national damage reports through 2022, and calibration uses national damage reports in 2023. The eight target airports remain excluded. Outputs retain national and target losses, subtype expectations, frozen-reference collection restrictions, and bounds for unresolved labels.

Subtype expectations combine the frozen damage probabilities with the conditional coding probabilities. They are exploratory point estimates. Their probability-loss results must accompany the decomposition. The entry recalculates collection restriction under frozen predictions. It reads the restricted-model expectations from `local_extent_complete.csv`; it does not refit that restricted damage model. Missing-label scenarios preserve the near-airport and known-label denominators.

## Report-source and reporter-role diagnostics

```text
python reporting_diagnostics.py --data DATA/analysis_events.parquet --near DATA/near_reports.parquet --raw DATA/raw_selected.parquet --reference DATA/temporal_0_glmm_EBL_predictions.parquet --source-benchmark DATA/target_source_strata.csv --year-benchmark DATA/coding_year_standardization.csv --output OUTPUT/reporting
```

The entry checks source and reporter-role fields against deduplicated source records. It retains 65,254 near-airport reports, including 54,919 known labels and 10,335 unresolved labels. Environmental and coordinate eligibility yields the 52,103-report analytical cohort. These populations retain separate denominators.

Seven tables describe category composition, annual distributions, stratified O/E, evaluated populations and supported coding benchmarks. Standardization keeps each supported numerator with its supported denominator. Unsupported cells and cells with fewer than five national damage reports remain visible. The source and year benchmark files provide numerical consistency checks. These analyses describe recorded report composition; they do not estimate a causal reporting-channel effect.

## Verified scope

`verification_summary.json` describes the actual replay. All saved bootstrap probabilities were used to reconstruct the five interval schemes. Seven development attempts were refitted, including both retained calibration failures. The conditional coding model was refitted, and all seven reporting tables were reconstructed. The full 500-attempt development fit was not repeated during this verification.

The tests used a relocated code directory and an empty working directory on the same host. They preserved the original inputs and checked missing attempt records, invalid probabilities, duplicate events and existing-output protection. A clean-machine installation and cross-platform numerical equivalence remain separate checks. These entries are components of the study workflow, rather than a standalone reconstruction of all analyses or raster extraction.
