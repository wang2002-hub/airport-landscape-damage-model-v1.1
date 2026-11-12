# Coding Transfer

Run `python diagnose_coding.py --config inputs.json --output new-results`.
Copy inputs.example.json and map each role to the retained local input file.
Paths are relative to the config directory unless absolute. All files are
checked against the supplied SHA256 hashes before computation. Choose a new
output directory. Errors retain failure.txt; successful runs record input hashes.

The feature construction and Encoder definitions match the original computation exactly. Encoder statistics are reconstructed on the original 2015–2022 damaged national reports; saved coefficients and the 2023 calibrator remain fixed. Raw, calibrated and constant references are all retained. Temporal score differences are descriptive, not causal effects of changing coding practices.

This route replays retained study evidence. It does not fit new model coefficients,
select a model, or supply independent validation. Results were viewed before this
code-packaging verification. The current corresponding data archive remains
unpublished; the example provides exact input hashes and roles, not a public DOI.
Event-level data and saved predictions are external dependencies, not bundled here.
No manuscript or reviewer correspondence is needed to run this component.
