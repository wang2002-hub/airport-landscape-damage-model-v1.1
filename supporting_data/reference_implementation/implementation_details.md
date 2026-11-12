# Reference implementation details

## Objectives and marginal prediction

The hierarchical model uses logistic regression with a normally distributed airport random intercept and a first-order Laplace approximation. Its objective adds half of 0.0001 times the squared fixed-effect coefficients, excluding the intercept, to the summed negative approximated log likelihood. The ordinary EB comparator uses the same encoding and nonintercept penalty convention with the summed Bernoulli negative log likelihood. It contains neither airport indicators nor landscape terms. Ordinary EB is implemented in fit_simple_reference.py; the generic logistic branch and FixedInterceptLogit in model_core.py are different routines.

Hierarchical predictions use 30 Gauss–Hermite nodes to integrate the random-intercept distribution for every evaluation population, including development airports. Probabilities are clipped to the interval from 0.00000001 to 0.99999999. The log standard deviation is bounded from −4 to 2. The conditional-mode calculation allows 60 updates, clips each update to the range from −3 to 3, and stops when the largest absolute update is below 0.000000001.

## Optimizers and acceptance

The hierarchical L-BFGS-B optimizer allows 250 iterations per attempt. Its first attempt uses ftol 0.00000000001, gtol 0.00001, maxls 40 and maxcor 20. Optimizer failure or a maximum absolute raw gradient above 0.02 triggers a restart from the first result, with ftol 0.0000000000001 and maxcor 30. The other settings remain unchanged. The final optimization record is saved. The fitting wrapper requires optimizer success and a maximum projected gradient at most 0.025. At the lower variance bound, a positive raw gradient is projected to zero; at the upper bound, a negative raw gradient is projected to zero. The wrapper uses log-standard-deviation thresholds −3.999 and 1.999 for this projection. Its acceptance test differs from the raw-gradient trigger used for the internal restart. A rejected fit raises an error, and the task failure record includes the collected fit records and traceback.

Ordinary EB uses L-BFGS-B with 1,000 iterations, gtol 0.0000001, maxls 40 and maxcor 30. Initial coefficients are zero except for the intercept, which is the logit of the training outcome proportion. An unsuccessful optimizer or maximum absolute gradient above 0.025 permits one restart from the preceding coefficients. The first ftol is 0.000000000001; the restart uses 0.00000000000001. Acceptance requires success and a maximum absolute gradient at most 0.025. Both attempt records are saved when a restart occurs. Ordinary optimization is unconstrained, so this gradient does not require a variance-bound projection.

## Boosting and selection

Histogram gradient boosting compares maximum depths two and three. Both candidates use 150 iterations, learning rate 0.05, minimum leaf size 40 and L2 regularization 10. Early stopping is disabled, and the random seed is 20261028. The mean of inner-validation log losses selects the candidate within each information block. When landscape inputs are present, candidate representations are evaluated jointly with the boosting settings. Ties use candidate order. Training-only encoding and the fixed temporal/geographic partitions are specified in S2.1–S2.3; target reports remain outside development.

## Calibration and diagnostic roles

Calibration applies a logistic transformation to the prediction logit. The intercept is bounded from −10 to 10 and the slope from 0.05 to 5. Starting values are intercept zero and slope one. Its objective adds half of 0.0001 times the sum of the squared calibration intercept and slope to the summed Bernoulli negative log likelihood; this penalty includes both calibration coefficients. L-BFGS-B uses ftol 0.000000000001 and gtol 0.0000001. Prediction probabilities are clipped before taking logits. The main fitting wrapper requires calibration success and records boundary proximity. The 48 saved primary configurations have no recorded calibration-bound hits. Evaluation calibration diagnostics describe held-out predictions and do not update them. Diagnostic fit details and the numerical checks in supporting_data/validation_records/numerical_checks.md retain their respective roles.

## Files and scope

The package paths components/analysis_core/model_core.py, fit_references.py, fit_simple_reference.py and analysis_config.json define these routines and settings. code_sources.json records their checksums and source spans. Full selected configurations are supplied in supporting_data/environmental_measurements/model_configurations. The interpretation of the nine-reference direction comparison and the four paired local loss comparisons remains as stated in S2.1. These implementation records describe existing analyses; they do not establish independent predictive validation or prospective management benefit.
