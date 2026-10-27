# FTA National Transit Database: 2025 Revenue Vehicle Inventory + 2025 Agency Information + 2024 Demand Response coverage, 13 target states

- **Source URL(s):** https://data.transportation.gov/d/ifzt-j53d (2025 NTD Annual Data - Revenue Vehicle Inventory) ; https://data.transportation.gov/d/jm7a-9hsy (2025 NTD Annual Data - Reporter Agency Information) ; https://data.transportation.gov/d/qifj-zz6e (2024 NTD Annual Data - Demand Response Geographic Area Coverage (Counties and Places)); downloaded via /api/views/<id>/rows.csv
- **Fetched:** 2026-10-27
- **Publisher update date:** RVI rows updated 2026-10-05; agency info 2026-10-05; DR coverage 2025-11-03 (2025 version not yet published)
- **License / terms:** Socrata license field: "Public Domain U.S. Government", termsLink https://www.usa.gov/government-works
- **Terms URL:** https://www.usa.gov/government-works
- **Attribution:** Source: Federal Transit Administration, National Transit Database (data.transportation.gov), accessed 2026-10-27
- **Coverage:** Agencies whose `State` is GA, CA, FL, LA, NC, NY, SC, TX, IL, WA, CO, PA, AZ: 1,140 agencies (GA 87); 16,794 vehicle fleet rows; 15,673 DR county/place coverage rows.
- **Public repo + video safe?** Yes

## Notes

- RVI has no state column; filtered by inner join on `NTD ID` to the target-state agency list and added `Agency State`, `Agency City`. All 35,625 national RVI rows match some agency, so nothing was lost to the join.
- Agency info carries `Service Area Sq Miles`, `Service Area Pop`, UZA, VOMS. RVI carries `ADA Fleet Vehicles`, `Seating Capacity`, `Active Fleet Vehicles`, `Emergency Contingency Vehicles` by mode/vehicle type (evacuation capacity proxy). DR coverage lists counties/places served by paratransit/demand response, filtered by `State Name`.
- Raw national CSVs + Socrata metadata JSON (outside kit): scratchpad raw_c/ntd/. Script: scratchpad scripts_c/ntd.py.

## Files

### `agency_info_2025_targets.parquet`: 1,140 rows, 46 columns

Columns: State/Parent NTD ID, NTD ID, Legacy NTD ID, Agency Name, Division/Department, Reporter Acronym, Doing Business As, Reporter Type, Reporting Module, Organization Type, Reported By NTD ID, Reported by Name, Public Sponsor, Subrecipient Type, FY End Date, Original Due Date, Address Line 1, Address Line 2, P.O. Box, City, State, Zip Code, Zip Code Ext, Region, URL, FTA Recipient ID, UEID, Voluntary Reporter Flag, Service Area Sq Miles, Service Area Pop, Primary UZA UACE Code, UZA Name, Tribal Area Name, Population, Density, Sq Miles, VOMS DO, VOMS PT, Total VOMS, Volunteer Drivers, Personal Vehicles, TAM Tier, Number of State Counties, Number of Counties with Service, State Admin Funds Expended, street_address_geo_reference

### `demand_response_coverage_2024_targets.parquet`: 15,673 rows, 11 columns

Columns: NTD ID, Agency, Reporter Type, Mode, TOS, Place Geo ID, Place Name, Level of Service, County Geo ID, County Name, State Name

### `revenue_vehicle_inventory_2025_targets.parquet`: 16,794 rows, 42 columns

Columns: State/Parent NTD ID, NTD ID, Agency Name, Reporter Type, Reporting Module, Group Plan Sponsor NTDID, Group Plan Sponsor Name, Modes, Revenue Vehicle Inventory ID, Agency Fleet ID, Total Fleet Vehicles, Dedicated Fleet, Vehicle Type, Ownership Type, Funding Source, Manufacture Year, Rebuild Year, Type of Last Renewal, Useful Life Benchmark, Manufacturer, Other Manufacturer Description, Model, Active Fleet Vehicles, ADA Fleet Vehicles, Emergency Contingency Vehicles, Fuel Type, Other Fuel Description, Vehicle Length, Seating Capacity, Standing Capacity, Total Miles on Active Vehicles During Period, Average Lifetime Miles per Active Vehicles, No Capital Replacement Flag, Separate Asset Flag, Event Data Recorders, Emergency Lighting System Design, Emergency Signage, Emergency Path Marking, Automated Vehicles Flag, Notes, Agency State, Agency City

