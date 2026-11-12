# Uncertainty procedures and interpretation

## Joint target intervals and multiple comparisons

Joint target intervals combine national development variation and variation across observed target years [29]. Of 500 national-airport bootstrap attempts, 498 passed fitting and calibration checks; attempts 224 and 336 failed the calibration optimizer check. Each successful fit supplies 20 resamples of eleven years, synchronized across all eight airports, giving 9,960 dependent summaries per airport. Relative ratios recompute the pool within each fit-year draw, including the focal airport (Appendix A.2). Absolute and relative ratios define separate eight-comparison families. Appendix A.4 specifies percentile pointwise intervals and single-step log-scale maximum-statistic intervals with fixed bootstrap standard deviations. The latter differ from Romano–Wolf stepdown testing [30]. Approximate marginal tail probabilities use an add-one correction and within-family Holm adjustment [31]; their threshold decisions can differ from the simultaneous intervals. Primary centering uses fitted estimates. Bootstrap-mean centering changes multiplier deviations while keeping interval centers at fitted estimates.

Development replication is 498 fits, since year samples sharing a fit are dependent. Each family concerns eight specified comparisons, with no nationwide or combined sixteen-comparison guarantee. Centering and split-half checks assess sensitivity without choosing results after inspection.

## Other uncertainty summaries

Table S6 distinguishes joint, development-only and fixed-reference uncertainty. Circular two-year sampling joins final and initial years. The landscape contrast repeats preprocessing, selection, fitting and calibration for EB-to-EBL. Of 200 attempts, 198 succeeded; attempts 25 and 132 failed calibration checks. National test airport histories are resampled; fixed target reports make their intervals development-only. Conditional funnel limits assume independent Bernoulli outcomes at fixed probabilities; dispersion envelopes have unestablished nominal coverage (Appendix A.3). Full-data rank intervals draw airport effects conditional on fitted coefficients and variance, including targets. They describe partial pooling rather than held-out geographic prediction. The damage-extent partition preserves every eligible report and recomputes annual national coding proportions within development resamples (S8.1). Its separate sixteen-comparison airport-by-subtype family uses natural-scale maximum statistics, with negative lower endpoints truncated at zero. Pooled subtype intervals remain pointwise (Appendix A.5). This family differs from the log-scale total-damage families.

Failed repetitions remain documented. Recent windows contain only two annual clusters and receive descriptive estimates without intervals. Leave-one-year-out ranges describe observed influence, not confidence intervals.

## Scope of inference

The resampling analyses evaluate existing report collections under their stated varying components. Resampling observed years does not validate future alerts or management interventions. Full-data rank intervals condition on fitted coefficients and variance and include the targets; they do not evaluate held-out geographic prediction. Table S6 and uncertainty_catalogue.csv distinguish all fourteen procedures. uncertainty_definitions.json records the counts, failed attempts and comparison families.

## Formula locations

Appendix A.2 defines the pool and relative ratios. Appendix A.3 gives conditional count limits and dispersion envelopes. Appendix A.4 defines total-damage and relative intervals, centering, add-one tail probabilities and Holm adjustment. Appendix A.5 defines the damage-extent partition and natural-scale subtype intervals, including zero truncation of negative lower endpoints.

## Cited sources

[29] Efron, B. (1979). Bootstrap Methods: Another Look at the Jackknife. The Annals of Statistics, 7(1), 1-26. https://doi.org/10.1214/aos/1176344552

[30] Romano, J.P., Wolf, M. (2005). Stepwise multiple testing as formalized data snooping. Econometrica, 73(4), 1237–1282. https://doi.org/10.1111/j.1468-0262.2005.00615.x

[31] Holm, S. (1979). A simple sequentially rejective multiple test procedure. Scandinavian Journal of Statistics, 6(2), 65–70. https://www.jstor.org/stable/4615733
