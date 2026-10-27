# 2020 Census group quarters population by major type (PL 94-171 table P5), tracts in 13 target states + GA blocks

- **Source URL(s):** Census Data API, 2020 Decennial PL 94-171: `https://api.census.gov/data/2020/dec/pl?get=group(P5)&for=tract:*&in=state:<FIPS>` (API key used at fetch time, not recorded) ; variable labels https://api.census.gov/data/2020/dec/pl/groups/P5.json ; GA blocks from the PL 94-171 summary file https://www2.census.gov/programs-surveys/decennial/2020/data/01-Redistricting_File--PL_94-171/Georgia/ga2020.pl.zip (geo header `gageo2020.pl` + segment 3 `ga000032020.pl`)
- **Fetched:** 2026-10-27 ~03:00–03:20 EDT
- **Publisher update date:** 2020 Census Redistricting Data (PL 94-171), released August 12, 2021 (ga2020.pl.zip Last-Modified 2021-08-12)
- **License / terms:** U.S. Government work. Census Bureau policy DS027 (https://www2.census.gov/foia/ds_policies/ds027.pdf): "Data/works created by Census Bureau employees generally are not subject to copyright protection within the United States. Census Bureau data or other works may be subject to copyright protection in foreign countries." The Census API Terms of Service (https://www.census.gov/data/developers/about/terms-of-service.html) ask apps that call the API to show an attribution notice. This kit ships a static extract and does not call the API at runtime.
- **Terms URL:** https://www.census.gov/data/developers/about/terms-of-service.html ; https://www.census.gov/about/policies/citation.html
- **Attribution:** Source: U.S. Census Bureau, 2020 Census Redistricting Data (Public Law 94-171) Summary File, Table P5 Group Quarters Population by Major Group Quarters Type, accessed 2026-10-27
- **Coverage:** All 2020 tracts in GA, CA, FL, LA, NC, NY, SC, TX, IL, WA, CO, PA, AZ (46,482). GA blocks: only blocks with GQ population > 0 are kept.
- **Public repo + video safe?** Yes

## Notes

- Column mapping (labels from P5.json): gq_total = P5_001N; gq_inst_total = P5_002N (institutionalized); gq_inst_correctional_adults = P5_003N; gq_inst_juvenile = P5_004N; gq_inst_nursing_skilled = P5_005N (nursing/skilled-nursing facilities); gq_inst_other = P5_006N; gq_noninst_total = P5_007N; gq_noninst_college_housing = P5_008N; gq_noninst_military_quarters = P5_009N; gq_noninst_other = P5_010N (shelters, group homes, workers' dorms, etc.).
- Checks that passed: gq_total = inst + noninst; inst = sum of its 4 subtypes; GA tract values from the www2 PL file equal the API values in every column; GA block sums equal the tract totals.
- `geo_id` = 11-digit tract; `block_geoid` = 15-digit block (GA file). API `*NA` annotation columns dropped.
- PL 94-171 numbers carry 2020 differential-privacy noise, which is worst at block level, so treat small block counts as approximate.
- Use with nursing-home/correctional/college points for evacuation or heat-vulnerability weighting (C1/C4).
- Built by `scripts_a/gq_api.sh`, `scripts_a/pl_ga_blocks.py`, `scripts_a/build_gq.py` (session scratchpad).

## Files

### `gq_p5_2020_block_ga_nonzero.parquet`: 2,208 rows, 13 columns

Columns: block_geoid, geo_id, GEO_ID, gq_total, gq_inst_total, gq_inst_correctional_adults, gq_inst_juvenile, gq_inst_nursing_skilled, gq_inst_other, gq_noninst_total, gq_noninst_college_housing, gq_noninst_military_quarters, gq_noninst_other

### `gq_p5_2020_tract_targets.parquet`: 46,482 rows, 15 columns

Columns: geo_id, GEO_ID, state, county, tract, gq_total, gq_inst_total, gq_inst_correctional_adults, gq_inst_juvenile, gq_inst_nursing_skilled, gq_inst_other, gq_noninst_total, gq_noninst_college_housing, gq_noninst_military_quarters, gq_noninst_other

