# EAGLE-I recorded electricity outages (ORNL/DOE): GA + FL county, 15-minute, 2014-2025, with named-storm summary

- **Source URL(s):** https://doi.org/10.6084/m9.figshare.24237376.v4 (figshare article 24237376, "The Environment for Analysis of Geo-Located Energy Information's Recorded Electricity Outages 2014-2025"). API: https://api.figshare.com/v2/articles/24237376. Files: `https://ndownloader.figshare.com/files/<id>` for eaglei_outages_2014..2025.csv, MCC.csv, coverage_history.csv, DQI.csv. Paper: Brelsford et al., "A dataset of recorded electricity outages by United States county 2014-2022", Scientific Data 11 (2024), https://www.nature.com/articles/s41597-024-03095-5
- **Fetched:** 2026-10-27
- **Publisher update date:** figshare version 4, modified 2026-02-25 ("UPDATE 2/24/2026: Added 2025 outage data.")
- **License / terms:** CC BY 4.0. figshare API `license` field: `{'value': 1, 'name': 'CC BY 4.0', 'url': 'https://creativecommons.org/licenses/by/4.0/'}`. The paper itself: "Open Access This article is licensed under a Creative Commons Attribution 4.0 International License, which permits use, sharing, adaptation, distribution and reproduction in any medium or format, as long as you give appropriate credit to the original author(s) and the source".
- **Terms URL:** https://creativecommons.org/licenses/by/4.0/ ; https://figshare.com/articles/dataset/24237376
- **Attribution:** Source: Brelsford, C., Tennille, S., Myers, A., et al., EAGLE-I Recorded Electricity Outages 2014-2025, Oak Ridge National Laboratory, figshare, doi:10.6084/m9.figshare.24237376.v4 (CC BY 4.0). Changes: filtered to Georgia and Florida, aggregated into storm-window metrics.
- **Coverage:** 226 counties (GA 159, FL 67), 2014-11-01 to 2025-12-31 UTC, 24,839,619 rows. Storm summary: 9 storms x 226 counties = 2,034 rows.
- **Public repo + video safe?** Yes. County aggregates only; credit EAGLE-I/ORNL on screen.

## Notes

- **Times are UTC** (paper: "All data in EAGLE-I is presented in Coordinated Universal Time (UTC)"). Storm windows are local Eastern dates converted to UTC: [start 00:00 ET, end+1 day 00:00 ET).
- **Missing rows mean zero or a collection gap.** Paper: "The provided outage data does not include zero outages/customers out. Missing entries are either a customer outage value of zero or a gap in data collection; we do not distinguish between these cases." In the summary, a 15-minute timestamp where no GA/FL county has any record is treated as a statewide collection gap and forward-filled; other missing county-intervals are treated as 0. Gaps in a single utility's parser are not detectable and read as 0 (this biases restoration times short). Matthew 2016 has 19 statewide-gap intervals (max gap about 5 h); the other storms have none.
- **Denominator.** `peak_share` uses `eaglei_total_customers_2024`, the `total_customers` column EAGLE-I added in the 2024 file (max per county over 2024). It uses the same utility-to-county attribution as `customers_out`. `peak_share_mcc` uses MCC.csv ("the modeled number of electric customers per county as of 2022", Moehl et al.). MCC undercounts many rural GA counties relative to what EAGLE-I attributes there (Clay 1,158 vs 3,825; Webster 988 vs 2,426), giving shares far above 1 under MCC, so MCC is kept only for reference. Even with the 2024 denominator, 13 GA counties exceed 1.0 in Helene (Long 1.81); `share_gt_1` flags them. Treat county shares as approximate and cap at 1 in models.
- **Pre-2018 quality.** No DQI before 2018, and some 2016-2017 values are implausible (e.g. Irma Miami-Dade 1.78M out; FL sum of county peaks 10.6M, which exceeds FL customers). `data_quality_era` flags Matthew and Irma rows.
- **Restoration metric.** `hours_peak_to_90pct_restored` = hours from the in-window peak to the first interval at or below 10% of that peak, searching up to 7 days after the window end. `restore_censored` = not reached. Windows overlap for Helene and Milton (2024-10-08..10-10).
- `hours_above_10pct` = 0.25 h x number of in-window intervals with customers_out >= 10% of `eaglei_total_customers_2024`.
- The national yearly CSVs (about 12.4 GB total) were streamed through `grep '^(fips_code|1[23][0-9]{3}),'` and never stored. The 2025 file names the outage column `sum` instead of `customers_out`; it was mapped to `customers_out`. No duplicate (fips, run_start_time) keys in GA/FL. The filtered intermediate CSVs were deleted after the parquet build; rebuild by re-running the scripts.
- Scripts: `/private/tmp/claude-501/-Volumes-4-GitHub-google-hackathon/dd49bbac-d7fb-47f1-aad6-f95ffe1e01f3/scratchpad/outages/fetch.sh` and `build_eaglei.py` (session scratchpad).

## Files

### `ga_fl_outages_15min.parquet` (24,839,619 rows, 97 MB)

Columns: fips, county, state, run_start_time (UTC), customers_out. Only nonzero records, as published.

### `ga_fl_storm_outage_summary.parquet` (2,034 rows)

One row per storm x county (all 226 GA/FL counties, including zero-outage ones). Storms: Matthew 2016-10-06..10-12, Irma 2017-09-09..09-20, Michael 2018-10-09..10-20, Dorian 2019-09-02..09-08, Ian 2022-09-27..10-05, Idalia 2023-08-29..09-05, Debby 2024-08-04..08-12, Helene 2024-09-25..10-10, Milton 2024-10-08..10-15.

Columns: storm, window_start_local, window_end_local, fips, county, state, mcc_customers, n_records_window, peak_customers_out, peak_time_utc, eaglei_total_customers_2024, peak_share_mcc, peak_share, share_gt_1, hours_above_10pct, hours_peak_to_90pct_restored, restore_censored, data_quality_era

### `ga_fl_county_customers.parquet` (226 rows)

Columns: fips, county, state, mcc_customers (MCC.csv, 2022 modeled), eaglei_total_customers_2024

### `raw/MCC.csv`, `raw/coverage_history.csv`, `raw/DQI.csv`

Supplementary files as published (national).
