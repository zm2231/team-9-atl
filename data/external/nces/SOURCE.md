# NCES EDGE public school + district (LEA) geocodes, Georgia, SY 2024-25

- **Source URL(s):** https://nces.ed.gov/opengis/rest/services/K12_School_Locations/EDGE_GEOCODE_PUBLICSCH_2425/MapServer/0 and .../EDGE_GEOCODE_PUBLICLEA_2425/MapServer/0 (where STATE='GA')
- **Fetched:** 2026-10-27
- **Publisher update date:** SY 2024-25 geocodes (TIGER 2025 based). A 2025-26 release is listed on the EDGE site, but there is no 2526 REST service yet.
- **License / terms:** U.S. Department of Education / NCES, U.S. Government work (public domain).
- **Terms URL:** https://nces.ed.gov/programs/edge/Geographic/SchoolLocations
- **Attribution:** Source: U.S. Department of Education, National Center for Education Statistics, EDGE Public School Geocodes 2024-25
- **Coverage:** 2,349 GA public schools; 256 GA LEAs, with LAT/LON
- **Public repo + video safe?** Yes

## Files

### `public_schools_ga_2425.csv`: 2,349 rows

Columns: OBJECTID, NCESSCH, LEAID, NAME, OPSTFIPS, STREET, CITY, STATE, ZIP, STFIP, CNTY, NMCNTY, LOCALE, LAT, LON, CBSA, NMCBSA, CBSATYPE, CSA, NMCSA, CD, SLDL, SLDU, SCHOOLYEAR

### `public_leas_ga_2425.csv`: 256 rows

Columns: OBJECTID, LEAID, NAME, OPSTFIPS, STREET, CITY, STATE, ZIP, STFIP, CNTY, NMCNTY, LAT, LON, CBSA, NMCBSA, CBSATYPE, CSA, NMCSA, CD, SLDL, SLDU, SCHOOLYEAR, LOCALE, PCT_CITY11, PCT_CITY12, PCT_CITY13, PCT_SUB21, PCT_SUB22, PCT_SUB23, PCT_TOWN31, PCT_TOWN32, PCT_TOWN33, PCT_RURAL41, PCT_RURAL42, PCT_RURAL43

## Addendum: other target states (public schools only), fetched 2026-10-27

- **Source URL:** https://nces.ed.gov/opengis/rest/services/K12_School_Locations/EDGE_GEOCODE_PUBLICSCH_2425/MapServer/0 (where STATE='<ST>'), paged 1,000 per request, ordered by OBJECTID
- **License / attribution / safety:** same as above (U.S. Government work; 17 U.S.C. § 105: "Copyright protection under this title is not available for any work of the United States Government"). Public repo + video safe: Yes.
- **Coverage:** 49,256 schools across 12 states. CA (10,407) and TX (9,774) were checked against the service's returnCountOnly and match; the other states were not separately checked. LEA files were not fetched for these states.
- Columns in every file are the same as `public_schools_ga_2425.csv`: OBJECTID, NCESSCH, LEAID, NAME, OPSTFIPS, STREET, CITY, STATE, ZIP, STFIP, CNTY, NMCNTY, LOCALE, LAT, LON, CBSA, NMCBSA, CBSATYPE, CSA, NMCSA, CD, SLDL, SLDU, SCHOOLYEAR
- Script: scratchpad scripts_c/nces.py

| File | Rows |
|---|---|
| `public_schools_az_2425.csv` | 2,633 |
| `public_schools_ca_2425.csv` | 10,407 |
| `public_schools_co_2425.csv` | 1,917 |
| `public_schools_fl_2425.csv` | 4,312 |
| `public_schools_il_2425.csv` | 4,439 |
| `public_schools_la_2425.csv` | 1,330 |
| `public_schools_nc_2425.csv` | 2,766 |
| `public_schools_ny_2425.csv` | 4,865 |
| `public_schools_pa_2425.csv` | 2,949 |
| `public_schools_sc_2425.csv` | 1,290 |
| `public_schools_tx_2425.csv` | 9,774 |
| `public_schools_wa_2425.csv` | 2,574 |
