# Environmental panel reconstruction

This component builds airport-year environmental panels from zonal measurements, landscape structure and common-pixel transition summaries. It retains the original numerical definitions. The main panel has 1,581 airport references, eleven years and 285 fields. These environmental references precede outcome screening. They are distinct from the 1,383 airports in the final analytic cohort.

## Run

Same-host verification used Python 3.12.14 and the versions in `requirements.txt`. Copy `environment_inputs.template.json` and replace its four paths with the retained input files. Relative paths resolve against that JSON file. Use a new or empty output directory.

```text
python rebuild_environment_panel.py --inputs environment_inputs.json --output OUTPUT/environment
```

The program records input and code hashes, package versions and failures. It writes the same-year panel, previous-year panel, landscape changes and a summary. The template describes input roles; it does not contain measurements.

## Measurement and timing rules

Six zones comprise cumulative 3, 8 and 13 km discs and three disjoint rings. Coverage uses valid 30 m pixel area divided by geometric area, capped at one. Primary eligibility requires at least 95% land-cover and impervious coverage in every ring. The 90% flags remain available for sensitivity analysis. The separate reference-identity exclusion is preserved.

Nine land-cover groups sum to one where land-cover pixels are observed. Zero valid coverage produces missing proportions rather than zeros. Imperviousness uses valid 0–100 values. Canopy values exist only for 2015, 2020 and 2025. Unobserved canopy years remain missing. Changes in 2015 remain missing because no preceding map is supplied.

Two-year common-pixel changes retain a different denominator from differences between separately measured annual proportions. The panel preserves both quantities. The previous-year panel moves the event-year key forward by one while retaining the actual map year. This is a retrospective alignment of later-released products; it does not establish historical real-time availability.

## Verified scope

The rebuilt same-year panel has 17,391 rows. The previous-year panel has 15,810 rows. Both retain 285 fields. The change table has 113,832 rows. Keys, categories and missingness matched the retained inputs. Across 10,112,076 numeric comparisons, the maximum absolute difference was below 3e-14, within the declared 1e-10 tolerance. These small differences arise in reconstruction from stored floating-point tables. The existing model input was preserved.

All eight target airports were checked against retained extraction caches. The checks covered 15,144 numeric values, with maximum difference below 8e-15. They test the relationship between saved pixel summaries and measurements. They are not a new raw-raster extraction.

Composition corruption, missing zones and incorrect coverage denominators were rejected. A nonempty output directory was protected. Execution used relocated code and an empty working directory on the same host. A clean installation and a complete raw-data extraction were not tested in this component.

## Raw-source boundary

The source inventory contains eleven annual land-cover maps, eleven impervious maps, three canopy maps and one 2025 land-change map. All 26 exact basenames were located in local archive member inventories. Their old direct filesystem paths are absent. Archive-member presence is distinct from decompression, content-hash verification and extraction replay.

`raw_rasters.template.json` supplies neutral source-location placeholders for future extraction integration. It is documentation, not an extraction command. The historical raster route also needs accepted airport geometries, grid alignment, pixel inclusion rules and the GIS runtime. Its GDAL loader uses a Windows DLL from the pyogrio distribution. These dependencies must be resolved explicitly before claiming portability.

The 2025 land-change map supports a separate consistency audit. Its stored archive is `03d_raw_landcover_change_2025.zip`. It is not a conditional-damage predictor. An environment-panel replay can start from the four measured input tables without that map. A complete replay of the historical raster consistency check requires it. This distinction should remain explicit in the integrated data-package map.
