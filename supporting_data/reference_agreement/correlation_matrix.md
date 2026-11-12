# Full-population Spearman correlation matrix

Reference | O-EB | H-EB | H-EBL | G-EB | G-EBL
--- | --- | --- | --- | --- | ---
O-EB | 1.00000 | 0.99998 | 0.99904 | 0.99766 | 0.99534
H-EB | 0.99998 | 1.00000 | 0.99906 | 0.99769 | 0.99540
H-EBL | 0.99904 | 0.99906 | 1.00000 | 0.99667 | 0.99568
G-EB | 0.99766 | 0.99769 | 0.99667 | 1.00000 | 0.99712
G-EBL | 0.99534 | 0.99540 | 0.99568 | 0.99712 | 1.00000

Main-text link: Section 4.4, close national ordering and differences in review membership. All entries use the same 1,375 airports and geographic outer-test O/E values. O denotes ordinary logistic, H hierarchical logistic and G gradient boosting. EB and EBL information blocks are defined in Table S3. The 602 zero-damage airports are tied at zero under every reference. Off-diagonal values are shown to five decimal places; diagonal self-correlations are one. rank_concordance.csv gives Kendall correlations, decile overlap and the common 144-airport subset. Correlation describes ordering, not probability calibration or airport safety equivalence.

Model identifiers: O-EB = ordinary_EB; H-EB = glmm_EB; H-EBL = glmm_EBL; G-EB = hgb_EB; G-EBL = hgb_EBL.
