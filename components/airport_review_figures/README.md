# Airport review figures

Run each command with a new output directory:

```
python plot_airport_comparisons.py --config airport_inputs.json --output airport-figures
python plot_review_workflow.py --config workflow_inputs.json --output review-workflow
python plot_volume_calibration.py --config volume_inputs.json --output volume-figure
```

Inputs are included aggregate display tables, verified by SHA256. Relative paths
resolve against the config directory. Figure mapping identifies current Figures
3, 5, 6 and S3. Public filenames describe their purpose. Output includes editable
PDF/SVG and 600-dpi PNG/TIFF; previews are 300 dpi.

Figure 3 distinguishes absolute and relative airport ratios, pointwise intervals,
simultaneous intervals and the selected pooled comparison. Each airport enters
that pool. Figure 5 preserves the same report population for damage-extent
partitioning. Its pooled pointwise intervals and sixteen-member airport/subtype
simultaneous family are different uncertainty summaries.

Figure 6 is a proposed retrospective review workflow. Follow-up branches may
overlap. It does not demonstrate operational benefit or prospectively validated
thresholds. The JFK illustration is checked against included counts and intervals.
Figure S3 shows observed/predicted marginal pointwise intervals across fixed
report-count groups. These summaries do not identify selection of unreported
events. Paired gap computations are supplied by report_volume_calibration.

No model is refitted and no data are newly sampled by these exporters. Existing
results were viewed before packaging. Plot-area alignment or workflow text-box
geometry is checked before export. Final PDF text, collisions and visual review
are release checks beyond successful rendering. The manuscript and peer-review
documents are not needed to run these scripts and are excluded from this module.
