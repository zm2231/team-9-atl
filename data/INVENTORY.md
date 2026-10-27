# C4 data inventory

Everything the Georgia scenario work can draw on, as of 2026-10-27. BigQuery project `qwiklabs-gcp-04-edc952746633` (US). Local copies are in the team repo, branch `data-external`, under `data/external/` (193 MB, no LFS); every folder there has a `SOURCE.md` with URL, licence evidence and columns.

## BigQuery

### `evac_prod` (47 tables)

Single source of truth for the agent. Snapshots of the above plus `ext_*` external tables. Lead's refresh script owns non-`ext_*`/`scenario_*` names.

| Table | Rows |
|---|---:|
| `assisted_living_flow_staging` | 1,894 |
| `care_facilities_clean` | 356 |
| `care_facilities_flow_staging` | 356 |
| `contraflow_intersections_flow_staging` | 32 |
| `county_grid_reliability` | 159 |
| `county_storm_outages` | 1,431 |
| `dialysis_centers_flow_staging` | 355 |
| `ext_ga_assisted_living` | 1,894 |
| `ext_ga_gdot_hurricane_evacuation_contraflow_route` | 12 |
| `ext_ga_gdot_hurricane_evacuation_routes` | 98 |
| `ext_ga_gdot_i16_contraflow_gates_crossovers` | 123 |
| `ext_ga_gema_contraflow_intersections` | 32 |
| `ext_ga_gema_evacuation_zones` | 27 |
| `ext_ga_hospital_capacity_2023_24` | 137 |
| `ext_ga_hrsa_health_center_sites` | 466 |
| `ext_ga_lodes_rac_tract_2023` | 2,791 |
| `ext_ga_lodes_wac_tract_2023` | 2,787 |
| `ext_ga_nces_public_schools_2425` | 2,349 |
| `ext_ga_overture_care_transport` | 8,401 |
| `ext_ga_tiger_prisec_roads` | 11,754 |
| `scenario_storm_county_exposure` | 8,362 |
| `scenario_outage_model_loso` | 81 |
| `ext_hurdat2_atlantic` | 55,524 |
| `ext_ntd_agencies_2025` | 1,140 |
| `ext_ntd_revenue_vehicles_2025` | 16,794 |
| `fema_disaster_declarations` | 2,844 |
| `fema_individual_assistance` | 46,671 |
| `fema_public_assistance` | 7,829 |
| `ga_evacuation_orders` | 4 |
| `hazard_tracts_clean` | 2,791 |
| `hazard_tracts_flow_staging` | 2,791 |
| `ipaws_alerts` | 21,402 |
| `nhc_advisories` | 9,157 |
| `nhc_advisory_cones` | 1,314 |
| `nhc_forecast_points` | 12,463 |
| `nws_tropical_alerts` | 7,531 |
| `outage_events_oe417` | 73 |
| `power_dependent_counties_clean` | 159 |
| `power_dependent_counties_flow_staging` | 159 |
| `shelter_activation_history` | 4,590 |
| `shelters_clean` | 1,792 |
| `storm_events_ncei` | 6,934 |
| `storm_lead_times` | 54 |
| `storm_tracks_ibtracs` | 44,489 |
| `utility_reliability_eia861` | 812 |
| `utility_service_territory_eia861` | 7,760 |
| `vulnerability_tracts_clean` | 2,796 |

### `hurricane_history` (18 tables)

Storm history loaded by the lead: tracks, advisories, warnings, alerts, outages, FEMA aid, shelter activations.

| Table | Rows |
|---|---:|
| `county_grid_reliability` | 159 |
| `county_storm_outages` | 1,431 |
| `fema_disaster_declarations` | 2,844 |
| `fema_individual_assistance` | 46,671 |
| `fema_public_assistance` | 7,829 |
| `ga_evacuation_orders` | 4 |
| `ipaws_alerts` | 21,402 |
| `nhc_advisories` | 9,157 |
| `nhc_advisory_cones` | 1,314 |
| `nhc_forecast_points` | 12,463 |
| `nws_tropical_alerts` | 7,531 |
| `outage_events_oe417` | 73 |
| `shelter_activation_history` | 4,590 |
| `storm_events_ncei` | 6,934 |
| `storm_lead_times` | 54 |
| `storm_tracks_ibtracs` | 44,489 |
| `utility_reliability_eia861` | 812 |
| `utility_service_territory_eia861` | 7,760 |

### `evacuation_readiness` (18 tables)

Event GA tables (organizer-provided) plus teammates' `*_clean` and `*_flow_staging`. Owned by teammates; read only.

| Table | Rows |
|---|---:|
| `assisted_living_flow_staging` | 1,894 |
| `care_facilities` | 356 |
| `care_facilities_clean` | 356 |
| `care_facilities_flow_staging` | 356 |
| `contraflow_intersections_flow_staging` | 32 |
| `dialysis_centers_flow_staging` | 355 |
| `hazard_tracts` | 2,791 |
| `hazard_tracts_clean` | 2,791 |
| `hazard_tracts_flow_staging` | 2,791 |
| `power_dependent_counties` | 159 |
| `power_dependent_counties_clean` | 159 |
| `power_dependent_counties_flow_staging` | 159 |
| `shelters` | 1,792 |
| `shelters_clean` | 1,792 |
| `storm_events_flow_staging` | 6,934 |
| `storm_history_flow_staging` | 192 |
| `vulnerability_tracts` | 2,796 |
| `vulnerability_tracts_clean` | 2,796 |

### `evacuation_readiness_fl` (5 tables)

Event FL tables (organizer-provided). Read only.

| Table | Rows |
|---|---:|
| `care_facilities` | 694 |
| `hazard_tracts` | 5,114 |
| `power_dependent_counties` | 67 |
| `shelters` | 2,793 |
| `vulnerability_tracts` | 5,160 |

## Local external tables (`data/external/` on branch `data-external`)

| Folder | Files | Size | Licence (from SOURCE.md) |
|---|---|---|---|
| `acs/` | 43 | 15.4 MB | U.S. Government work (17 U.S.C. 105), no copyright. Census confidentiality terms apply: users "will not use th |
| `c4_capabilities/` | 2 | 0.1 MB |  |
| `cms/` | 2 | 0.4 MB | U.S. Government work (CMS). The metastore 'license' field is empty for both datasets, and no dataset-specific  |
| `cre/` | 1 | 2.2 MB | U.S. Government work. No dataset-specific license. Census Bureau policy DS027 (https://www2.census.gov/foia/ds |
| `eagle_i/` | 26 | 51.9 MB | CC BY 4.0. figshare API `license` field: `{'value': 1, 'name': 'CC BY 4.0', 'url': 'https://creativecommons.or |
| `eia861/` | 2 | 0.1 MB | U.S. Government work (EIA), public domain. Attribution: Source: U.S. Energy Information Administration, Form E |
| `emPOWER/` | 2 | 0.1 MB | Federal (ASPR/CMS) de-identified data; the service is described as "publicly available, and can be consumed an |
| `fema_nss/` | 1 | 0.3 MB | US Government work (FEMA), co-attributed with the American Red Cross, as in the packet README:697 |
| `ga_evac_orders/` | 1 | 0.0 MB | Facts extracted from state press releases and news reports; state data cleared by organizer ruling 2026-10-27. |
| `gdot_evac/` | 3 | 2.1 MB | Georgia DOT (state government). No license stated: the ArcGIS licenseInfo is empty and accessInformation reads |
| `gema/` | 3 | 2.0 MB | None stated (empty `licenseInfo`). Cleared for use with attribution by the event organizers on 2026-10-27 (sta |
| `group_quarters/` | 2 | 1.2 MB | U.S. Government work. Census Bureau policy DS027 (https://www2.census.gov/foia/ds_policies/ds027.pdf): "Data/w |
| `hospital_capacity/` | 2 | 3.0 MB | U.S. Government work (CDC/HHS), published on Socrata open data portals. No dataset-specific license restrictio |
| `hrsa_sites/` | 1 | 1.3 MB | U.S. Government work (HHS/HRSA). No dataset-specific license found on data.hrsa.gov (footer links to HHS discl |
| `hurdat2/` | 1 | 0.7 MB | NOAA/NHC, U.S. Government work (public domain under 17 U.S.C. 105). No separate license text published on the  |
| `ibtracs/` | 2 | 2.4 MB | NOAA/NCEI data, U.S. Government work. NCEI: IBTrACS follows the World Data Center for Meteorology policy of "f |
| `lodes/` | 3 | 1.0 MB | U.S. Government work (Census Bureau), public domain. Census confidentiality terms apply (no re-identification) |
| `ncei_storm_events/` | 1 | 0.2 MB | U.S. Government work (NOAA/NWS, 17 U.S.C. 105, public domain). NCEI metadata (gov.noaa.ncdc:C00510): "Access C |
| `nces/` | 3 | 1.7 MB | U.S. Department of Education / NCES, U.S. Government work (public domain). |
| `nhc_advisories/` | 4 | 23.2 MB | NOAA/NWS, U.S. Government work (public domain, 17 U.S.C. 105). NWS disclaimer: "The information on National We |
| `ntd/` | 3 | 1.2 MB | Socrata license field: "Public Domain U.S. Government", termsLink https://www.usa.gov/government-works |
| `nws_vtec/` | 1 | 0.1 MB | IEM disclaimer: "The materials found on this website are in the public domain and may be used freely by anyone |
| `oe417/` | 1 | 0.0 MB | US Government work (Department of Energy, Form OE-417 is a mandatory federal filing published by DOE). Not sub |
| `openfema/` | 5 | 13.2 MB | OpenFEMA terms: "This product uses the Federal Emergency Management Agency's OpenFEMA API, but is not endorsed |
| `overture/` | 1 | 0.7 MB | Per-source: CDLA-Permissive-2.0 (273,351 rows: Meta, Microsoft, etc.), Apache-2.0 (19,267 rows: Foursquare, "C |
| `places/` | 2 | 2.9 MB | Socrata metadata `license` field: "Public Domain" (licenseId `PUBLIC_DOMAIN`) for both yjkw-uj5s and cwsq-ngmh |
| `slosh/` | 11 | 72.2 MB | NOAA/NWS, U.S. Government work (public domain). NWS disclaimer: "The information on National Weather Service ( |
| `tiger/` | 1 | 2.2 MB |  |

## Derived scenario files (repo branch `data-external`, `data/scenario/`; also in `evac_prod.scenario_*`)

| File | What | Status |
|---|---|---|
| `data/scenario/storm_county_exposure.parquet` | 37 storms 2014-2025 within 250 km of GA x 226 GA+FL counties: modelled county wind exposure (peak wind, hours >= 34/50/64 kt, min distance) + EAGLE-I peak outage share in a closest-approach window (-24 h, +48 h), status `recorded`/`carryover`/`suspect` | provisional; to be replaced by g-grid's extended `county_storm_outages` |
| `data/scenario/outage_model_loso.json` | Leave-one-storm-out results, hierarchical vs boosted trees | see `data/CLAIMS.md` |
| `c4-scenario-packet/` | Codex build packet: model spec, factor table, flow integration, interface, prototype | reference |
| `c4-capabilities/out/` | Statewide medical capability summary, geocoded dialysis centres | in repo under `data/external/c4_capabilities/` |

## Known gaps

Full list with sizes and handling: `c4-gap-sources.md` (and g-flow's `GAPS.md`). The ones that bound claims: no shelter-level fill history; nursing-home and shelter generator status mostly unrecorded; no pre-2018 trustworthy county outages; no trustworthy Atlantic direct-landfall outage example in Georgia; HES clearance times only in HURREVAC (EM-only); no GA coastal IPAWS evacuation orders before 2022.
