# NOAA NCEI Storm Events Database: Georgia + Florida tropical events 1996-present

- **Source URL(s):** https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/StormEvents_details-ftp_v1.0_dYYYY_cYYYYMMDD.csv.gz for 1996-2026 (31 files; creation dates c20260323 to c20261026)
- **Fetched:** 2026-10-27
- **Publisher update date:** Per-year files re-created 2026-03-23 to 2026-10-26 (see `ncei_file_created`). The 2026 file only runs to 2026-07 events, so Isaias 2026 is NOT in Storm Events yet; the latest tropical row is 2025-08-21.
- **License / terms:** U.S. Government work (NOAA/NWS, 17 U.S.C. 105, public domain). NCEI metadata (gov.noaa.ncdc:C00510): "Access Constraints: None"; "Use Constraints: Cite dataset when used as a source. An effort is made to use the best available information but because of time and resource constraints, information from these sources may be unverified by the NWS." NWS disclaimer: "The information on National Weather Service (NWS) Web pages are in the public domain".
- **Terms URL:** https://www.ncei.noaa.gov/access/metadata/landing-page/bin/iso?id=gov.noaa.ncdc:C00510 ; https://www.weather.gov/disclaimer
- **Attribution:** NOAA National Centers for Environmental Information, Storm Events Database (DSI 3910_03, gov.noaa.ncdc:C00510), accessed 2026-10-27.
- **Coverage:** GA and FL, 1996-07-10 to 2025-08-21. 6,934 events (FL 3,511, GA 3,423) in 691 episodes, 128 storms. 4,606 rows are tropical event types; 2,328 are flood/wind/tornado/surf rows from tropical episodes.
- **Public repo + video safe?** Yes. Narratives dropped (see notes).

## Notes

- Kept: event types Hurricane (Typhoon), Tropical Storm, Tropical Depression, Storm Surge/Tide (`is_tropical_type`), plus Flash Flood, Flood, Heavy Rain, High/Strong/Thunderstorm Wind, Tornado, Coastal Flood, High Surf, Rip Current, Debris Flow, Waterspout rows whose episode either contains a tropical event type or whose episode narrative names a storm ("Hurricane X", "Tropical Storm X", ...) that HURDAT2 shows active within 3 days of the event.
- `storm_atcf_id` / `storm_name`: HURDAT2 storm active within +/-3 days of the event; preferred when its name matches `storm_name_from_narrative`, otherwise the one whose track passed closest to the event point (or state centroid when the event has no lat/lon). 10 rows have no storm.
- EPISODE_NARRATIVE and EVENT_NARRATIVE are DROPPED: they describe victims ("a 45-year-old man ...") and can name people, and screening for names is not reliable. Only the extracted storm name is kept. NCEI fatality detail files (age/sex/location per death) were not fetched.
- Tropical events are mostly logged by forecast zone (`cz_type`='Z'), so `cz_fips` is a zone number; `county_fips` is filled only for county rows (`cz_type`='C'). `ugc` = state + type + 3-digit code joins to ../nws_vtec.
- `begin_local`/`end_local` are in the `cz_timezone` given (EST-5 / CST-6 etc.), not UTC.
- `damage_property_usd` / `damage_crops_usd` parsed from K/M/B strings; nominal dollars of the event year, and damage for a hurricane is often entered on only one or a few zones per episode. Deaths/injuries per row are direct + indirect as NWS logged them.
- Source CSVs contain malformed quoting (e.g. 1997 `"7 MILE" BRIDGE`); read with DuckDB strict_mode=false.

## Files

### `ga_fl_tropical.parquet`: 6,934 rows

Columns: event_id, episode_id, state, state_fips, year, event_type, is_tropical_type, episode_has_tropical_type, episode_narrative_tropical, storm_name_from_narrative, cz_type, cz_fips, cz_name, county_fips, ugc, wfo, begin_local, end_local, cz_timezone, deaths_direct, deaths_indirect, injuries_direct, injuries_indirect, damage_property_raw, damage_property_usd, damage_crops_raw, damage_crops_usd, magnitude, magnitude_type, source, flood_cause, begin_lat, begin_lon, ncei_file_created, storm_atcf_id, storm_name, storm_min_dist_km, storm_match_method
