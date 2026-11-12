# Damage-extent partition and paired comparisons

Run `python analyze_partition.py --config inputs.json --output new-results`.
The output directory must be new. Copy inputs.example.json and change its file
paths to your local retained data. Relative paths resolve against the config
file directory. Every supplied input is verified against its SHA256 value.
The example contains the exact hashes for this study, not invented sample data.
The event cohort, frozen predictions and saved fit attempts are separate data
dependencies. They are not included in this component. The current corresponding
data archive has not been publicly released; no public DOI is claimed here.

The computation preserves the national/target split, three allocation schemes,
500 attempt records (498 successful fits), twenty synchronized target-year draws
per successful fit, and geographic-fold exclusions. It constructs eight-airport
relative simultaneous intervals and a sixteen-comparison subtype family. It also
reconstructs national endpoint profiles and report-volume calibration summaries.
Calendar/source allocation uses descriptive national proportions. The analysis
does not establish a causal contribution of coding or reporting selection.

This route regenerates results from saved predictions and replays fixed random
seeds. It does not refit the damage models or provide independent validation.
The results had already been examined before this packaging work. Failed attempts
are retained. Saved NPZ files contain event identifiers and are loaded with
pickle support; use only trusted retained inputs with the supplied hashes.

Outputs include numerical CSV files, compressed joint draws, role-based input
hashes, saved-fit hashes and verification.json. Errors retain failure.txt.
No manuscript, peer-review document or local authoring paths are required.
