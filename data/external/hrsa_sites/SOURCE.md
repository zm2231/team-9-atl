# HRSA Health Center Service Delivery and Look-Alike Sites (with operating hours/week), 13 target states

- **Source URL(s):** https://data.hrsa.gov/DataDownload/DD_Files/Health_Center_Service_Delivery_and_LookAlike_Sites.csv ; metadata: https://data.hrsa.gov/DataDownload/DD_Files/Health_Center_Service_Delivery_and_LookAlike_Sites_Data_Download_Metadata.xlsx ; page: https://data.hrsa.gov/data/download
- **Fetched:** 2026-10-27
- **Publisher update date:** File Last-Modified 2026-10-26; `Data Warehouse Record Create Date` 10/26/2026 (refreshed daily)
- **License / terms:** U.S. Government work (HHS/HRSA). No dataset-specific license found on data.hrsa.gov (footer links to HHS disclaimer, which returned 403). Basis: 17 U.S.C. § 105, "Copyright protection under this title is not available for any work of the United States Government".
- **Terms URL:** https://www.law.cornell.edu/uscode/text/17/105 ; https://www.hhs.gov/disclaimer.html
- **Attribution:** Source: Health Resources and Services Administration, Health Center Service Delivery and Look-Alike Sites (data.hrsa.gov), accessed 2026-10-27
- **Coverage:** 10,056 active sites in GA (466), CA, FL, LA, NC, NY, SC, TX, IL, WA, CO, PA, AZ. 9,471 FQHC + 585 Look-Alike; 8,242 Permanent, 985 Seasonal, 829 Mobile Van.
- **Public repo + video safe?** Yes (the file includes members of Congress names as public officials; no patient data)

## Notes

- `Operating Hours per Week` numeric: median 40, max 168, 431 nulls in target states.
- Coordinates: `Geocoding Artifact Address Primary X Coordinate` = longitude, `...Y Coordinate` = latitude (WGS84); 1 null.
- Trailing empty column dropped. Raw national CSV (19,471 rows) + metadata xlsx (outside kit): scratchpad raw_c/hrsa/. Script: scratchpad scripts_c/hrsa.py.

## Files

### `health_center_sites_targets.parquet`: 10,056 rows, 55 columns

Columns: Health Center Type, Health Center Number, BHCMIS Organization Identification Number, BPHC Assigned Number, Site Name, Site Address, Site City, Site State Abbreviation, Site Postal Code, Site Telephone Number, Site Web Address, Operating Hours per Week, Health Center Location Setting Identification Number, Health Center Service Delivery Site Location Setting Description, Health Center Status Identification Number, Site Status Description, FQHC Site Medicare Billing Number, FQHC Site NPI Number, Health Center Location Identification Number, Health Center Location Type Description, Health Center Type Identification Number, Health Center Type Description, Health Center Operator Identification Number, Health Center Operator Description, Health Center Operating Schedule Identification Number, Health Center Operational Schedule Description, Health Center Operating Calendar Surrogate Key, Health Center Operating Calendar, Site Added to Scope this Date, Health Center Name, Health Center Organization Street Address, Health Center Organization City, Health Center Organization State, Health Center Organization ZIP Code, Grantee Organization Type Description, Geocoding Artifact Address Primary X Coordinate, Geocoding Artifact Address Primary Y Coordinate, U.S. - Mexico Border 100 Kilometer Indicator, U.S. - Mexico Border County Indicator, State and County Federal Information Processing Standard Code, Complete County Name, County Equivalent Name, County Description, HHS Region Code, HHS Region Name, State FIPS Code, State Name, State FIPS and Congressional District Number Code, Congressional District Number, Congressional District Name, Congressional District Code, U.S. Congressional Representative Name, Name of U.S. Senator Number One, Name of U.S. Senator Number Two, Data Warehouse Record Create Date

