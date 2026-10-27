# OpenFEMA: GA disaster declarations, IPAWS archived alerts for GA/FL storm windows, GA/FL hurricane Public Assistance + Housing Assistance

- **Source URL(s):** https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries.csv?$filter=state eq 'GA' ; https://www.fema.gov/api/open/v1/IpawsArchivedAlerts?$filter=sent ge '2026-10-05' and sent le '2026-10-18' and geo.intersects(searchGeometry, <GA bbox -85.61,30.36,-80.75,35.0>)
- **Source URL(s) (added 2026-10-27, second pass):** https://www.fema.gov/api/open/v1/IpawsArchivedAlerts?$filter=sent ge '<start>' and sent lt '<end>' (all alerts nationwide per storm window, filtered locally to GA/FL) ; https://www.fema.gov/api/open/v2/PublicAssistanceFundedProjectsDetails?$filter=(stateAbbreviation eq 'GA' or stateAbbreviation eq 'FL') and incidentType in (Hurricane, Tropical Storm, Coastal Storm) ; https://www.fema.gov/api/open/v2/HousingAssistanceOwners and /v2/HousingAssistanceRenters ?$filter=state eq 'GA' or state eq 'FL' ; https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries (GA+FL, Hurricane/Tropical Storm/Coastal Storm, used for the join only)
- **Fetched:** 2026-10-27
- **Publisher update date:** PublicAssistanceFundedProjectsDetails lastRefresh 2026-07-21; HousingAssistanceOwners/Renters lastRefresh 2026-10-27. Declarations lastRefresh up to 2026-10-20; IPAWS dataset lastRefresh 2026-10-08 per OpenFemaDataSets, but it contains alerts sent through 2026-10-25
- **License / terms:** OpenFEMA terms: "This product uses the Federal Emergency Management Agency's OpenFEMA API, but is not endorsed by FEMA." FEMA/DHS logos "may not be used without prior written authorization"; "You may not modify or falsely represent content"; data "cannot be used to make determinations that might affect an individual's rights or eligibility".
- **Terms URL:** https://www.fema.gov/about/openfema/terms-conditions
- **Attribution:** This product uses the Federal Emergency Management Agency's OpenFEMA API, but is not endorsed by FEMA. (Cite endpoint + version + access date, e.g. DisasterDeclarationsSummaries v2, accessed 2026-10-27.)
- **Coverage:** Declarations: all Georgia rows 1953-05-02 to 2026-10-09 (82 disasters). IPAWS: 44 alerts whose geometry touches the GA bounding box (includes FL panhandle/AL/SC edges).
- **Coverage (second pass):** IPAWS: 21,402 alerts touching GA or FL in 17 storm windows (Hermine 2016 to Isaias 2026), 2016-08-28 to 2026-10-16. PA: 7,829 aggregate rows = 67,000 funded projects in 47 GA/FL hurricane/tropical/coastal-storm disasters, incidents 1999-09-13 to 2024-10-05. IA: 46,671 zip-level aggregate rows (owners + renters), 27 disasters with a hurricane-type declaration, 2004-08-11 to 2024-10-05.
- **Public repo + video safe?** Yes, with the non-endorsement statement and no FEMA logo. IPAWS rows are public broadcast alerts; personal-content alerts are excluded (see notes).

## Notes

- EM-3657-GA EXISTS: declarationTitle 'HURRICANE ISAIAS', incidentType 'Tropical Storm', declarationType EM, declared 2026-10-09, incident 2026-10-08 to 2026-10-15, PA only (paProgramDeclared true, IA/IH false), designatedIncidentTypes 'H', 76 designated counties.
- OpenFEMA has no shelter dataset. The only IPAWS dataset is IpawsArchivedAlerts. In the Isaias window it holds 44 alerts in the GA bbox: 21 Tornado Warning, 12 Local Area Emergency, 5 Hurricane Warning (all NWS Tallahassee, FL/AL zones), 1 Storm Surge Warning, plus others. It is sparse, so do not treat it as a complete record of NWS warnings.
- ipaws_..._summary.csv adds the event, senderName and areaDesc fields parsed from the CAP XML.

## Notes: IPAWS GA/FL storm windows (`ipaws_ga_fl_tropical.parquet`)

- Windows (UTC, start inclusive, end exclusive): Hermine2016 08-28..09-05, Matthew2016 10-02..10-11, Irma2017 09-04..09-14, Michael2018 10-06..10-14, Dorian2019 08-27..09-08, Isaias2020 07-30..08-06, Sally2020 09-12..09-19, Zeta2020 10-26..10-31, Elsa2021 07-03..07-10, Fred2021 08-12..08-19, Ian2022 09-23..10-03, Nicole2022 11-06..11-13, Idalia2023 08-26..09-02, Debby2024 08-02..08-11, Helene2024 09-22..09-30, Milton2024 10-04..10-13, Isaias2026 10-05..10-19. Every alert in each window was downloaded nationwide (155,896 total) and filtered locally, which is more complete than the bbox filter used for the first Isaias pass (alerts without searchGeometry are kept here).
- Kept when status=Actual AND (a SAME geocode is 012xxx/013xxx, OR a UGC starts FL/GA, OR the sender names FL/GA) AND the text/event concerns evacuation, hurricane, tropical storm/depression, storm surge or shelter (or SAME code EVI/HUW/HUA/TRW/TRA/SSW/SSA/SPW).
- Dropped as personal data: alerts matching missing/endangered/year-old/last seen/AMBER/Silver/suspect/wanted/escaped/inmate/abduct unless they also mention a hurricane/tropical storm/surge (none of the kept rows match those terms).
- `evac_action`: `order` = event Evacuation Immediate (EVI) or a non-NWS sender's text with mandatory evacuation / evacuation order / evacuate now / leave now; `recommend` = voluntary / recommended / urged; `lifted_or_reentry`; `mention`; `none`. NWS-originated warnings get `nws_text_mentions_evacuation` instead, because their boilerplate ("follow evacuation orders from local officials") is not an order. `orders_evacuation` and `recommends_evacuation` are booleans of that. `storm_related` is a keyword heuristic: some orders in the windows are unrelated local incidents (e.g. Rockdale County GA 2024-10-07) and some storm orders lack keywords (Cumberland Island visitors, Helene 2024-09-24).
- The archive is sparse and uneven. 2016-2022 windows hold 7k-18k alerts nationwide (mostly NWS relays); 2023-2026 windows hold only 460-902 nationwide. Few counties send evacuation orders through IPAWS: 71 `order` rows in total, 7 touching GA. Absence of an IPAWS order does NOT mean no order was issued (e.g. Georgia's coastal evacuations for Matthew 2016, Irma 2017 and Dorian 2019 are not in this archive).
- `ga_fl_county_fips` is derived from SAME codes (last 5 digits). Text fields (`headline`, `description`, `instruction`, `cmam_text`, `cmam_long_text`) are the public alert text.

## Notes: Public Assistance + Housing Assistance

- `ga_fl_hurricane_pa.parquet` aggregates PublicAssistanceFundedProjectsDetails (one row per disaster x county x damage category x project size): n_projects, n_applicants (distinct public-entity applicant ids), project_amount_usd, federal_share_obligated_usd, total_obligated_usd, first/last obligation date. Applicants are governments and eligible non-profits, not individuals; per-project titles are dropped. 15 FL projects (disaster 3561, an EM) have no matching declaration title.
- `ga_fl_hurricane_ia.parquet` is HousingAssistanceOwners + HousingAssistanceRenters as FEMA publishes them (already aggregated to disaster x county x city x zip; no registrant records), restricted to GA/FL disasters with a Hurricane, Tropical Storm or Coastal Storm declaration and tagged with `tenure` and the declaration title. Helene (DR-4830-GA) and Milton are included; Isaias 2026 (EM-3657, PA only) has no IA.

## Files

### `ga_disaster_declarations.parquet`: 2,844 rows

Columns: femaDeclarationString, disasterNumber, state, declarationType, declarationDate, fyDeclared, incidentType, declarationTitle, ihProgramDeclared, iaProgramDeclared, paProgramDeclared, hmProgramDeclared, incidentBeginDate, incidentEndDate, disasterCloseoutDate, tribalRequest, fipsStateCode, fipsCountyCode, placeCode, designatedArea, declarationRequestNumber, declarationRequestDate, lastIAFilingDate, incidentId, region, designatedIncidentTypes, lastRefresh, hash, id

### `ipaws_ga_bbox_2026-10-05_to_10-18.jsonl`: 44 rows

Columns: originalMessage, identifier, sender, sent, status, msgType, source, scope, restriction, addresses, code, note, searchGeometry, incidents, cogId, id, xmlns, info

### `ipaws_ga_bbox_2026-10-05_to_10-18_summary.csv`: 44 rows

Columns: identifier, sent, status, msgType, event, senderName, areaDesc, searchGeometry

### `ipaws_ga_fl_tropical.parquet`: 21,402 rows

Columns: id, identifier, storm_window, sent_utc, msg_type, sender, sender_name, is_nws, event, same_event_codes, urgency, severity, certainty, response_type, headline, area_desc, same_geocodes, ga_fl_county_fips, ugc_geocodes, states, effective, expires, evac_action, storm_related, orders_evacuation, recommends_evacuation, mentions_shelter_open, description, instruction, cmam_text, cmam_long_text

### `ga_fl_hurricane_pa.parquet`: 7,829 rows

Columns: declaration_title, declaration_type, incident_begin, disaster_number, incident_type, state, county, county_fips, damage_category_code, damage_category, project_size, n_projects, n_applicants, project_amount_usd, federal_share_obligated_usd, total_obligated_usd, first_obligation_date, last_obligation_date

### `ga_fl_hurricane_ia.parquet`: 46,671 rows

Columns: tenure, declaration_title, declaration_type, incident_type, incident_begin, disasterNumber, state, county, city, zipCode, validRegistrations, averageFemaInspectedDamage, totalInspected, totalDamage, noFemaInspectedDamage, femaInspectedDamageBetween1And10000, femaInspectedDamageBetween10001And20000, femaInspectedDamageBetween20001And30000, femaInspectedDamageGreaterThan30000, approvedForFemaAssistance, totalApprovedIhpAmount, repairReplaceAmount, rentalAmount, otherNeedsAmount, approvedBetween1And10000, approvedBetween10001And25000, approvedBetween25001AndMax, totalMaxGrants, totalInspectedWithNoDamage, totalWithModerateDamage, totalWithMajorDamage, totalWithSubstantialDamage
