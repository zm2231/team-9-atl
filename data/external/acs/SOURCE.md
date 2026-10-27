# Census ACS 2020-2024 5-year, Georgia census tracts (estimates + 90% MOE)

- **Source URL(s):** https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/acsdt5y2024-<table>.dat (table-based Summary File, one file per table, all US geographies; filtered to GEO_ID prefix 1400000US13). Labels: https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/documentation/ACS20245YR_Table_Shells.txt
- **Fetched:** 2026-10-27
- **Publisher update date:** Summary files dated 2026-01-29 on the Census server (2020-2024 ACS 5-year is the latest 5-year release)
- **License / terms:** U.S. Government work (17 U.S.C. 105), no copyright. Census confidentiality terms apply: users "will not use these data, alone or in combination with any other Census or non-Census data, to identify any individual person, household, business or other entity".
- **Terms URL:** https://www.census.gov/data/developers/about/terms-of-service.html ; https://www.census.gov/about/policies.html
- **Attribution:** Source: U.S. Census Bureau, 2020-2024 American Community Survey 5-Year Estimates
- **Coverage:** All 2,796 Georgia census tracts (2020 tract geography)
- **Public repo + video safe?** Yes

## Notes

- api.census.gov hung (curl timeouts at 40-60 s, with and without a key) from this machine on 2026-10-27, and keyless requests to the 2024 endpoint return a 302 redirect to missing_key.html. The table-based Summary File on www2.census.gov is the same published data and downloaded in seconds.
- Column naming follows the Summary File: <TABLE>_E### = estimate and <TABLE>_M### = 90% margin of error. The API names the same fields <TABLE>_###E and <TABLE>_###M. columns_dictionary.csv maps every column to its label, indent and universe.
- B16001 (detailed language spoken at home) is NOT published at tract level: the Summary File has zero tract rows for it. C16001 (collapsed languages + 'speak English less than very well') and B16004 (age by language by English ability) are included instead.
- GEOID = 11-digit tract FIPS; county_fips = first 5 digits.
- raw/ keeps the filtered .dat files and table shells for provenance.
- Other files in this folder (b03002_ga_tract.parquet, b03002_ca_tract.parquet, and the *_us_tracts.parquet set added around 02:41) were written to this folder by another process during this session (derived pct columns). They are not produced by this pull. b03002_ga_tracts.{csv,parquet} is the full B03002 table with MOEs from the Summary File.

## Files

### `b01001_ga_tracts.parquet`: 2,796 rows

Columns: GEO_ID, GEOID, county_fips, B01001_E001, B01001_M001, B01001_E002, B01001_M002, B01001_E003, B01001_M003, B01001_E004, B01001_M004, B01001_E005, B01001_M005, B01001_E006, B01001_M006, B01001_E007, B01001_M007, B01001_E008, B01001_M008, B01001_E009, B01001_M009, B01001_E010, B01001_M010, B01001_E011, B01001_M011, B01001_E012, B01001_M012, B01001_E013, B01001_M013, B01001_E014, B01001_M014, B01001_E015, B01001_M015, B01001_E016, B01001_M016, B01001_E017, B01001_M017, B01001_E018, B01001_M018, B01001_E019, B01001_M019, B01001_E020, B01001_M020, B01001_E021, B01001_M021, B01001_E022, B01001_M022, B01001_E023, B01001_M023, B01001_E024, B01001_M024, B01001_E025, B01001_M025, B01001_E026, B01001_M026, B01001_E027, B01001_M027, B01001_E028, B01001_M028, B01001_E029, B01001_M029, B01001_E030, B01001_M030, B01001_E031, B01001_M031, B01001_E032, B01001_M032, B01001_E033, B01001_M033, B01001_E034, B01001_M034, B01001_E035, B01001_M035, B01001_E036, B01001_M036, B01001_E037, B01001_M037, B01001_E038, B01001_M038, B01001_E039, B01001_M039, B01001_E040, B01001_M040, B01001_E041, B01001_M041, B01001_E042, B01001_M042, B01001_E043, B01001_M043, B01001_E044, B01001_M044, B01001_E045, B01001_M045, B01001_E046, B01001_M046, B01001_E047, B01001_M047, B01001_E048, B01001_M048, B01001_E049, B01001_M049

### `b03002_ga_tracts.parquet`: 2,796 rows

Columns: GEO_ID, GEOID, county_fips, B03002_E001, B03002_M001, B03002_E002, B03002_M002, B03002_E003, B03002_M003, B03002_E004, B03002_M004, B03002_E005, B03002_M005, B03002_E006, B03002_M006, B03002_E007, B03002_M007, B03002_E008, B03002_M008, B03002_E009, B03002_M009, B03002_E010, B03002_M010, B03002_E011, B03002_M011, B03002_E012, B03002_M012, B03002_E013, B03002_M013, B03002_E014, B03002_M014, B03002_E015, B03002_M015, B03002_E016, B03002_M016, B03002_E017, B03002_M017, B03002_E018, B03002_M018, B03002_E019, B03002_M019, B03002_E020, B03002_M020, B03002_E021, B03002_M021

### `b08201_ga_tracts.parquet`: 2,796 rows

Columns: GEO_ID, GEOID, county_fips, B08201_E001, B08201_M001, B08201_E002, B08201_M002, B08201_E003, B08201_M003, B08201_E004, B08201_M004, B08201_E005, B08201_M005, B08201_E006, B08201_M006, B08201_E007, B08201_M007, B08201_E008, B08201_M008, B08201_E009, B08201_M009, B08201_E010, B08201_M010, B08201_E011, B08201_M011, B08201_E012, B08201_M012, B08201_E013, B08201_M013, B08201_E014, B08201_M014, B08201_E015, B08201_M015, B08201_E016, B08201_M016, B08201_E017, B08201_M017, B08201_E018, B08201_M018, B08201_E019, B08201_M019, B08201_E020, B08201_M020, B08201_E021, B08201_M021, B08201_E022, B08201_M022, B08201_E023, B08201_M023, B08201_E024, B08201_M024, B08201_E025, B08201_M025, B08201_E026, B08201_M026, B08201_E027, B08201_M027, B08201_E028, B08201_M028, B08201_E029, B08201_M029, B08201_E030, B08201_M030

### `b11007_ga_tracts.parquet`: 2,796 rows

Columns: GEO_ID, GEOID, county_fips, B11007_E001, B11007_M001, B11007_E002, B11007_M002, B11007_E003, B11007_M003, B11007_E004, B11007_M004, B11007_E005, B11007_M005, B11007_E006, B11007_M006, B11007_E007, B11007_M007, B11007_E008, B11007_M008, B11007_E009, B11007_M009, B11007_E010, B11007_M010, B11007_E011, B11007_M011

### `c16001_ga_tracts.parquet`: 2,796 rows

Columns: GEO_ID, GEOID, county_fips, C16001_E001, C16001_M001, C16001_E002, C16001_M002, C16001_E003, C16001_M003, C16001_E004, C16001_M004, C16001_E005, C16001_M005, C16001_E006, C16001_M006, C16001_E007, C16001_M007, C16001_E008, C16001_M008, C16001_E009, C16001_M009, C16001_E010, C16001_M010, C16001_E011, C16001_M011, C16001_E012, C16001_M012, C16001_E013, C16001_M013, C16001_E014, C16001_M014, C16001_E015, C16001_M015, C16001_E016, C16001_M016, C16001_E017, C16001_M017, C16001_E018, C16001_M018, C16001_E019, C16001_M019, C16001_E020, C16001_M020, C16001_E021, C16001_M021, C16001_E022, C16001_M022, C16001_E023, C16001_M023, C16001_E024, C16001_M024, C16001_E025, C16001_M025, C16001_E026, C16001_M026, C16001_E027, C16001_M027, C16001_E028, C16001_M028, C16001_E029, C16001_M029, C16001_E030, C16001_M030, C16001_E031, C16001_M031, C16001_E032, C16001_M032, C16001_E033, C16001_M033, C16001_E034, C16001_M034, C16001_E035, C16001_M035, C16001_E036, C16001_M036, C16001_E037, C16001_M037, C16001_E038, C16001_M038

### `b16004_ga_tracts.parquet`: 2,796 rows

Columns: GEO_ID, GEOID, county_fips, B16004_E001, B16004_M001, B16004_E002, B16004_M002, B16004_E003, B16004_M003, B16004_E004, B16004_M004, B16004_E005, B16004_M005, B16004_E006, B16004_M006, B16004_E007, B16004_M007, B16004_E008, B16004_M008, B16004_E009, B16004_M009, B16004_E010, B16004_M010, B16004_E011, B16004_M011, B16004_E012, B16004_M012, B16004_E013, B16004_M013, B16004_E014, B16004_M014, B16004_E015, B16004_M015, B16004_E016, B16004_M016, B16004_E017, B16004_M017, B16004_E018, B16004_M018, B16004_E019, B16004_M019, B16004_E020, B16004_M020, B16004_E021, B16004_M021, B16004_E022, B16004_M022, B16004_E023, B16004_M023, B16004_E024, B16004_M024, B16004_E025, B16004_M025, B16004_E026, B16004_M026, B16004_E027, B16004_M027, B16004_E028, B16004_M028, B16004_E029, B16004_M029, B16004_E030, B16004_M030, B16004_E031, B16004_M031, B16004_E032, B16004_M032, B16004_E033, B16004_M033, B16004_E034, B16004_M034, B16004_E035, B16004_M035, B16004_E036, B16004_M036, B16004_E037, B16004_M037, B16004_E038, B16004_M038, B16004_E039, B16004_M039, B16004_E040, B16004_M040, B16004_E041, B16004_M041, B16004_E042, B16004_M042, B16004_E043, B16004_M043, B16004_E044, B16004_M044, B16004_E045, B16004_M045, B16004_E046, B16004_M046, B16004_E047, B16004_M047, B16004_E048, B16004_M048, B16004_E049, B16004_M049, B16004_E050, B16004_M050, B16004_E051, B16004_M051, B16004_E052, B16004_M052, B16004_E053, B16004_M053, B16004_E054, B16004_M054, B16004_E055, B16004_M055, B16004_E056, B16004_M056, B16004_E057, B16004_M057, B16004_E058, B16004_M058, B16004_E059, B16004_M059, B16004_E060, B16004_M060, B16004_E061, B16004_M061, B16004_E062, B16004_M062, B16004_E063, B16004_M063, B16004_E064, B16004_M064, B16004_E065, B16004_M065, B16004_E066, B16004_M066, B16004_E067, B16004_M067

### `b17001_ga_tracts.parquet`: 2,796 rows

Columns: GEO_ID, GEOID, county_fips, B17001_E001, B17001_M001, B17001_E002, B17001_M002, B17001_E003, B17001_M003, B17001_E004, B17001_M004, B17001_E005, B17001_M005, B17001_E006, B17001_M006, B17001_E007, B17001_M007, B17001_E008, B17001_M008, B17001_E009, B17001_M009, B17001_E010, B17001_M010, B17001_E011, B17001_M011, B17001_E012, B17001_M012, B17001_E013, B17001_M013, B17001_E014, B17001_M014, B17001_E015, B17001_M015, B17001_E016, B17001_M016, B17001_E017, B17001_M017, B17001_E018, B17001_M018, B17001_E019, B17001_M019, B17001_E020, B17001_M020, B17001_E021, B17001_M021, B17001_E022, B17001_M022, B17001_E023, B17001_M023, B17001_E024, B17001_M024, B17001_E025, B17001_M025, B17001_E026, B17001_M026, B17001_E027, B17001_M027, B17001_E028, B17001_M028, B17001_E029, B17001_M029, B17001_E030, B17001_M030, B17001_E031, B17001_M031, B17001_E032, B17001_M032, B17001_E033, B17001_M033, B17001_E034, B17001_M034, B17001_E035, B17001_M035, B17001_E036, B17001_M036, B17001_E037, B17001_M037, B17001_E038, B17001_M038, B17001_E039, B17001_M039, B17001_E040, B17001_M040, B17001_E041, B17001_M041, B17001_E042, B17001_M042, B17001_E043, B17001_M043, B17001_E044, B17001_M044, B17001_E045, B17001_M045, B17001_E046, B17001_M046, B17001_E047, B17001_M047, B17001_E048, B17001_M048, B17001_E049, B17001_M049, B17001_E050, B17001_M050, B17001_E051, B17001_M051, B17001_E052, B17001_M052, B17001_E053, B17001_M053, B17001_E054, B17001_M054, B17001_E055, B17001_M055, B17001_E056, B17001_M056, B17001_E057, B17001_M057, B17001_E058, B17001_M058, B17001_E059, B17001_M059

### `b18101_ga_tracts.parquet`: 2,796 rows

Columns: GEO_ID, GEOID, county_fips, B18101_E001, B18101_M001, B18101_E002, B18101_M002, B18101_E003, B18101_M003, B18101_E004, B18101_M004, B18101_E005, B18101_M005, B18101_E006, B18101_M006, B18101_E007, B18101_M007, B18101_E008, B18101_M008, B18101_E009, B18101_M009, B18101_E010, B18101_M010, B18101_E011, B18101_M011, B18101_E012, B18101_M012, B18101_E013, B18101_M013, B18101_E014, B18101_M014, B18101_E015, B18101_M015, B18101_E016, B18101_M016, B18101_E017, B18101_M017, B18101_E018, B18101_M018, B18101_E019, B18101_M019, B18101_E020, B18101_M020, B18101_E021, B18101_M021, B18101_E022, B18101_M022, B18101_E023, B18101_M023, B18101_E024, B18101_M024, B18101_E025, B18101_M025, B18101_E026, B18101_M026, B18101_E027, B18101_M027, B18101_E028, B18101_M028, B18101_E029, B18101_M029, B18101_E030, B18101_M030, B18101_E031, B18101_M031, B18101_E032, B18101_M032, B18101_E033, B18101_M033, B18101_E034, B18101_M034, B18101_E035, B18101_M035, B18101_E036, B18101_M036, B18101_E037, B18101_M037, B18101_E038, B18101_M038, B18101_E039, B18101_M039

### `b25044_ga_tracts.parquet`: 2,796 rows

Columns: GEO_ID, GEOID, county_fips, B25044_E001, B25044_M001, B25044_E002, B25044_M002, B25044_E003, B25044_M003, B25044_E004, B25044_M004, B25044_E005, B25044_M005, B25044_E006, B25044_M006, B25044_E007, B25044_M007, B25044_E008, B25044_M008, B25044_E009, B25044_M009, B25044_E010, B25044_M010, B25044_E011, B25044_M011, B25044_E012, B25044_M012, B25044_E013, B25044_M013, B25044_E014, B25044_M014, B25044_E015, B25044_M015

### `columns_dictionary.csv`: 658 rows

Columns: table, title, universe, column, kind, line, indent, label

## Multi-state + national pull (appended 2026-10-27 03:00 local)

- **Source URL(s):** same table-based Summary File, https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/acsdt5y2024-<table>.dat (full national file per table, all tract rows `1400000US*` kept).
- **Vintage:** 2020-2024 ACS 5-year (the latest release, and the same vintage as the GA files above). The prefetch request said 2019-2023; this pull deliberately stays on 2020-2024 so every file in `acs/` is one vintage. Both use 2020 tract geography.
- **License:** U.S. Government work, public domain; Census confidentiality terms quoted above apply.
- **Schema of these files:** `GEO_ID` (1400000US...), `geo_id` (11-digit tract FIPS, string), `county_fips` (5-digit), then `<TABLE>_E###` estimate / `<TABLE>_M###` 90% MOE as floats (Census annotation codes become null). The original GA files above use `GEOID` instead of `geo_id`; `kit/core/acs.py` renames `GEOID` to `geo_id`, so both load the same way.
- **Files:** `<table>_us_tracts.parquet` (all 85,382 US tracts incl. PR) and `<table>_<st>_tracts.parquet` for st in ga ca fl la nc ny sc tx il wa co pa az. Pre-existing GA files for the first 9 tables were kept unchanged. Use the `_us_` file for metros that cross state lines (NY-NJ, Philadelphia-NJ-DE-MD, Chicago-IN-WI).
- **Rows per state:** ga 2,796; ca 9,129; fl 5,160; la 1,388; nc 2,672; ny 5,397; sc 1,323; tx 6,896; il 3,265; wa 1,784; co 1,447; pa 3,446; az 1,765; us 85,382. Identical for every table.
- **Caveat:** B26001 is *total* group-quarters population only (one line). GQ by type is not in ACS at tract level; see `group_quarters/` (2020 Census) for type.
- `columns_dictionary.csv` regenerated from the table shells for all 21 tables.

| Table | Title | Estimate columns |
|---|---|---|
| B01001 | Sex by Age | 49 |
| B03002 | Hispanic or Latino Origin by Race | 21 |
| B08201 | Household Size by Vehicles Available | 30 |
| B11007 | Households by Presence of People 65 Years and Over, Household Size and Household Type | 11 |
| B16004 | Age by Language Spoken at Home by Ability to Speak English for the Population 5 Years and Over | 67 |
| B17001 | Poverty Status in the Past 12 Months by Sex by Age | 59 |
| B18101 | Sex by Age by Disability Status | 39 |
| B25044 | Tenure by Vehicles Available | 15 |
| C16001 | Language Spoken at Home for the Population 5 Years and Over | 38 |
| B08302 | Time of Departure to Go to Work | 15 |
| B08303 | Travel Time to Work | 13 |
| B28002 | Presence and Types of Internet Subscriptions in Household | 13 |
| B26001 | Group Quarters Population | 1 |
| B25003 | Tenure | 3 |
| C16002 | Household Language by Household Limited English Speaking Status | 14 |
| B09005 | Household Type for Children Under 18 Years in Households (Excluding Householders, Spouses, and Unmarried Partners) | 5 |
| B22010 | Receipt of Food Stamps/SNAP in the Past 12 Months by Disability Status for Households | 7 |
| B19058 | Public Assistance Income or Food Stamps/SNAP in the Past 12 Months for Households | 3 |
| B27010 | Types of Health Insurance Coverage by Age | 66 |
| B11003 | Family Type by Presence and Age of Own Children Under 18 Years | 20 |
| B23008 | Age of Own Children Under 18 Years in Families and Subfamilies by Living Arrangements by Employment Status of Parents | 27 |
