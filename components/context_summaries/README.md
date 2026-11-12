# Descriptive context summaries

This component reconstructs landscape variability, three-date canopy context, report-composition standardization, annual frozen-reference summaries and year-deletion ranges. These are descriptive checks. They are separate from model training, out-of-fold performance and uncertainty intervals.

## Run

The verified environment uses Python 3.12.14 and the package versions in `requirements.txt`. Copy `context_inputs.template.json` and bind the environmental panel, analytic event cohort, frozen temporal hierarchical EBL predictions and matched-year canopy table. Relative paths resolve against the JSON file.

```text
python summarize_context.py --inputs context_inputs.json --output OUTPUT/context
```

Use a new or empty output directory. Inputs are read-only. The entry records complete file hashes, code hashes and runtime versions. The final target event identifiers, airports, years and outcomes must agree with the frozen predictions. Environmental airport-year keys and the target canopy keys must be unique.

## Populations and denominators

The analytic cohort contains 46,167 national reports from 1,375 airports and 5,936 target reports from eight airports. Target reports include 309 recorded damage outcomes. The national reference excludes all targets.

Landscape variability uses national airports with eleven distinct annual rows and complete eligibility across the stated rings. All 1,375 national airports qualify, giving 15,125 airport-years. Between-airport variability is the sample standard deviation of airport temporal means. Within-airport variability is the square root of the average airport sample variance. These calculations weight airports equally. The temporal range is computed separately for each airport before its median and the fraction below one percentage point are summarized. Fractional cover values are multiplied by 100; imperviousness is already in percent. These summaries do not measure predictive improvement.

Canopy context retains the three measured dates, 2015, 2020 and 2025, for each target's 13 km zone. No annual interpolation is applied. Target landscape context contains 88 airport-year rows.

Composition standardization groups national reports by phase, recorded aircraft mass class and bird size. Supported strata have at least twenty reports from five national airports. Their national observed damage proportions are reweighted by supported target frequencies. Each supported-target observed proportion uses the same target reports as those weights. The all-target observed proportion has a separate denominator. Unsupported reports remain visible in the counts. These full-period empirical reference proportions are descriptive; they are not out-of-fold predictions, causal adjustments or flight-exposure rates.

Annual summaries and leave-one-year-out summaries retain the frozen hierarchical EBL probabilities. Each of eleven calendar years is omitted once per airport. The remaining observed and expected damage counts are recomputed without fitting a model. Bias is predicted minus observed probability in percentage points. The ratio is remaining observed damage divided by remaining expected damage. The deletion range describes annual influence and is not a confidence interval. All eligible years remain in the primary analysis.

## Verified outputs

The nine output tables reproduce 24 canopy rows, six landscape variability rows, 88 target landscape rows, 96 national strata, eight standardization rows, 88 annual rows, 88 deletion rows, eight deletion summaries and 1,383 airport map rows. Values, missingness, data types and row order match the retained results, with maximum numerical difference zero.

Independent checks cover national stratum totals, supported-target weighting, annual observed and expected counts, and deletion conservation. Duplicate environmental keys, duplicate canopy records, mismatched prediction outcomes and existing output directories are rejected. Complete input hashes remain unchanged. The calculation block matches the retained analysis after relocation of input loading.

Execution used relocated code and an empty working directory on the same host. No model was fitted and no random sample was drawn. A clean installation and raw raster extraction are separate verification tasks.
