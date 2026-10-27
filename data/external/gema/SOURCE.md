# GEMA hurricane evacuation zones, I-16 contraflow intersections, WebEOC shelter feed schema

- **Source URL(s):** https://services1.arcgis.com/2iUE8l8JKrP2tygQ/arcgis/rest/services/Georgia_Hurricane_Evacuation_Zones/FeatureServer/11 ; .../Contraflow_Intersections/FeatureServer/0 ; .../Shelters_v2_view/FeatureServer/0
- **Fetched:** 2026-10-27
- **Publisher update date:** Zones service "Evacuation_Zones_08212023", data last edited 2024-03-28. Shelter feed last edited 2026-07-28.
- **License / terms:** None stated (empty `licenseInfo`). Cleared for use with attribution by the event organizers on 2026-10-27 (state agency data counts as government work for this event).
- **Attribution:** Source: Georgia Emergency Management and Homeland Security Agency (GEMA/HS)
- **Coverage:** 27 zone polygons in 11 coastal and near-coastal counties (zones A-D, X for Charlton); 32 contraflow intersections on I-16. The shelter feed (WebEOC) had 0 rows on 2026-10-27; only its schema is saved.
- **Public repo + video safe?** Yes with attribution. The shelter feed has contact name and phone fields (primary_contact, primary_phone, secondary_*, twentyfour_*): never load them.

## Files

- `evacuation_zones.geojson`, 27 features: OBJECTID, Id, County, Zone, AreaAcres, Shape__Area, Shape__Length
- `contraflow_intersections.geojson`, 32 features: OBJECTID, Interstate, Exit_Num, CrossRoad, Type, Comments
- `shelters_v2_schema.json`: layer definition only. Live fields: status, shelter_open_datetime, shelter_closing_datetime, capacity, occupancy, post_impact_capacity, shelter_type, county, address, incidentid
