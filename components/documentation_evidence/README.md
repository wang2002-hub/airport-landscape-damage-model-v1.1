# Documentation evidence replay

Run `python replay_documentation.py --output /path/to/separate-results`.
Python requires numpy and pandas. The verified local versions are Python 3.12.14,
numpy 2.3.5 and pandas 3.0.1. No network access is used.

The included aggregate inputs reconstruct 135 partition interval rows, sixteen
relative-comparison rows, sixteen subtype-family rows and twelve national
dispersion rows. Three allocation schemes and all nine target/pooled series are
preserved. Two failed model-fitting attempts (224 and 336) remain excluded,
leaving 498 saved fits and twenty synchronized year resamples per fit.

This is a deterministic replay of saved aggregate counts, probabilities and
joint draws. It does not independently rebuild the cohort, refit the models or
validate their event-level predictions. These results had already been viewed
before this release-verification script was prepared. No new random draws or
model fits are generated. Numerical comparisons use relative and absolute
tolerances of 1e-10; identities are also checked for every stored draw.

Output includes recomputed CSV tables, input hashes and a verification report.
Failures retain a traceback in the chosen output directory. The manuscript and
peer-review correspondence are excluded from this component.
