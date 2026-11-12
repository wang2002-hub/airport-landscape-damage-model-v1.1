# Auxiliary sensitivity models

This component fits eight specified sensitivity scenarios with four information blocks each. It uses the same hierarchical model, preprocessing and calibration code as the reference analysis. The configurations retain their original definitions. They are not additional experiments selected after this verification.

## Run

Same-host verification used Python 3.12.14 and the versions in `requirements.txt`. Supply the final analytic event table and the retained airport-year environmental panel. The event table must include its original damage extent, completeness, target status, coordinates and environmental fields.

```text
python fit_sensitivity.py --data DATA/analysis_events.parquet --environment DATA/environment.parquet --output OUTPUT/sensitivity
```

Use `--scenario` to run one named scenario and `--block` to run one of E, EL, EB or EBL. Defaults run all 32 configurations. Every invocation requires a new or empty output directory. It records input/code hashes, runtime versions, scenario membership, fit diagnostics and task status. Failed fits retain their logs and cause a nonzero final exit code. Completed outputs are preserved.

## Scenario definitions

| Scenario | Definition |
| --- | --- |
| exclude_M_question | Remove damage reports whose recorded extent is undetermined, then refit. |
| label70 | Retain airport-years with known, internally consistent labels for at least 70% of near-airport reports. |
| label80 | Apply the corresponding 80% completeness threshold. |
| contemporary2016 | Use same-year maps for reports from 2016 onward within the common map-comparison collection. |
| lagged | Use the preceding map year within that same collection. |
| fixed2015 | Use 2015 map measurements within that same collection. |
| ilr | Represent nine land-cover proportions by eight isometric log-ratio coordinates. |
| buffer50 | Exclude national-source airports within 50 km of any target airport. |

Training uses national reports through 2022. Calibration uses 2023; national testing uses 2024–2025. Target airports remain outside these sets. Landscape blocks use the fixed 3 km disc for these sensitivity fits. No new landscape-scale search is performed. ILR uses the original 1e-6 zero replacement and renormalization; its original correlation-screening setting is preserved.

The three map scenarios share the intersection of complete, eligible event measurements. Even the blocks that omit landscapes use this intersection for that comparison. Previous-year alignment describes retrospectively available products. It does not establish real-time product availability. The spatial rule uses the original great-circle approximation and a strict distance below 50 km.

## Verified populations

Each row applies to all four information blocks in its scenario. Populations overlap across scenarios and blocks; their row counts are not independent sample sizes.

| Scenario | Training | Calibration | National test | Targets |
| --- | --- | --- | --- | --- |
| exclude_M_question | 28,911 | 4,380 | 10,573 | 5,684 |
| label70 | 27,628 | 4,180 | 10,485 | 5,623 |
| label80 | 23,141 | 3,288 | 8,953 | 3,429 |
| contemporary2016 | 26,207 | 4,616 | 11,124 | 5,451 |
| lagged | 26,207 | 4,616 | 11,124 | 5,451 |
| fixed2015 | 26,207 | 4,616 | 11,124 | 5,451 |
| ilr | 30,427 | 4,616 | 11,124 | 5,936 |
| buffer50 | 28,247 | 4,319 | 10,423 | 5,936 |

Membership records include counts, damage counts, airport counts and hashes of sorted event identifiers. They provide alignment checks without distributing event-level identifiers in this component.

## Interpretation and verification

The M? scenario combines a changed collection with a refitted model. It is distinct from restricting the collection under a frozen reference. Their comparison can describe these changes but does not causally separate coding behavior from model error. Completeness thresholds and spatial exclusions also change the study collection. The three common-population map scenarios answer a narrower matched comparison.

Relocated replay completed 32 hierarchical fits and 32 calibrations. All 511,564 prediction rows matched the retained outputs exactly. Fit metadata, preprocessing selections, calibration parameters and sample counts matched, excluding execution time. The target-distance audit matched all 1,383 airports. All three map scenarios had identical event sets within each evaluation partition.

Duplicate events, duplicate environmental keys and existing output directories were rejected. Original inputs remained unchanged. The verification used the same host and an empty working directory. It is component-level reproduction; a clean installation, new scientific replication and full raw-raster reconstruction were not performed here.
