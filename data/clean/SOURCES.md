# Sources and licences

Every input is read locally; nothing is fetched at build time. Paths are the defaults in
`gaclean/sources.py`, and each can be overridden by the environment variable shown.

| Input | Default path (env) | Publisher | Licence | Used for |
|---|---|---|---|---|
| Georgia snapshot: `care_facilities`, `hazard_tracts`, `power_dependent_counties`, `vulnerability_tracts`, `shelters` | `~/work/c4data/GA/<table>/data.parquet` (`C4DATA_GA`) | Challenge staging of CMS, FEMA NRI, HHS emPOWER, Census ACS/CDC SVI, FEMA NSS | Per the repository README: CMS and emPOWER US Government work; FEMA NRI terms of use, attribution required, planning purposes only; NSS US Government work (FEMA and American Red Cross co-attributed) | Base rows and leading columns of the three clean tables; tract centroids; shelters read only for the pending medical-shelter distance |
| HHS emPOWER REST service, county and ZIP layers (fetched 2026-10-27) | `$EXTDATA/emPOWER/empower_ga_{county,zip}.csv` (`EXTDATA`, default `~/work/extdata`) | HHS ASPR / CMS | US Government work, de-identified; use only for emergency preparedness and make no attempt to identify any individual | Canonical live counts (`*_live`); ZIP-to-county for dialysis centers |
| CMS Provider Data: Nursing Home Provider Information, Dialysis Facility listing (GA rows) | `$CMS_DIR/{nursing_homes_ga,dialysis_facilities_ga}.parquet` (`CMS_DIR`) | Centers for Medicare & Medicaid Services | US Government work | Residents per day, CMS beds, provider type, sprinklers; dialysis stations |
| Census Geocoder results for the CMS dialysis addresses | `dialysis_centers_geocoded.csv` (`DIALYSIS_GEOCODED`) | US Census Bureau | US Government work | Dialysis center coordinates and match quality |
| GEMA hurricane evacuation zones (27 polygons) and I-16 contraflow intersections (32 points), fetched 2026-10-27 | `$EXTDATA/gema/{evacuation_zones,contraflow_intersections}.geojson` | Georgia Emergency Management and Homeland Security Agency | No licence stated; cleared for this event with attribution (see below) | `evac_zone` on hazard tracts, care facilities and assisted living; `contraflow_intersections` |
| GEMA WebEOC shelter feed schema (`Shelters_v2_view`; 0 rows on 2026-10-27) | `$EXTDATA/gema/shelters_v2_schema.json` | GEMA/HS | As above | Field list for `gema_shelter_feed`; contact, phone, remarks, subscriber and editor fields are never read |
| GaMap2Care assisted living communities and personal care homes, facility fields only (fetched 2026-10-27) | `$EXTDATA/gamap2care/gamap2care_alc_pch_facility_fields.parquet` | Georgia Department of Community Health, Healthcare Facility Regulation | As above; administrator, email and telephone were never downloaded | `assisted_living` |
| NOAA NCEI Storm Events Database, Georgia and Florida tropical-related events 1996-2025, matched to HURDAT2 storms | `$EXTDATA/ncei_storm_events/ga_fl_tropical.parquet` | NOAA National Centers for Environmental Information | US Government work | `storm_events`, `storm_history` |
| FEMA ESF#6 Shelter System, last activation per shelter, GA and FL (fetched 2026-10-27) | `$EXTDATA/fema_nss/nss_ga_fl_last_activation.parquet` | FEMA, synchronized with the American Red Cross shelter database | US Government work | `shelter_activation_history` |
| Georgia governor evacuation orders, Matthew 2016, Irma 2017, Dorian 2019 | `$EXTDATA/ga_evac_orders/orders.csv` | Governor press releases (URL per row), WTOC where a release is not online | Facts with cited URL; state data cleared with attribution | `evac_orders` |
| NHC GIS advisory archive, storm lead times 2008-2026 | `$EXTDATA/nhc_advisories/storm_lead_times.parquet` | NOAA National Hurricane Center | US Government work | Georgia tropical-storm-wind onset for `evac_orders` |
| DOE Form OE-417 annual summaries 2013-2023 (via Internet Archive captures) | `$EXTDATA/oe417/oe417_ga_fl_weather_events.csv` | US Department of Energy | US Government work | `outage_events` |
| Overture Maps Places, release 2026-10-21.0, Georgia care and transport categories | `places_ga_care_transport.parquet` (`OVERTURE_PLACES`) | Overture Maps Foundation | Per row in `source_license`: CDLA-Permissive-2.0, Apache-2.0 (Foursquare), CC0-1.0 (AllThePlaces) | `overture_places` |

Not used here: GDOT evacuation routes (used by `analysis/flow` as the corridor layer), Census
TIGER/Line roads (used by `analysis/flow` where GDOT has no route), EAGLE-I county outages (used by
`analysis/flow` through the grid analysis), and Georgia DPH OASIS (not needed for these tables). No phone numbers, emails or websites are carried
from any source.

## Licence bar

The repository bar is public domain, CC0 or US Government work, and no non-commercial,
no-derivatives, share-alike, unstated licence or individual-level personal data. On 2026-10-27 the
event organizers ruled that Georgia state and county agency data with no stated licence counts as
government work and may be used with attribution (GDOT, GEMA, GaMap2Care). The personal-data rule
still binds: facility fields only, and personal care homes with 6 or fewer licensed beds, often
family homes in private residences, carry no name or street address and sit at their tract
centroid in every output. A second ruling the same day cleared Overture (CDLA-Permissive-2.0,
Apache-2.0) and EAGLE-I (CC BY 4.0) with attribution.

## Attribution

- Centers for Medicare & Medicaid Services, Provider Data Catalog (data.cms.gov), accessed 2026-10-27.
- HHS emPOWER Program (ASPR/CMS), HHS emPOWER REST Service, accessed 2026-10-27.
- FEMA National Risk Index. For planning purposes only.
- US Census Bureau Geocoder.
- Source: Georgia Emergency Management and Homeland Security Agency (GEMA/HS).
- Source: Georgia Department of Community Health, Healthcare Facility Regulation (GaMap2Care).
- Source: Georgia Department of Transportation (GDOT) EGIS, Office of Transportation Data (`analysis/flow`).
- NOAA National Centers for Environmental Information, Storm Events Database.
- Source: FEMA ESF#6 Shelter System, synchronized with the American Red Cross shelter database.
- Source: NOAA National Hurricane Center, GIS forecast advisory archive.
- Source: U.S. Department of Energy, Form OE-417 Electric Emergency Incident and Disturbance Reports.
- Brelsford et al., EAGLE-I Recorded Electricity Outages, ORNL / DOE CESER, Scientific Data 2024, CC BY 4.0
  (`analysis/flow`).
- Overture Maps Foundation, overturemaps.org. Data from Meta, Microsoft, Foursquare, AllThePlaces and
  others under CDLA Permissive 2.0, Apache 2.0 and CC0.

Foursquare rows (`source_dataset = 'Foursquare'`) are redistributed under Apache 2.0 with this notice:
"Copyright 2024 Foursquare Labs, Inc. All rights reserved. Available under Apache 2.0."
