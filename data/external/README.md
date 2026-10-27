# External data (Georgia C4)

Every external table the team uses, copied from the prework pulls on 2026-10-27 so the repo holds them without Git LFS (every file is under 45 MB). Each folder has a `SOURCE.md` with URL, fetch date, licence evidence, attribution and columns.

Licence bar: public domain, CC0, US Government work, Georgia state data cleared by the organizers on 2026-10-27, and attribution-only licences (CC BY 4.0, CDLA-Permissive-2.0, Apache-2.0) approved the same day. No contact fields. GaMap2Care is not here in raw form: use `data/local/clean` (`assisted_living`), where homes with 6 or fewer beds carry no name or address. Transit GTFS feeds and non-C4 challenge data are left out.

`eagle_i/outages_15min/` splits the 24.8M-row 15-minute series by state and year. `nhc_advisories/` holds the parsed tables, not the 2,441 raw zips. `c4_capabilities/` holds the Census-geocoded dialysis centers and the statewide capability summary.

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
