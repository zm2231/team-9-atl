# Census LEHD LODES8 WAC + RAC 2023, Georgia (block -> 2020 tract)

- **Source URL(s):** https://lehd.ces.census.gov/data/lodes/LODES8/ga/wac/ga_wac_S000_JT00_2023.csv.gz ; https://lehd.ces.census.gov/data/lodes/LODES8/ga/rac/ga_rac_S000_JT00_2023.csv.gz (docs: https://lehd.ces.census.gov/data/lodes/LODES8/LODESTechDoc8.3.pdf)
- **Fetched:** 2026-10-27
- **Publisher update date:** 2023 is the latest year published for GA (directory lists 2021, 2022, 2023); createdate 20251202
- **License / terms:** U.S. Government work (Census Bureau), public domain. Census confidentiality terms apply (no re-identification). LODES values are noise-infused, partially synthetic data.
- **Terms URL:** https://lehd.ces.census.gov/data/ ; https://www.census.gov/about/policies.html
- **Attribution:** U.S. Census Bureau. LEHD Origin-Destination Employment Statistics (LODES8), 2023. Longitudinal-Employer Household Dynamics Program.
- **Coverage:** WAC: 61,542 GA blocks with jobs -> 2,787 tracts, 4,705,268 jobs (C000). RAC: 158,504 blocks -> 2,791 tracts, 4,712,276 resident workers.
- **Public repo + video safe?** Yes

## Notes

- S000 = all jobs segment, JT00 = all job types. WAC = jobs by workplace (daytime presence of workers); RAC = workers by residence.
- Daytime population proxy per tract: ACS total pop - RAC C000 + WAC C000. Workers only, so it ignores students, visitors and retirees.
- LODES8 uses 2020 Census blocks, so GEOID (first 11 digits of the block code) joins directly to the 2020-geography ACS tracts in ../acs/.
- Column codes: C000 total; CA01-03 age; CE01-03 earnings; CNS01-20 NAICS sectors; CR/CT race/ethnicity; CD education; CS sex (CFA/CFS firm age/size are WAC-only). See LODESTechDoc8.3.pdf.
- lehd.ces.census.gov throttled heavily on 2026-10-27 (~3 KB/s, frequent resets). The files were fetched with parallel HTTP range requests and verified with gzip -t.

## Files

### `lodes8_wac_ga_tract_2023.parquet`: 2,787 rows

Columns: GEOID, county_fips, C000, CA01, CA02, CA03, CE01, CE02, CE03, CNS01, CNS02, CNS03, CNS04, CNS05, CNS06, CNS07, CNS08, CNS09, CNS10, CNS11, CNS12, CNS13, CNS14, CNS15, CNS16, CNS17, CNS18, CNS19, CNS20, CR01, CR02, CR03, CR04, CR05, CR07, CT01, CT02, CD01, CD02, CD03, CD04, CS01, CS02, CFA01, CFA02, CFA03, CFA04, CFA05, CFS01, CFS02, CFS03, CFS04, CFS05

### `lodes8_rac_ga_tract_2023.parquet`: 2,791 rows

Columns: GEOID, county_fips, C000, CA01, CA02, CA03, CE01, CE02, CE03, CNS01, CNS02, CNS03, CNS04, CNS05, CNS06, CNS07, CNS08, CNS09, CNS10, CNS11, CNS12, CNS13, CNS14, CNS15, CNS16, CNS17, CNS18, CNS19, CNS20, CR01, CR02, CR03, CR04, CR05, CR07, CT01, CT02, CD01, CD02, CD03, CD04, CS01, CS02

### `ga_wac_S000_JT00_2023.csv.gz`: 61,542 rows

Columns: w_geocode, C000, CA01, CA02, CA03, CE01, CE02, CE03, CNS01, CNS02, CNS03, CNS04, CNS05, CNS06, CNS07, CNS08, CNS09, CNS10, CNS11, CNS12, CNS13, CNS14, CNS15, CNS16, CNS17, CNS18, CNS19, CNS20, CR01, CR02, CR03, CR04, CR05, CR07, CT01, CT02, CD01, CD02, CD03, CD04, CS01, CS02, CFA01, CFA02, CFA03, CFA04, CFA05, CFS01, CFS02, CFS03, CFS04, CFS05, createdate

### `ga_rac_S000_JT00_2023.csv.gz`: 158,504 rows

Columns: h_geocode, C000, CA01, CA02, CA03, CE01, CE02, CE03, CNS01, CNS02, CNS03, CNS04, CNS05, CNS06, CNS07, CNS08, CNS09, CNS10, CNS11, CNS12, CNS13, CNS14, CNS15, CNS16, CNS17, CNS18, CNS19, CNS20, CR01, CR02, CR03, CR04, CR05, CR07, CT01, CT02, CD01, CD02, CD03, CD04, CS01, CS02, createdate

## Other states, WAC only (appended 2026-10-27)

- **Source URL(s):** https://lehd.ces.census.gov/data/lodes/LODES8/<st>/wac/<st>_wac_S000_JT00_2023.csv.gz (and /rac/ for RAC). Same license and attribution as above.
- **Schema:** block files keep the raw columns plus `geo_id` (first 11 digits of `w_geocode`); tract files are block sums keyed by `geo_id` (string). The GA files above use `GEOID` instead.
- **Status:** the server ran at roughly 1-3 KB/s per connection all night. Completed and verified with `gzip -t`: WAC for AZ, CO, FL, IL, LA, NC, PA, SC, WA. **Not fetched:** WAC for CA, NY, TX, and RAC for every non-GA state. Downloads were stopped on purpose; they are not needed.
- **For C3 (SF):** the packet's `employer_blocks` already come from CA LODES WAC (C3 README:688-690), so CA is not blocking.

| File | Rows | Jobs (C000) |
|---|---|---|
| `lodes8_wac_az_block_2023.parquet` | 38,594 | 3,140,901 |
| `lodes8_wac_az_tract_2023.parquet` | 1,757 | 3,140,901 |
| `lodes8_wac_co_block_2023.parquet` | 50,404 | 2,806,464 |
| `lodes8_wac_co_tract_2023.parquet` | 1,442 | 2,806,464 |
| `lodes8_wac_il_block_2023.parquet` | 92,112 | 5,943,827 |
| `lodes8_wac_il_tract_2023.parquet` | 3,257 | 5,943,827 |
| `lodes8_wac_la_block_2023.parquet` | 35,876 | 1,895,919 |
| `lodes8_wac_la_tract_2023.parquet` | 1,375 | 1,895,919 |
| `lodes8_wac_nc_block_2023.parquet` | 74,734 | 4,760,483 |
| `lodes8_wac_nc_tract_2023.parquet` | 2,656 | 4,760,483 |
| `lodes8_wac_sc_block_2023.parquet` | 36,509 | 2,213,437 |
| `lodes8_wac_sc_tract_2023.parquet` | 1,315 | 2,213,437 |
| `lodes8_wac_wa_block_2023.parquet` | 54,421 | 3,519,988 |
| `lodes8_wac_wa_tract_2023.parquet` | 1,771 | 3,519,988 |
| `lodes8_wac_fl_block_2023.parquet` | 137,473 | 9,619,338 |
| `lodes8_wac_fl_tract_2023.parquet` | 5,099 | 9,619,338 |
| `lodes8_wac_pa_block_2023.parquet` | 102,844 | 5,901,664 |
| `lodes8_wac_pa_tract_2023.parquet` | 3,442 | 5,901,664 |
