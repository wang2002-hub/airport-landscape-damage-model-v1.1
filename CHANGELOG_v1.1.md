# Changes in v1.1 (2026-11-12)

v1.1 aligns the package with the revised RESS submission (seven main and eleven
supplementary figures). No analysis input, saved prediction or fitted model was changed.

## Added
- `components/reporting_signals/`: D1 annual damage check, manuscript value audit,
  main-text Fig. 2 and Fig. S8 exporters (see its README). Registered in `components.json`.
- `CHANGELOG_v1.1.md` and `figure_assets/retired_v1.0/`.

## Modified
- `components/airport_review_figures/plot_review_workflow.py`: box 3-4 now lists
  report-volume calibration and coding period (two-line detail; box height +12 pt,
  later elements shifted accordingly; geometry checks unchanged and passing).
- `components/national_profile_figures/plot_national_profiles.py`: footer of the national
  profile figure cites Fig. S3 (formerly Figure S4).
- Both scripts list `Liberation Sans` (metric-compatible with Arial) as a fallback font.
- `figure_correspondence.csv`: current figure numbers, assets, generating entries and the
  v1.0 number of each figure.
- `figure_assets/`: renamed to current numbering; new Fig. 2, Fig. 3, Fig. 7 and Fig. S8.
- `manuscript_binding.json`: hashes of the five revised submission files.
- `release_metadata.json`, `CITATION.cff`: version 1.1.
- `manifest_sha256.csv` and the component manifests of the changed components.

## Figure numbering, v1.0 to v1.1
| v1.0 | v1.1 |
|---|---|
| — | Fig. 2 (new: reporting-system signals) |
| Fig. 2-6 | Fig. 3-7 |
| Fig. S3 | removed (Fig. 2A-B; Table S8) |
| Fig. S4-S8 | Fig. S3-S7 |
| Fig. S9A | Fig. 2C |
| Fig. S9B-C | Fig. S8 (panels A-B) |
| Fig. S10-S12 | Fig. S9-S11 |

Component READMEs, verification records and display-definition files written for v1.0
keep the v1.0 numbering; use the table above.

## Not changed / not claimed
- No event-level rerun. National calibration by year, a categorical-year refit and
  log-scale subtype simultaneous intervals need external inputs that are not bundled.
- No public release, DOI or licence is claimed.

## R5 task-script integration (2026-11-12)

- Copied four supplied round-4 Python scripts unchanged into
  components/reporting_signals/round4/, with an integrated README, requirements and
  the original README retained as UPSTREAM_README.md.
- Registered all four entries; refreshed the component and root integrity manifests.
- Corrected the root README's inherited figure count to seven main and eleven
  supplementary figures; documented the requested v1.0.zip delivery label.
- Kept actual software version 1.1 and existing data/figures.
- Did not apply the year-specification patch to released model files or publish
  external-data analysis results. Integration checks are recorded separately.

- Refreshed stale manuscript bindings for Cover_Letter.docx and Supplementary_Information_RESS_R5_clean.docx to match the actual files in the supplied R5 submission folder. No submission document was edited. Old and new hashes are recorded in r5_packaging_verification.json.
