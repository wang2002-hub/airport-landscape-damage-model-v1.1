# Report Volume Calibration

Run `python diagnose_volume.py --config inputs.json --output new-results`.
Copy inputs.example.json and map each role to the retained local input file.
Paths are relative to the config directory unless absolute. All files are
checked against the supplied SHA256 hashes before computation. Choose a new
output directory. Errors retain failure.txt; successful runs record input hashes.

Tie-preserving report-count groups and their membership remain fixed during the original 2000 airport-cluster draws per group. Observed and predicted values use the same sampled airports. The gap is stored as a proportion; multiply by 100 for percentage points. Pointwise intervals are conditional on saved predictions and groups, not simultaneous intervals or estimates of reporting selection.

This route replays retained study evidence. It does not fit new model coefficients,
select a model, or supply independent validation. Results were viewed before this
code-packaging verification. The current corresponding data archive remains
unpublished; the example provides exact input hashes and roles, not a public DOI.
Event-level data and saved predictions are external dependencies, not bundled here.
No manuscript or reviewer correspondence is needed to run this component.
