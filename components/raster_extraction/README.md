# Raw landscape extraction

This entry computes landscape measurements from explicit raster and accepted geometry inputs. It does not fit damage models. Extraction runs in a new directory and recomputes every selected airport; existing caches are never substituted for computation.

## Inputs and execution

The verified environment uses Python 3.12.14, GDAL 3.12.4 and the versions in `requirements.txt`. Copy `raster_inputs.template.json` and bind the extracted rasters, airport buffers, airport rings and DEN reference alternatives. Configure `gdal_library` as the actual compatible GDAL shared-library file. The library's dependent files must be available to the operating system. The tested Windows runtime loads these through pyogrio. Installing another platform or mixing GDAL builds requires separate verification.

```text
python extract_landscape.py --inputs raster_inputs.json --output OUTPUT/landscape
```

Relative paths resolve against the JSON file. The template uses neutral raster filenames. D02 denotes annual land cover, D03 annual imperviousness, D04 tree canopy and D05 land-cover change. Supply eleven D02 and eleven D03 rasters for 2015-2025, three D04 rasters for 2015, 2020 and 2025, and the 2025 D05 raster. Input hashes identify the exact retained products. Raster files occupy approximately 39.13 GB after extraction from the data archives. The code reads selected windows rather than loading entire national rasters into memory.

The `airports` list selects geometry identifiers. The verified list contains all eight target airports and `KDEN_ALT`. The alternative is derived from the second row of the supplied DEN reference-alternatives table, preserving the retained design. It is a reference-point sensitivity location, not an additional study airport.

## Geometry and measurement rules

Inputs retain the accepted buffer and ring geometries. The six zones are 0-3, 3-8 and 8-13 km rings plus cumulative 3, 8 and 13 km buffers. Geometry and raster coordinate systems are checked. Annual land-cover, imperviousness and change rasters must share the retained grid; the landscape-structure calculations require 30 m pixels. Canopy measurements use each canopy raster's own grid.

Centre-based masks partition the cumulative 13 km buffer without overlap. All-touched masks are calculated separately. Histograms retain the raster codes, including missing-data codes; valid-class summaries belong to the downstream environmental-panel component. The original sixteen land-cover classes and their groupings are preserved.

Landscape structure uses valid land-cover pixels. Edge density counts each unlike neighbouring horizontal or vertical pair once, excluding outer and missing-data edges. Largest patches use eight-neighbour connectivity. Annual transition matrices use common valid pixels. The twelve year pairs comprise ten consecutive-year pairs and 2015-2020 and 2020-2025. Transition marginals are checked during extraction. The 2025 change product is compared with its expected encoding from 2024 and 2025 land cover.

The DEN alternative uses geodesic circles sampled at 0.5-degree azimuth intervals, followed by transformation into the accepted geometry CRS. Its projected areas are retained in square kilometres. This source design remains separate from other local context diagnostics that use local equidistant circles.

## Outputs and checks

Each selected location produces a compressed array file with 23 fields. These cover masks, centre/all-touched histograms, canopy counts, geometry areas, landscape structure, transitions, common imperviousness and change-product checks. DEN locations also export three land-cover windows. Logs record source hashes, runtime metadata, synthetic checks, raster metadata and computation times. The alternative geometry is recorded as WKB with its coordinate system.

Same-host verification independently extracted all eight targets and the DEN alternative from the original raster pixels. All 862,920 numeric entries were compared with retained caches. Integer arrays, shapes, data types and missingness matched. Eight target locations matched exactly. The alternative differed only in six projected-area values, with maximum absolute difference 3.98e-12 square kilometres, below the specified 1e-10 tolerance. Its pixel-based measurements matched.

Synthetic checks verify diagonal connectivity, missing-data edge exclusion, entropy and edge-density calculations, and the distinction between centre and all-touched masks. Invalid product-year duplication, repeated airport selections and existing output directories are rejected. Cache reuse is disabled. The unchanged calculation functions were compared structurally with the retained implementation.

Twenty-nine staged source files retained identical complete hashes after execution. Archive members were read fully with ZIP checksum validation during staging; archive sizes and modification times remained unchanged. The complete archive files were not rehashed after extraction. Verification used relocated code and an empty working directory on the same host. It does not establish a clean installation or a fresh extraction of every national airport. No model was fitted and no random sample was drawn.
