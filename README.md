# Airport landscape damage model

Code and supporting evidence for *Case-mix profiling of airport bird-strike damage reports: uncertainty and damage-extent documentation*.
The document hashes in manuscript_binding.json identify the five accompanying submission files. Manuscript text and peer-review correspondence are excluded.

## Quick start
Use Python 3.12. From the repository root:
```
python -B verify_manifest.py
python -B run_component.py --list
python -B run_component.py --component evidence_replay --entry replay_aggregates.py -- --output ../aggregate-results
```
The aggregate example uses only the standard library. Use a new output directory outside the repository. Other entries require dependencies and their documented inputs.

## Current analysis and figures
The documentation_partition, coding_transfer, report_volume_calibration and reference_comparison components reproduce the current diagnostics. documentation_evidence replays saved joint summaries without event-level model fitting. Figure correspondence lists all seven main and eleven supplementary figures. Current figure PNGs are retained as comparison assets; they do not substitute for source code. Graphical abstract code is separately provided.

Portable components accept explicit JSON input roles with hashes. Included figure configurations are ready to run. Event-level cohort, saved model-fit and GIS inputs required for full rebuilding are external dependencies; their roles and example hashes are documented. All failed attempts are retained where relevant. Previously viewed outcomes informed these exploratory analyses; packaging checks are not preregistration or independent validation.

## Data and access
supporting_data contains retained aggregate evidence and 40 compact report-level prediction tables. These contain event identifiers, labels and predictions, not narrative reports or author correspondence. supporting_file_inventory.csv identifies them. Large raw FAA/GIS data, event cohort and complete saved bootstrap files are not bundled. The exact matching current data archive has not been publicly released; no public DOI is claimed. Check provider terms before redistributing source products.

## Environment and verification
requirements.txt pins the analysis environment. requirements-figures.txt pins the tested drawing environment; use separate environments rather than mixing their numpy versions. Component requirements describe their local routes. Verification records distinguish executed current-result replays and image reproduction from inherited code and externally supplied input routes. No claim is made of a clean-machine installation, all national raster/model refits, or a single full end-to-end run. See verification_summary.json.

## Publishing
Upload this folder's contents as the GitHub repository root. Do not upload the author's work directory. CITATION.cff contains the supplied author names; no DOI or public release date is invented. No software license has been assigned by this package: public visibility alone does not grant an open-source license. Data-provider and dependency terms remain applicable. This preparation performs no remote upload.

## Optional GIS routes
Raster and spatial-context commands require the GIS packages listed by their components. Their help text is available before loading optional GIS libraries. Viewing help is an interface check, not a raster-processing test. Component verification summaries are retained computational records unless explicitly marked as current-release executions.

## Version 1.1
Version 1.1 matches the revised submission with seven main and eleven supplementary figures. components/reporting_signals adds the annual damage-composition check (reviewer item D1), an audit of 74 manuscript values against bundled files, main-text Figure 2 and Figure S8. The review-workflow and national-profile exporters were updated for the new figure numbering. CHANGELOG_v1.1.md lists every change and the v1.0-to-v1.1 figure numbering; figure_correspondence.csv gives the current mapping. No inferential input or saved prediction was changed, and no event-level rerun is claimed.

## R5 code integration (2026-11-12)

The four supplied round-4 task scripts are included unchanged under
`components/reporting_signals/round4/` and registered with `run_component.py`.
Their README provides commands using the integrated paths and distinguishes pending
external-data analyses from package checks. The year-specification patch is optional;
it has not been applied to the released model code. No new inferential result is claimed.
See `r5_packaging_verification.json` for this integration's checks.

The requested delivery filename is `airport-landscape-damage-model-v1.0.zip`.
Its contents are the current v1.1 repository plus the R5 round-4 scripts; the archive
name is a delivery label, not a downgrade to software version 1.0.
