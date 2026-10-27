# HHS emPOWER: Medicare electricity-dependent beneficiaries, Georgia ZIP + county

- **Source URL(s):** https://services2.arcgis.com/ZQ4jTQn6k7VPXEwO/arcgis/rest/services/HHS_emPOWER_REST_Service_Public/FeatureServer (layer 1 ZIP, layer 2 county; where State_FIPS_Code='13'). Info: https://empowerprogram.hhs.gov/empower-rest.html
- **Fetched:** 2026-10-27
- **Publisher update date:** Feature service dataLastEditDate 2026-10-07 (monthly refresh)
- **License / terms:** Federal (ASPR/CMS) de-identified data; the service is described as "publicly available, and can be consumed and displayed as a data layer in other geospatial information systems". The ArcGIS item licenseInfo is empty.
- **Terms URL:** https://empowerprogram.hhs.gov/empower-rest.html ; https://aspr.hhs.gov/Pages/disclaimer.aspx
- **Attribution:** Source: HHS emPOWER Program (ASPR/CMS), HHS emPOWER REST Service, accessed 2026-10-27
- **Coverage:** 711 GA ZIPs, 159 GA counties
- **Public repo + video safe?** Yes. Keep the suppression caveat visible.

## Notes

- Counts 1-10 are suppressed and shown as 11 (emPOWER methodology). Treat 11 as '1-11'.
- Columns: Medicare_Benes, Power_Dependent_Devices_DME (electricity-dependent DME), plus at-risk combinations (ESRD facility dialysis, O2, home health, hospice, any service).
- https://empowerprogram.hhs.gov/zips.csv is NOT usable: every row carries the same 1546/40360 values (placeholder). Use the REST service.

## Files

### `empower_ga_zip.csv`: 711 rows

Columns: OBJECTID, STATE, AREA, PA_NAME, COUNTY, Zip_Code_Recode, County_FIPS_Code, State_FIPS_Code, FIPS_Code, Zip_Code, Medicare_Benes, Power_Dependent_Devices_DME, Facility_ESRD_Dialysis_Any_DME, O2_Services_Any_DME, Home_Health_Services_Any_DME, AtHome_Hospice_Any_DME, Any_Healthcare_Srvc_Any_DME

### `empower_ga_county.csv`: 159 rows

Columns: OBJECTID, NAME, NAMELSAD, FIPS_Code_recode, State, FIPS_Code, County_FIPS_Code, County, State_FIPS_Code, Medicare_Benes, Power_Dependent_Devices_DME, Facility_ESRD_Dialysis_Any_DME, O2_Services_Any_DME, Home_Health_Services_Any_DME, AtHome_Hospice_Any_DME, Any_Healthcare_Srvc_Any_DME
