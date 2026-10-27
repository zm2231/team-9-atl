# NHC HURDAT2 Atlantic best track 1851-2025

- **Source URL(s):** https://www.nhc.noaa.gov/data/hurdat/hurdat2-1851-2025-092326.txt (index: https://www.nhc.noaa.gov/data/hurdat/)
- **Fetched:** 2026-10-27
- **Publisher update date:** Release file dated 2026-09-23; covers through the 2025 season (last record 2025-11-01). 2026 storms are not in HURDAT2 yet; use IBTrACS provisional for Isaias 2026.
- **License / terms:** NOAA/NHC, U.S. Government work (public domain under 17 U.S.C. 105). No separate license text published on the HURDAT page.
- **Terms URL:** https://www.weather.gov/disclaimer
- **Attribution:** Landsea, C. W. and J. L. Franklin (2013): Atlantic Hurricane Database Uncertainty and Presentation of a New Database Format. Mon. Wea. Rev., 141, 3576-3592. Data: NOAA National Hurricane Center HURDAT2.
- **Coverage:** All Atlantic storms (1,988). hurdat2_within300km_ga.csv = the 424 storms with any fix within 300 km of Georgia.
- **Public repo + video safe?** Yes

## Notes

- Parsed to tidy rows with lat/lon signed (W negative), wind radii in nm, -999 = missing.

## Files

### `hurdat2_atl_1851_2025.parquet`: 55,524 rows

Columns: atcf_id, name, date, time, record_id, status, lat, lon, max_wind_kt, min_pres_mb, r34_ne, r34_se, r34_sw, r34_nw, r50_ne, r50_se, r50_sw, r50_nw, r64_ne, r64_se, r64_sw, r64_nw, rmw_nm, in300, dist_ga_km

### `hurdat2_within300km_ga.csv`: 13,873 rows

Columns: atcf_id, name, date, time, record_id, status, lat, lon, max_wind_kt, min_pres_mb, r34_ne, r34_se, r34_sw, r34_nw, r50_ne, r50_se, r50_sw, r50_nw, r64_ne, r64_se, r64_sw, r64_nw, rmw_nm, in300, dist_ga_km
