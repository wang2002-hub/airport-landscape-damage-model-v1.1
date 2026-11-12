# Surface-weather diagnostics

This component reconstructs retrospective weather matches for the eight target airports. It retains frozen hierarchical EBL probabilities and summarizes their agreement with recorded damage within descriptive strata. It fits no weather model and estimates no causal weather effect.

## Run

Same-host verification used Python 3.12.14 and the versions in `requirements.txt`, including tzdata 2026.5. Copy `weather_inputs.template.json` and bind the extended event table, frozen predictions and eleven surface CSV files for each airport. Preserve the original order of each airport's files. Relative paths resolve against the JSON file.

```text
python match_surface_weather.py --inputs weather_inputs.json --output OUTPUT/weather
```

Use a new or empty output directory. The entry records hashes of both event/prediction inputs and all 88 weather files. The matched table is written under `processed`; airport audits, time evidence, strata and method notes are written under `results`. Failures remain in `logs` and cause a nonzero exit code.

## Time and missingness

Each source file is checked against embedded METAR day/hour/minute UTC stamps. More than 100 comparable records and at least 99% agreement are required. This is the retained consistency check, rather than an independent guarantee of every source timestamp. FAA event clocks are interpreted as local civil time and converted using the airport's IANA zone. Ambiguous and nonexistent daylight-saving times remain unmatched.

Temperature, wind speed and precipitation are matched separately to the latest nonmissing observation at or before the event, within 60 minutes. A later wind-only report therefore does not hide a valid earlier temperature. Matching never uses future observations. At duplicate station-time keys, the retained rule compares all three variables, treating missingness as a distinct state. A conflict in any variable removes that timestamp from all three matching series.

Temperature values outside -100 to 140 Fahrenheit, wind outside 0 to 200 knots and precipitation outside 0 to 20 inches are missing. Trace and nonnumeric precipitation remain missing. A zero denotes an explicit reported zero. The precipitation value is the accumulation stated in the surface record, not a measurement of rain at the instant of impact.

The separate hourly precipitation spreadsheets have unresolved time provenance and remain outside this match. FD forecasts at altitude also remain separate from surface observations. Target-only weather summaries supply context; they are not additional national predictors.

## Verified coverage

All 5,936 target reports remain in the matched table, including reports with unavailable clocks or weather. A surface timestamp was found for 5,655 reports; 281 had none. Variable-specific availability differs from this general timestamp match.

| Variable | Matched reports | Unmatched reports | Largest lag in minutes |
| --- | --- | --- | --- |
| Temperature | 5,653 | 283 | 59 |
| Wind speed | 5,654 | 282 | 59 |
| Reported precipitation | 5,457 | 479 | 60 |

The replay matched the retained event table, eight airport audit rows, 88 time-evidence rows and 384 descriptive stratum rows. Data types and missingness matched. Each available measurement had a nonnegative lag of at most 60 minutes. All 108 field/population totals preserved their report and damage denominators. Strata overlap across variables and periods; they must not be added as independent samples.

Repeated event identifiers, mismatched prediction labels, duplicate weather paths, inconsistent timestamp evidence and nonempty output directories were rejected. All 90 source inputs remained unchanged. This was a relocated same-host replay with an empty working directory, not a clean-installation test. No model was fitted and no random sample was drawn.
