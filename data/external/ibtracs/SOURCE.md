# NOAA IBTrACS v04r01, North Atlantic, storms near Georgia (300 km and 800 km extracts)

- **Source URL(s):** https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv/ibtracs.NA.list.v04r01.csv
- **Fetched:** 2026-10-27
- **Publisher update date:** File Last-Modified 2026-10-25; last observation 2026-10-22 18:00 UTC (2026 storms are TRACK_TYPE=PROVISIONAL)
- **License / terms:** NOAA/NCEI data, U.S. Government work. NCEI: IBTrACS follows the World Data Center for Meteorology policy of "full and open access to the data"; "We also use the World Meteorological Organization's Resolution 40 policy as the guide for commercial use of IBTrACS data."
- **Terms URL:** https://www.ncei.noaa.gov/products/international-best-track-archive
- **Attribution:** NOAA's International Best Track Archive for Climate Stewardship (IBTrACS) data, accessed on 2026-10-27. Cite Knapp et al. (2010, BAMS) and Gahtan et al. (2024), doi:10.25921/82ty-9e16.
- **Coverage (800 km extract, fetched 2026-10-27 15:43 UTC, same file Last-Modified 2026-10-25):** 731 storms (1851-2026; 209 from 1980 on) whose track passed within 800 km of Georgia's centroid (-83.4325, 32.6389; Census cb_2024_us_state_20m, EPSG:5070 area centroid) or had a track point inside the FL, GA, SC or AL state polygon. 44,489 points, 1851-08-16 to 2026-10-11 12:00 UTC.
- **Coverage (300 km extract):** 459 storms (1851-2026) with at least one track point inside a 300 km buffer of the Georgia state polygon (Census cb_2024 20m, EPSG:5070). All track points of those storms are kept.
- **Public repo + video safe?** Yes

## Notes

- in300 = this point lies inside the 300 km buffer; dist_ga_km = distance from the point to the Georgia polygon (0 = inside GA).
- 2026 storms in the extract: BERTHA (closest 237 km), EDOUARD (261 km), ISAIAS (2026-10-04 to 10-11, closest 101.6 km, max USA_WIND 105 kt), all PROVISIONAL.
- The full NA CSV (57.6 MB) was deleted after filtering. Re-fetch it from the URL above.
- 800 km extract: every point of a selected storm is kept. Columns are the IBTrACS core columns plus every USA_* column (NHC best track: wind, pressure, SSHS, R34/R50/R64 quadrant radii in nmile, POCI, ROCI, RMW, eye, gust, sea-height radii). Other agencies' columns are dropped (blank for NA). Wind radii are present on 5,393 points / 128 storms (first season with radii: 2001). Blank IBTrACS cells are null.
- Added columns: dist_ga_centroid_km (Albers EPSG:5070 distance to the GA centroid), dist_ga_km (distance to the GA polygon, 0 inside), state (state polygon containing the point among GA, FL, SC, AL, NC, TN, MS; null at sea or elsewhere), within800 (point within 800 km of the centroid), sel_within800 / sel_landfall_fl_ga_sc_al (why the storm was selected). Only 5 storms qualify by landfall alone.
- "Landfall" here means a 3-hourly track point falls inside the state polygon; IBTrACS LANDFALL is a distance-to-land field, not a state flag.
- 2026 storms (PROVISIONAL): BERTHA, EDOUARD, ISAIAS.
- Script: scratchpad storms/ibtracs_filter.py (not kept in repo). The full NA CSV was deleted after filtering; re-fetch from the URL above.

## Files

### `ibtracs_na_within300km_ga.parquet`: 29,348 rows

Columns: SID, SEASON, NUMBER, BASIN, SUBBASIN, NAME, ISO_TIME, NATURE, LAT, LON, WMO_WIND, WMO_PRES, USA_ATCF_ID, USA_RECORD, USA_STATUS, USA_WIND, USA_PRES, USA_SSHS, USA_RMW, USA_R34_NE, USA_R34_SE, USA_R34_SW, USA_R34_NW, STORM_SPEED, STORM_DIR, DIST2LAND, LANDFALL, TRACK_TYPE, in300, dist_ga_km

### `ibtracs_na_within800km_ga.parquet`: 44,489 rows, 731 storms

Columns: SID, SEASON, NUMBER, BASIN, SUBBASIN, NAME, ISO_TIME (UTC), NATURE, LAT, LON, WMO_WIND, WMO_PRES, WMO_AGENCY, TRACK_TYPE, DIST2LAND, LANDFALL, IFLAG, USA_AGENCY, USA_ATCF_ID, USA_LAT, USA_LON, USA_RECORD, USA_STATUS, USA_WIND, USA_PRES, USA_SSHS, USA_R34_NE, USA_R34_SE, USA_R34_SW, USA_R34_NW, USA_R50_NE, USA_R50_SE, USA_R50_SW, USA_R50_NW, USA_R64_NE, USA_R64_SE, USA_R64_SW, USA_R64_NW, USA_POCI, USA_ROCI, USA_RMW, USA_EYE, USA_GUST, USA_SEAHGT, USA_SEARAD_NE, USA_SEARAD_SE, USA_SEARAD_SW, USA_SEARAD_NW, STORM_SPEED, STORM_DIR, dist_ga_centroid_km, dist_ga_km, state, within800, sel_within800, sel_landfall_fl_ga_sc_al
