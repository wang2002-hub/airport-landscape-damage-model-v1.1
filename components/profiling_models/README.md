# Airport profiles, conditional ranks and enhanced event references

These programs read explicitly supplied inputs and write to new output directories. They use the numerical core and dependency versions in the companion core-analysis component. Same-host verification used Python 3.12.14. Install the packages listed in `requirements.txt` in the analysis environment. Event-level data and retained predictions are supplied separately.

## National profiles and target comparisons

```text
python profile_airports.py --data DATA/analysis_events.parquet --national-dir DATA/national_predictions --simple DATA/simple_predictions.parquet --reference DATA/temporal_0_glmm_EBL_predictions.parquet --draws DATA/primary_joint_draws.csv.gz --intervals DATA/primary_joint_intervals.csv --output OUTPUT/profiles
```

The national prediction directory contains five geographic-fold files for each of hierarchical EB, hierarchical EBL, boosted EB and boosted EBL. The simple prediction file supplies the fifth reference, ordinary logistic EB. Each reference covers all 46,167 national reports and 1,375 national airports. Predictions come from geographic folds that exclude the evaluated airport.

The program rebuilds Poisson-binomial count distributions, conditional count limits and O/E summaries. It also compares reference ordering and marked sets. All airports remain in the primary output. Higher expected-count or report-count thresholds define named display subsets. Boundary ties are retained in decile comparisons.

Target comparisons use frozen temporal hierarchical EBL predictions and the retained paired joint draws. The pooled report count, damage count and expected count are computed from the supplied predictions. They are not fixed numerical constants in the analysis code. Target subtype counts, source strata and the conditional target overlay are also produced. These counts describe eligible reports with known labels, rather than strike incidence per flight.

## Conditional count-limit audit

```text
python audit_count_limits.py --data DATA/analysis_events.parquet --national-dir DATA/national_predictions --simple DATA/simple_predictions.parquet --reference DATA/temporal_0_glmm_EBL_predictions.parquet --profiles OUTPUT/profiles/results/national_profiles.csv --output OUTPUT/limits
```

This entry checks the count distribution with exhaustive enumeration for a short probability vector. It also uses independent FFT convolution for the two largest national airports under each reference. The remaining calculations cover all national airports, discrete tail probabilities, width sensitivities and marked-set overlap.

Multiplicative width factors are estimated in three stated populations. The widened envelope includes the original discrete limits and the expected count. The output retains both the estimation population and the display population. Conditional count limits hold fitted predictions fixed. They differ from joint uncertainty intervals and simultaneous target comparisons.

## Conditional airport effects and rank uncertainty

```text
python partial_pooling.py --data DATA/analysis_events.parquet --profiles OUTPUT/profiles/results/national_profiles.csv --output OUTPUT/pooling
```

This explanatory hierarchical EBL fit uses the complete 52,103-report cohort, including the eight targets. It covers 1,383 airports and uses the original 3 km landscape specification. Each airport's conditional intercept density is evaluated on a 4,001-point grid. Selected densities are checked with adaptive integration. A fixed seed generates 5,000 conditional draws per airport for rank summaries.

The effects and rank intervals condition on estimated coefficients and variance. They omit uncertainty in those hyperparameters. They are not safety ranks or held-out validation of the target airports. The joined external O/E table retains missing geographic predictions for the targets, which were excluded from national development.

## Enhanced event references

```text
python fit_enhanced_references.py --data DATA/analysis_extended.parquet --config analysis_config.json --features enhanced_features.json --output OUTPUT/enhanced
```

The seven extra fields are height, distance, time of day, aircraft class, speed, engine type and engine count. Encoding, missingness handling and numerical scaling use training data. Reported speed outside 0–400 indicated knots is treated as missing. The base environmental correlation screening remains unchanged.

The entry fits two model families and four information blocks. Forward validation selects settings within the 2015–2022 training period. National reports from 2023 calibrate predictions. Evaluation uses national reports from 2024–2025 and the frozen target collection. Four paired landscape contrasts reuse 2,000 airport resamples each. The seeds and settings reproduce the retained analyses; the resamples are not new independent evidence.

## Outputs, provenance and tested scope

Every entry records input and source hashes and numerical-library versions. Nonempty output directories are rejected. Analysis failures are retained in the output directory. This component contains code, configuration, checksums and the verification summary. It contains no incident rows, manuscripts or review documents.

`verification_summary.json` describes the actual replay and its numerical errors. The tests used a relocated code directory and an empty working directory on the same host. They checked profiles, limits, conditional ranks, all eight enhanced references and paired contrasts. The verification also tests invalid probabilities, duplicate events and output protection. Clean-machine installation, cross-platform equivalence, raster extraction and the complete study workflow remain separate tasks.
