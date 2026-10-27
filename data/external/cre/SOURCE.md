# Census Community Resilience Estimates (CRE) 2024 + CRE for Heat 2022, tract level

- **Source URL(s):** CRE 2024 tract: https://www2.census.gov/programs-surveys/demo/datasets/community-resilience/2024/CRE_24_Tract.csv ; CRE 2024 percentile rankings (tract): https://www2.census.gov/programs-surveys/demo/datasets/community-resilience/2024/CRE_24_Rankings_Tract.csv ; CRE for Heat 2022 tract: https://www2.census.gov/programs-surveys/demo/datasets/community-resilience/2022/heat/CRE22_Heat_Tract.csv ; layouts: https://www2.census.gov/programs-surveys/demo/technical-documentation/community-resilience/2024/cre_file_layout_2024.pdf , https://www2.census.gov/programs-surveys/demo/technical-documentation/community-resilience/2024/cre_rankings_file_layout_2024.pdf , https://www2.census.gov/programs-surveys/demo/datasets/community-resilience/2022/heat/CRE_Heat_2022_File_Layout.pdf ; landing pages https://www.census.gov/programs-surveys/community-resilience-estimates.html , https://www.census.gov/data/experimental-data-products/cre-heat.html (www.census.gov returned 520/524 from here; heat URLs found via search of that page and the www2 index)
- **Fetched:** 2026-10-27 ~02:55 EDT
- **Publisher update date:** CRE_24_Tract.csv Last-Modified 2026-01-29 (layout dated January 29, 2026); CRE22_Heat_Tract.csv 2024-07-16 (released July 16, 2024). CRE for Heat 2022 is the latest heat edition (www2 `2023/heat/` → 404; the 2024 directory has no heat folder).
- **License / terms:** U.S. Government work. No dataset-specific license. Census Bureau policy DS027 (https://www2.census.gov/foia/ds_policies/ds027.pdf): "Data/works created by Census Bureau employees generally are not subject to copyright protection within the United States. Census Bureau data or other works may be subject to copyright protection in foreign countries."
- **Terms URL:** https://www.census.gov/about/policies/citation.html ; https://www2.census.gov/foia/ds_policies/ds027.pdf
- **Attribution:** Source: U.S. Census Bureau, 2024 Community Resilience Estimates and 2022 Community Resilience Estimates for Heat (experimental), accessed 2026-10-27
- **Coverage:** National files: 84,415 tracts (2020 tract GEOIDs). Filtered parquet: tracts in GA, CA, FL, LA, NC, NY, SC, TX, IL, WA, CO, PA, AZ (46,482 tracts; GA 2,796).
- **Public repo + video safe?** Yes

## Notes

- `geo_id` = last 11 characters of `GEO_ID` (`1400000US` + 11-digit tract). Asserted that `geo_id[:2] == STATE` for every row.
- Upstream CSVs are cp1252-encoded (e.g. "Doña Ana"), not UTF-8. The two full national CSVs here are byte-identical copies of upstream.
- CRE counts individuals by number of "components of social vulnerability" (0, 1–2, 3+). `PRED3_PE` = % with 3+ components; `_M`/`_PM` = 90% margins of error. `POPUNI` excludes residents of adult correctional/juvenile facilities and college dorms.
- 2024 CRE has `WATER_TRACT` (1 = water-only tract; 149 in target states) and `CBSA`.
- Heat 2022 adds tract-level `LONG_90_DAY` (longest run of days ≥90°F in 2022), `MAX_WBT` (max wet-bulb temp 2022), `EXPOSED` (1 = ≥2 consecutive days ≥90°F or wet-bulb ≥80°F). In GA, 2,783 of 2,796 tracts are EXPOSED=1. Heat uses its own AC-adjusted vulnerability model, so its PRED* columns differ from general CRE.
- Rankings file: national/within-state percentile ranks of `PRED3_PE` plus hazard-conditional ranks (winter weather, strong wind, hurricane, earthquake, wildfire, flood) and FEMA NRI Expected Annual Loss ratings (`*_EALR`). Missing values are coded **-888888888** (per rankings layout); hazard ranks are missing where the tract's risk is below "Relatively Moderate".
- The national rankings CSV (54 MB) is not copied; only the target-state parquet. The national tract and heat CSVs (~13 MB each) are included.
- Built by `scripts_a/build_places_cre.py` (session scratchpad).

## Files

### `CRE22_Heat_Tract.csv`: 84,415 rows, 21 columns

Columns: GEO_ID, STATE, COUNTY, TRACT, NAME, POPUNI, PRED0_E, PRED0_M, PRED0_PE, PRED0_PM, PRED12_E, PRED12_M, PRED12_PE, PRED12_PM, PRED3_E, PRED3_M, PRED3_PE, PRED3_PM, LONG_90_DAY, MAX_WBT, EXPOSED

### `CRE_24_Tract.csv`: 84,415 rows, 20 columns

Columns: GEO_ID, STATE, COUNTY, TRACT, CBSA, NAME, WATER_TRACT, POPUNI, PRED0_E, PRED0_M, PRED0_PE, PRED0_PM, PRED12_E, PRED12_M, PRED12_PE, PRED12_PM, PRED3_E, PRED3_M, PRED3_PE, PRED3_PM

### `CRE_Heat_2022_File_Layout.pdf`

Documentation (151 KB).

### `cre_2024_rankings_tract_targets.parquet`: 46,482 rows, 66 columns

Columns: geo_id, GEO_ID, STATE, COUNTY, TRACT, NAME, REGION, DIVISION, POPUNI, PRED3_PE, PRED3_PM, PCT3, PCT3_LB, PCT3_UB, PCT3_1K, PCT3_1K_LB, PCT3_1K_UB, PCT3_ST, PCT3_ST_LB, PCT3_ST_UB, PCT3_1K_ST, PCT3_1K_ST_LB, PCT3_1K_ST_UB, WINTW_PCT3, WINTW_PCT3_LB, WINTW_PCT3_UB, WINTW_PCT3_1K, WINTW_PCT3_1K_LB, WINTW_PCT3_1K_UB, WINTW_EALR, SWND_PCT3, SWND_PCT3_LB, SWND_PCT3_UB, SWND_PCT3_1K, SWND_PCT3_1K_LB, SWND_PCT3_1K_UB, SWND_EALR, HRCN_PCT3, HRCN_PCT3_LB, HRCN_PCT3_UB, HRCN_PCT3_1K, HRCN_PCT3_1K_LB, HRCN_PCT3_1K_UB, HRCN_EALR, ERQK_PCT3, ERQK_PCT3_LB, ERQK_PCT3_UB, ERQK_PCT3_1K, ERQK_PCT3_1K_LB, ERQK_PCT3_1K_UB, ERQK_EALR, WFIR_PCT3, WFIR_PCT3_LB, WFIR_PCT3_UB, WFIR_PCT3_1K, WFIR_PCT3_1K_LB, WFIR_PCT3_1K_UB, WFIR_EALR, FLD_PCT3, FLD_PCT3_LB … (66 total)

### `cre_2024_tract_targets.parquet`: 46,482 rows, 21 columns

Columns: geo_id, GEO_ID, STATE, COUNTY, TRACT, CBSA, NAME, WATER_TRACT, POPUNI, PRED0_E, PRED0_M, PRED0_PE, PRED0_PM, PRED12_E, PRED12_M, PRED12_PE, PRED12_PM, PRED3_E, PRED3_M, PRED3_PE, PRED3_PM

### `cre_file_layout_2024.pdf`

Documentation (134 KB).

### `cre_heat_2022_tract_targets.parquet`: 46,482 rows, 22 columns

Columns: geo_id, GEO_ID, STATE, COUNTY, TRACT, NAME, POPUNI, PRED0_E, PRED0_M, PRED0_PE, PRED0_PM, PRED12_E, PRED12_M, PRED12_PE, PRED12_PM, PRED3_E, PRED3_M, PRED3_PE, PRED3_PM, LONG_90_DAY, MAX_WBT, EXPOSED

### `cre_rankings_file_layout_2024.pdf`

Documentation (158 KB).

