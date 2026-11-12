# Spatial context diagnostics

This component reconstructs wetland/deepwater, source-vintage and runway-geometry diagnostics for the eight target airports. These measurements supply local spatial context. They are separate from the national damage-prediction inputs and do not estimate ecological effects on recorded damage.

## Run

Same-host verification used Python 3.12.14 and the versions in `requirements.txt`. The tested pyogrio runtime uses GDAL 3.12.4. Copy `spatial_inputs.template.json` and bind the airport reference, 2025 environmental panel, runway-vector inventory and eight GeoPackages. Relative paths resolve against the JSON file. Each GeoPackage entry identifies its wetland and source-project metadata layers explicitly.

```text
python audit_spatial_context.py --inputs spatial_inputs.json --output OUTPUT/spatial
```

Use a new or empty output directory. The entry checks actual layer coordinates against configured coordinate systems before calculation. It records full source-file hashes, source-code hashes and runtime versions. The supplied GeoPackages are read-only inputs. Their combined size is approximately 35 GB; hashing and geometry processing require substantial local disk reads. No downloads are performed by this entry.

## Geometry and source years

Each airport uses a local azimuthal equidistant coordinate system centred on its reference point. The 13 km circular polygon has 180 segments per quadrant. Area percentages use this projected polygon's area. Invalid input polygons are repaired using the retained geometry rule, then transformed and clipped. Union area prevents double counting within each reported union.

Wetland/deepwater classes are reported both together and by supplied type. Their taxonomy differs from the annual land-cover wetland class. The displayed 2025 land-cover percentages are contextual comparisons, not a validation against an equivalent classification system.

Source-project footprints are intersected with the local circle and wetland union. All recorded image-year labels and positive polygon/project overlaps are retained, including small overlaps. The analysis does not replace those years with the download year or infer a single dominant vintage. Overlap rows may refer to overlapping project footprints and must not be summed as independent areas.

Runway-tagged geometry is transformed into local coordinates. The maximum reference distance uses its retained vertices. It describes supplied geometry rather than historical runway use, flight movements or bird-strike locations. The 3, 8 and 13 km circles in the diagnostic plot are spatial guides.

## Outputs and verified scope

The replay matched five retained tables: 8 airport summaries, 49 type rows, 34 project rows, 15,841 polygon-vintage overlaps and 8 runway summaries. All numeric values agreed within 1e-10, with matching categories, missingness and row order. The 34 project-footprint features and their coordinates also matched.

The diagnostic PNG reproduced the retained pixels and dimensions exactly. A PDF was also exported, and the preview was visually inspected. The neutral `spatial_context_diagnostic` basename identifies an auxiliary check; it assigns no new manuscript figure number.

Area denominators, project-year labels and overlap fractions were independently checked. Duplicate target references, duplicated layer definitions, mismatched coordinate systems and existing output directories were rejected. Complete pre-read and post-run hashes matched for all eleven source files, including the eight GeoPackages. The source file sizes and modification times also remained unchanged.

Execution used relocated code, an empty working directory and the same local environment. No model was fitted and no random sample was drawn. A clean GIS installation and a complete national raster reconstruction were not tested here.
