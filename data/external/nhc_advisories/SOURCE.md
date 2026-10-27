# NHC GIS advisory archive: forecast track, cone and coastal watches/warnings, 2008-2026, storms affecting GA/FL

- **Source URL(s):** per-storm index https://www.nhc.noaa.gov/gis/archive_forecast_results.php?id=alNN&year=YYYY ; files https://www.nhc.noaa.gov/gis/forecast/archive/alNNYYYY_5day_NNN[A].zip (forecast track line, cone polygon, forecast points, watch/warning lines) and alNNYYYY_fcst_NNN[A].zip (forecast wind radii; kept raw, not parsed)
- **Fetched:** 2026-10-27 (3,777 zips for 97 candidate storms in 31 s; 2,441 zips for the 54 selected storms kept)
- **Publisher update date:** Per-advisory, as issued (zip member timestamps = advisory time). Latest advisory in the set: AL092026 Isaias adv 014, 2026-10-10 09:00 UTC.
- **License / terms:** NOAA/NWS, U.S. Government work (public domain, 17 U.S.C. 105). NWS disclaimer: "The information on National Weather Service (NWS) Web pages are in the public domain, unless specifically noted otherwise, and may be used without charge for any lawful purpose". Same page: "NOAA/National Weather Service data presented using Google Earth, Google Maps, or Esri ArcGIS Online map services are in the public domain and are also made available in open geospatial standard formats such as KML/KMZ (Google) and shapefile (Esri)".
- **Terms URL:** https://www.weather.gov/disclaimer
- **Attribution:** Source: NOAA National Hurricane Center, GIS forecast advisory archive (https://www.nhc.noaa.gov/gis/).
- **Coverage:** 54 Atlantic storms, 2008-2026, 1,314 advisories (incl. intermediate "A" advisories). Selection: from all AL storms 2008+ in IBTrACS whose track came within 500 km of GA or FL (97 candidates), keep those with a hurricane/tropical storm watch or warning segment on the GA or FL coast, or whose best track entered GA. 20 storms had a GA-coast watch/warning, 52 an FL-coast one, 20 entered GA. Priority storms all present: Matthew 2016, Irma 2017, Michael 2018, Dorian 2019, Ian 2022, Idalia 2023, Debby/Helene/Milton 2024, Isaias 2026.
- **Public repo + video safe?** Yes (public domain). Label derived lead times as computed, not official NHC verification.

## Notes

- issue_time_utc is parsed from ADVDATE: "yymmdd/hhmm" (UTC, 2008-2013 style) or "400 PM CDT Wed Sep 25 2024" (local zone converted to UTC). All 2,024 parsed advisories (97 storms) parsed with 0 failures.
- ww_type codes: TWA tropical storm watch, TWR tropical storm warning, HWA hurricane watch, HWR hurricane warning. Watch/warning lines are coastal only: inland TS/hurricane warnings (e.g. SW Georgia in Michael, Helene, Isaias 2026) are issued by NWS WFOs and are not in these files. Storm surge watches/warnings are not in the 5-day zips either.
- A segment "touches" GA (or FL) when at least 15 km of it lies within 10 km of the Census cb_2024 20m state polygon (EPSG:5070). This excludes segments that only end at the St. Marys River border (about 10 km of overlap) and keeps e.g. Irma adv 041 TWA Fernandina Beach to Altamaha Sound. len_in_ga_km / len_in_fl_km give the overlap so the threshold can be changed.
- storm_lead_times impact definitions, from IBTrACS v04r01 USA best track interpolated to hourly: *_ts_wind_onset_utc = first hour when any R34 quadrant wedge (NE/SE/SW/NW, 90 degrees each, built in EPSG:5070) intersects the state polygon; *_landfall_time_utc = first hour the centre is inside the polygon; *_impact_utc = TS-wind onset, else landfall; *_watch_lead_h / *_warning_lead_h = impact minus first watch / first warning on that state's coast (negative = issued after onset). GA impact is state-wide (inland included), while GA watches/warnings are coast-only, so for Gulf storms (Michael, Helene, Isaias 2026) GA impact can have no GA watch.
- forecast_points.valid_time_utc comes from the VALIDTIME label "DD/HHMM" (UTC) resolved against the issue month.
- cone_wkt is the largest-period cone polygon in the zip (120 h from 2008 on; some early pgn rings are stored with hole orientation and are read as exteriors).
- Scripts (scratchpad, not in repo): nhc_candidates.py, nhc_parse.py, nhc_leadtimes.py.

## Files

### `advisories.parquet`: 9,157 rows (one per advisory x watch/warning segment; advisories with no segments have one row with null ww_type), 54 storms, 2008-08-15 21:00 to 2026-10-10 09:00 UTC

Columns: storm_id, season, storm_name, storm_type, advisory, advdate_raw, issue_time_utc, ga_ww_types, fl_ww_types, forecast_track_wkt, source_zip, forecast_points_wkt, segment_idx, ww_type, ww_label, start_lon, start_lat, end_lon, end_lat, n_vertices, len_in_ga_km, len_in_fl_km, touches_ga, touches_fl, geometry_wkt

### `forecast_points.parquet`: 12,463 rows (one per advisory x forecast tau)

Columns: storm_id, season, advisory, issue_time_utc, tau_h, lat, lon, max_wind_kt, gust_kt, mslp_mb, dvlbl, storm_type, valid_label, valid_time_utc

### `advisory_cones.parquet`: 1,314 rows (one per advisory)

Columns: storm_id, season, storm_name, advisory, issue_time_utc, cone_wkt, source_zip

### `storm_lead_times.parquet`: 54 rows (one per storm)

Columns: storm_id, season, storm_name, ibtracs_sid, n_advisories, first_advisory_utc, last_advisory_utc, track_entered_ga, max_wind_kt, ga_closest_km, ga_closest_time_utc, ga_landfall_time_utc, ga_ts_wind_onset_utc, fl_closest_km, fl_closest_time_utc, fl_landfall_time_utc, fl_ts_wind_onset_utc, ga_first_watch_utc, ga_first_watch_type, ga_first_warning_utc, ga_first_warning_type, ga_first_hurricane_warning_utc, ga_first_ww_advisory, fl_first_watch_utc, fl_first_watch_type, fl_first_warning_utc, fl_first_warning_type, fl_first_hurricane_warning_utc, fl_first_ww_advisory, ga_impact_utc, ga_impact_basis, ga_watch_lead_h, ga_warning_lead_h, ga_landfall_or_closest_utc, fl_impact_utc, fl_impact_basis, fl_watch_lead_h, fl_warning_lead_h, fl_landfall_or_closest_utc

### `raw/`: 2,441 zips, 92 MB

1,314 `*_5day_*.zip` (shapefiles: _5day_lin, _5day_pgn, _5day_pts, _ww_wwlin) and 1,127 `*_fcst_*.zip` (forecast wind radii) for the 54 storms.
