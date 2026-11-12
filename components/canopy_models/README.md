# Static canopy model comparisons

This component fits eight existing EBL specifications: two model families, two land-cover timings and a paired static-canopy addition. It keeps the original selected scales and boosting parameters. No additional model search or canopy interpolation is performed.

## Run

Same-host verification used Python 3.12.14 and the versions in `requirements.txt`. Copy `canopy_inputs.template.json` and supply the extended event table, environment panel, matched-year canopy measurements and two retained temporal EBL configuration files. Relative input paths resolve against the JSON file.

```text
python fit_canopy_models.py --inputs canopy_inputs.json --output OUTPUT/canopy
```

The default runs both model families. `--family glmm` or `--family hgb` selects one family. Use a new or empty output directory. Outputs include raw/calibrated predictions, fitted bundles, parameter metadata, absolute metrics, input/code hashes and failure records. A failed model is retained in `model_failures.json` and causes a nonzero exit code.

## Design

The paired models use the same reports and base encoder. Hierarchical regression uses the retained 3 km representation; boosting uses 8 km. Both use the 2015 canopy measurement. Annual and fixed-2015 variants differ in their land-cover and impervious inputs, while keeping the canopy source fixed. Other canopy years are not interpolated into this experiment.

The national partitions contain 30,427 training reports through 2022, 4,616 calibration reports from 2023 and 11,124 test reports from 2024–2025. The eight excluded targets contain 5,936 reports; the recent target subset has 1,615. Every paired comparison retains its common report set and outcome labels. These overlapping predictions are not independent study samples.

Canopy measurements must be present with at least 95% valid coverage at the required disc radii. Training data determine scaling and other encoder operations. The canopy addition is kept outside the base environmental correlation screen, as specified in the retained design. Its paired base feature selection is checked explicitly.

## Results and verified scope

The successful relocated run repeated eight model fits and eight calibrations. All 136,480 prediction rows matched the retained raw and calibrated probabilities exactly. The eight parameter records and 24 absolute metric rows also matched, apart from execution time. Four national paired point estimates and 32 local paired summaries agreed within 1e-10. No random resampling was repeated; saved uncertainty intervals retain their own provenance.

National Brier changes from adding canopy were about -0.00000527 and -0.00000352 for hierarchical annual and fixed-map models. The corresponding boosting changes were about -0.00000536 and 0.00003344. These small changes have different signs. Their saved paired intervals span zero. The experiment describes a static information increment for recorded damage; it does not evaluate annual canopy change or vegetation-management effects.

Duplicate events, duplicate 2015 canopy keys, insufficient coverage and nonempty output directories were rejected. All five source inputs remained unchanged. The checks ran in a relocated directory with an empty working directory on the same host. They do not establish a clean dependency installation or a complete raw-raster reconstruction.

The verification counts above describe the successful retained-input replay. Detailed execution records are kept with the computational audit.
