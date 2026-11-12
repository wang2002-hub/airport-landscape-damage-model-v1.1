# Landscape development bootstrap

This component reproduces the retained EB-to-EBL hierarchical development bootstrap. It samples complete national airport histories and repeats preprocessing, landscape-scale selection, final fitting and 2023 calibration. The target report collection remains fixed.

## Run

Same-host verification used Python 3.12.14 and the versions in `requirements.txt`. Supply the final analytical event table and the included analysis configuration. Use a new or empty directory for each command.

```text
python bootstrap_landscape.py --data DATA/analysis_events.parquet --config analysis_config.json --output OUTPUT/development --workers 4
python summarize_landscape_bootstrap.py --records OUTPUT/development/results --output OUTPUT/summary
```

The first command records every attempted replicate, including failures. Exit code 2 indicates that one or more recorded attempts failed the fitting or calibration requirements. It does not discard the successful outputs. Inspect `run_status.json` and the individual records before summarization. The verified reference run contains failures 25 and 132. Other failures must be investigated rather than treated as expected.

`--attempts` can select unique original identifiers from 0 through 199 for a targeted replay. The default runs all 200. The summary entry requires all 200 records, including failures. It refuses incomplete collections. Existing output directories and duplicate attempt identifiers are protected.

## Design and estimand

Replicate i uses the configured seed plus i. Sampling is by national airport, with the complete history kept together across training, calibration and temporal testing. Repeated copies receive different random-intercept identifiers. Training ends in 2022, calibration uses 2023 and national testing uses 2024–2025.

EB uses recorded event and bird information. EBL repeats selection among the original 3, 8 and 13 km discs and ring representation. Forward validation uses 2019–2022. Candidate ordering and tie handling remain unchanged. Both models are recalibrated within every attempt. The recorded contrasts are EBL minus EB Brier and log losses.

National test histories participate in the cluster resampling. The eight target collections stay fixed. Target intervals therefore represent variation in national development and calibration for those retained reports. They are distinct from the separate 500-attempt absolute-probability analysis that combines development and target-year variation. Do not combine their denominators or interpret either as demonstrated management benefit.

## Outputs and verification

All 200 attempts were replayed. The successful attempts numbered 198; attempts 25 and 132 reproduced the calibration-success failures. Across these attempts, 4,383 internal and final fit records matched. The audit compared convergence records, sample counts, selected representations and paired losses, excluding elapsed time and machine-specific traceback paths.

The summaries contain 1,980 successful collection-loss rows and 20 metric-specific interval rows. Their 60 percentile values matched the retained summaries within 1e-10. The interval rows contain the 2.5th, 50th and 97.5th percentiles, conditional on successful attempts. Failure records remain separate and visible.

Verification used relocated code, an empty working directory and the same host. Four independent processes each used two numerical-library threads. Duplicate event records, repeated attempt identifiers, incomplete summary inputs and nonempty output directories were rejected. The input table and all 200 retained reference records remained unchanged. A clean installation and a complete raw-raster reconstruction were not tested here.
