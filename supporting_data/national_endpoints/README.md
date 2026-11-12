# National endpoint dispersion and population definitions

Table S18 displays the four all-available endpoint summaries. national_extent_dispersion.csv retains all twelve original rows at full precision, including the common damage-positive airport set and endpoint-specific expected-count subsets. dispersion_display.csv and display_definition.json preserve every original display cell and note. No airport or endpoint was removed from the analytical files.

national_extent_profiles.csv contains 4,898 endpoint-airport rows: 1,375 for each of three full-report endpoints and 773 for M? conditional on recorded damage. All 602 airports without damage remain in the full-report endpoints. The common 773-airport set contributes 43,724 eligible reports to each full-report endpoint, but only 3,096 damaged reports to conditional M?. Endpoint-specific E-at-least-five sets are not a matched population. The conditional-M? all-available and common-set rows intentionally coincide.

national_crossfit_coding_rates.csv contains 55 annual coding-rate estimates across five geographic folds. Each estimate excludes the evaluated fold and every target airport. Airport profiles preserve O, E, conditional variance, O/E and standardized discrepancy. Dispersion is the equal-airport mean of squared standardized discrepancies. Different endpoint variances and report denominators prevent interpreting a difference between dispersion values as a share explained by documentation. These are conditional descriptive checks, not joint intervals or formal parameter tests.

All numerical files were copied from saved results. No fit, coding model or resampling was rerun. The files have not been publicly released.
