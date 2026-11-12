# Airport report aggregate evidence replay

This directory checks numerical summaries for eight held-out airports and five national references. It contains airport-level aggregates and synchronized resampling draws. The script uses the Python standard library and requires no network connection. Run it with Python 3.12 or later.

```text
python replay_aggregates.py --output ../evidence_results
```

Choose an output directory outside this directory. The command first checks every retained file against the SHA-256 manifest. It recalculates pooled ratios, 32 pointwise intervals and 16 airport comparisons under two centering conventions. The latter include relative ratios, simultaneous intervals and Holm-adjusted bootstrap values. It also checks national profile summaries, dispersion-width counts, flag overlap and coding-related count identities. A failure produces a nonzero exit status and a failure record in the output directory.

The 79,680 draw rows represent eight airports, 498 successful development fits and 20 synchronized year samples per fit. These are 9,960 dependent fit-year combinations, not 9,960 independently fitted models. Relative ratios use the same draw's pooled reference. The simultaneous procedure is a single-step maximum statistic with fixed estimated scales. National conditional limits address a different uncertainty question.

This is an aggregate verification component. It does not fit models, rebuild raw report cohorts, recover omitted outcomes or extract raster measurements. Saved conditional count limits and tail probabilities are inputs; the script does not reconstruct their probability mass functions. It does not recalculate event-level losses or posterior ranks. Code and data for full analytical reproduction require separate input mappings and execution checks.

Input files omit incident narratives, aircraft registration numbers and event-level predictions. They retain public airport identifiers and aggregate counts. No public deposit, publication identifier or complete-study reproduction is asserted. The authors determine the final release and licensing terms.
