# Auxiliary source scope

This entry measures local classifier confidence and audits acquisition dates, forecasts, hourly precipitation and the available activity table. These sources supply measurement context. The conditional-damage model uses its separate national input set.

## Run

Verification used Python 3.12.14 and the package versions in `requirements.txt`. Rasterio used GDAL 3.12.2. Copy `source_inputs.template.json` and bind the airport reference, confidence archive, thirteen Sentinel archives, nineteen forecast workbooks, eighty-eight precipitation workbooks and activity table. Relative paths resolve against the JSON file. Source labels identify the retained data layout; they are not local absolute paths.

```text
python audit_source_scope.py --inputs source_inputs.json --output OUTPUT/source_scope
```

Use a new or empty output directory. Source files are read-only. The entry records complete input hashes, code hashes and package versions. It performs local reads without downloads. The input set totals 21.77 GB. Every worksheet used by the audit is read again; saved audit tables are not inputs to this entry.

## Confidence denominators

For each target airport, local azimuthal equidistant buffers of 3, 8 and 13 km are transformed to the raster CRS. Polygon boundaries use 180 segments per quadrant. Rasterization selects pixel centres, with `all_touched=False`. The outer buffer supplies the cropped array. Statistics use unmasked values from 1 through 100, inclusive. Mean, median, tenth percentile and percentage below 50 have this valid-pixel denominator. The valid percentage instead divides valid pixels by all selected buffer pixels.

The product metadata describes values above 100 as locations with additional interpretation procedures and separately identifies 250 as NoData. Excluded values must not all be labelled low confidence or missing. The index is not externally validated classification accuracy, land-cover change or damage probability. The below-50 percentage is a descriptive summary, not a validated intervention threshold.

## Source roles

Sentinel dates come from each archive's product XML. All thirteen acquisitions are in 2026, after the 2015-2025 outcome window. Only metadata are interpreted; images are not classified.

Forecast files retain station, reference time, valid time, altitude fields, lead values and duplicate keys. All eleven supplemental JFK exports have their unique station/reference/valid keys inside the corresponding primary export. Key inclusion does not establish equality of every meteorological value. The supplemental files are not concatenated into the primary export. Forecasts remain separate from observed surface conditions.

The eighty-eight hourly precipitation workbooks are read for dates, station labels, invalid timestamps, missing or negative values and duplicate keys. File coverage does not establish timezone provenance. These values remain outside incident matching; the surface-weather route uses its own verified timestamp evidence.

The HTML activity table has an XLS suffix. It contains 61,958 rows: 26,857 monthly classification rows, 35,100 subtotals and 1 grand total. Detail rows cover 132 months for DEN. Neither table rows nor subtotal rows are individual flights or strike events. No movement total is estimated by summing this mixed table. DEN coverage cannot provide a common eight-airport incidence denominator.

## Verification scope

Twenty-four confidence summaries, thirteen acquisition records, nineteen forecast audits and eighty-eight precipitation audits matched the retained tables in values, categories, missingness and data types. Activity-table structure and retained date previews also matched. Additional row classification separates activity detail and totals. Input hashes, source file sizes and modification times remained unchanged for all 123 files.

Checks covered confidence denominators and nested ranges, source years, forecast leads and export overlap. Duplicate references, duplicate source files, a mismatched activity source and an existing output directory were rejected. Execution used relocated code and an empty working directory on the same host. No model was fitted or resampling performed. A clean installation and complete national raster extraction are separate verification tasks.
