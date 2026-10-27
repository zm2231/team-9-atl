# NWS VTEC tropical watches/warnings for Georgia + Florida (via Iowa Environmental Mesonet)

- **Source URL(s):** https://mesonet.agron.iastate.edu/cgi-bin/request/gis/watchwarn.py?accept=csv&sts=2005-01-01T00:00Z&ets=2026-10-28T00:00Z&location_group=states&states=GA,FL&limitps=1&phenomena=HU,HU,TR,TR,SS,SS,HI,HI,TI,TI&significance=W,A,W,A,W,A,W,A,W,A
- **Fetched:** 2026-10-27
- **Publisher update date:** Live archive (IEM ingests NWS products in real time); latest row issued 2026-10-10 06:07 UTC (Isaias 2026).
- **License / terms:** IEM disclaimer: "The materials found on this website are in the public domain and may be used freely by anyone for any lawful purpose. Attributing the Iowa Environmental Mesonet of Iowa State University would be appreciated." Underlying products are NWS: "The information on National Weather Service (NWS) Web pages are in the public domain, unless specifically noted otherwise, and may be used without charge for any lawful purpose so long as you do not: 1) claim it is your own ... 2) use it in a manner that implies an endorsement or affiliation with NOAA/NWS, or 3) modify its content and then present it as official government material."
- **Terms URL:** https://mesonet.agron.iastate.edu/disclaimer.php ; https://www.weather.gov/disclaimer
- **Attribution:** NOAA National Weather Service VTEC watch/warning archive, retrieved from the Iowa Environmental Mesonet, Iowa State University.
- **Coverage:** Every NWS county/zone (UGC) in GA and FL that received a Hurricane (HU), Tropical Storm (TR), Storm Surge (SS), Inland Hurricane Wind (HI, retired ~2010) or Inland Tropical Storm Wind (TI) Watch or Warning, 2005-08-24 to 2026-10-10. 7,531 rows (FL 5,047, GA 2,484), 89 storm-state combinations (61 storms in FL, 28 in GA).
- **Public repo + video safe?** Yes (public domain; do not present as official NWS material)

## Notes

- One row per (VTEC event, UGC, phenomena.significance) as returned by IEM; `status` is the latest VTEC action (NEW/CON/EXA/EXT/UPG/CAN/EXP) for that UGC. `issue_utc` is when that UGC entered the event; `expire_utc` when it ended. A zone upgraded from TR.W to HU.W has two rows.
- Evacuation orders are NOT VTEC products. NWS "Evacuation Immediate" (EVI) is a non-VTEC relay of local orders, so there is no EV phenomenon here; use the IPAWS file in ../openfema for evacuation alerts.
- Coverage is thin before 2008 (IEM's tropical VTEC archive for 2005-2007 is partial: e.g. no Dennis 2005 rows) and empty for 2015. 2004 is not covered.
- Storm association: since ~2007 NHC assigns tropical ETNs nationally as 1000 + Atlantic storm number, so `eventid` 1014 in 2016 = AL142016 (Matthew). Joined to HURDAT2 (../hurdat2) and, for 2026, to IBTrACS provisional (../ibtracs), and only accepted when the issue time falls within the storm's track lifetime (-5 d / +2 d). Rows with local ETNs (<1000, pre-2008) or a mis-coded ETN (EYW 2005 1024, CHS 2016 1004) use the HURDAT2 storm with a fix within 12 h of issue that is closest to the state centroid (`storm_match_method`). Every row has a storm.
- Dropped: 23 NHC rows with eventid 1082 issued 2016-05-13 (test/erroneous HU.A outside any storm).
- `state` is the UGC prefix (GA/FL). `ugc_type` Z = forecast zone, C = county. Zones are not counties: use a zone-county correlation file to map.

## Files

### `ga_fl_tropical_vtec.parquet`: 7,531 rows

Columns: wfo, issue_utc, expire_utc, product_issue_utc, init_expire_utc, updated_utc, phenomena, significance, ps, product_name, eventid, vtec_year, status, ugc, state, ugc_type, gtype, area_km2, is_emergency, product_id, storm_atcf_id, storm_name, storm_match_method
