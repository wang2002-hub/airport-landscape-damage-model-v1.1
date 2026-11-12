# Bird-strike case-mix analysis core

These command-line programs prepare the report cohort and fit national reference models. They use supplied input files and write to a new output directory. The eight target airports remain outside model development and calibration.

## Environment

The retained runtime uses Python 3.12.14 on Windows with the versions in `requirements.txt`. Install those dependencies in the analysis environment. The scripts do not locate packages in a private project folder. Directory relocation has been evaluated on the same host; installation on a clean machine and cross-platform equivalence require separate checks.

```text
python -m pip install -r requirements.txt
```

## Prepare the report cohort

Provide the selected FAA fields, the species taxonomy, the airport eligibility lookup, the airport-year environmental panel, and the retained geographic fold assignment. The input schema describes their columns. Data files are supplied separately. The species and airport lookup files are necessary inputs, not outputs inferred from the eight target outcomes.

```text
python prepare_cohort.py --raw DATA/raw_selected.parquet --taxa DATA/taxon_reference.csv --airports DATA/airport_reference.csv --environment DATA/environment.parquet --folds DATA/spatial_folds.csv --config analysis_config.json --output OUTPUT/cohort
```

The output `processed/analysis_events.parquet` contains eligible reports. Audit files record duplicate handling, environmental closure, cohort counts and airport-year counts. The analysis covers 2015–2025. Known positive damage includes FAA code M?, which records damage with undetermined extent. Unknown or conflicting labels are handled by the retained eligibility rules.

## Fit national reference models

```text
python fit_references.py --data OUTPUT/cohort/processed/analysis_events.parquet --config analysis_config.json --output OUTPUT/national --workers 2
```

This runs 48 outer configurations: two model families, four information blocks, and six validation settings. The families are airport random-intercept logistic models (`glmm`) and histogram gradient boosting (`hgb`). The blocks are E, EL, EB and EBL. E denotes event information, B adds recorded bird size and number struck, and L adds landscape measurements. Environmental scale and tree settings are selected within the training data.

The temporal design trains through 2022, calibrates on 2023, and evaluates 2024–2025. Its frozen models also predict the eight target airports. The geographic design holds out one of five assigned folds and uses the remaining folds for internal selection and calibration. Target airports never enter these folds. Hierarchical predictions integrate over the random-intercept distribution, rather than estimating target-specific effects from their outcomes.

Optional `--scheme`, `--family` and `--block` arguments run a stated subset. They accept `all` or a single value shown by `--help`. A subset run does not constitute completion of the full analysis. Each worker uses two numerical threads. Fitting failures are logged and cause a nonzero final exit status. A run directory is never treated as a cache.

## Fit the simple EB comparator

```text
python fit_simple_reference.py --data OUTPUT/cohort/processed/analysis_events.parquet --output OUTPUT/simple
```

This fits ordinary logistic EB models using the same temporal and geographic divisions. It includes 26 fits: one temporal fit and five geographic outer fits, each with four inner fits. Encoding is learned only from training rows. Calibration uses 2023 in the temporal design and inner-fold predictions in the geographic design. The numerical thread limit is one.

## Outputs and provenance

Each entry point records input hashes, source hashes and dependency versions in `run_inputs.json`. Model outputs include event-level raw and calibrated probabilities, fitted model objects, encoding details and convergence records. Use a new or empty output directory. Failed runs remain available for inspection.

The configuration retains the study's fixed seed and design. This is a retrospective analysis, and target summaries had been examined. The configuration is not a prospective preregistration. O/E describes damage among eligible reports with known labels. It does not estimate strike incidence per flight or remove unmeasured confounding.

## Scope

This directory contains the cohort and national-reference core. It is one component of the complete research workflow. Raster extraction, enhanced bird/species comparators, joint resampling, coding diagnostics, provider profiles, partial pooling, reporting analyses and manuscript figures use separate modules. The companion aggregate replay recomputes summaries from retained aggregate inputs. Neither component alone reconstructs the complete study.

No incident data, manuscripts, review documents or private execution logs are distributed in this directory. `verification_summary.json` states the tested coverage. `manifest_sha256.csv` provides checksums for the distributed files.
