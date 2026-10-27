# FEMA ESF#6 Shelter System (NSS), full layer with last-activation fields, GA + FL

- **Source URL(s):** https://gis.fema.gov/arcgis/rest/services/NSS/FEMA_NSS/MapServer/5 (Shelter Locations), queried state='GA' and 'FL'
- **Fetched:** 2026-10-27
- **License / terms:** US Government work (FEMA), co-attributed with the American Red Cross, as in the packet README:697
- **Attribution:** Source: FEMA ESF#6 Shelter System, synchronized with the American Red Cross shelter database
- **Coverage:** GA 1,792 rows (same shelters as the packet), FL 2,798. One row per shelter holding its MOST RECENT activation only: incident_name/number, shelter_open_date, shelter_closed_date, general_population, medical_needs_population, total_population, pre_landfall_shelter. Earlier activations are overwritten.
- **Public repo + video safe?** Yes. The org_poc_* and org email/phone contact fields were not requested.
- **Known defects:** populations are sparse and undercounted (GA: 833 rows linked to an incident, 342 with an open date, 51 with any population; Helene 2024 shows 38 people in 19 shelters, while Red Cross reported 680+ in 35). Use as "this shelter has actually opened" evidence, not as fill rates. 628 GA rows carry incident_id 0 / blank name.

## Files

### `nss_ga_fl_last_activation.parquet`: 4,590 rows

Columns: shelter_id, shelter_name, city, county_parish, fips_code, state, evacuation_capacity, post_impact_capacity, generator_onsite, wheelchair_accessible, pre_landfall_shelter, population_code, incident_id, incident_number, incident_name, incident_code, shelter_status_code, reporting_period, general_population, medical_needs_population, other_population, total_population, pet_population, facility_type, latitude, longitude, shelter_open_date, shelter_closed_date (UTC timestamps)
