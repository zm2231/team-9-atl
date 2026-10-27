# Overture Maps Places, Atlanta metro bbox (release 2026-10-21.0)

- **Source URL(s):** s3://overturemaps-us-west-2/release/2026-10-21.0/theme=places/type=place/* (anonymous AWS S3, read with DuckDB; bbox xmin -84.85..-83.95, ymin 33.40..34.15)
- **Fetched:** 2026-10-27
- **Publisher update date:** Release 2026-10-21.0
- **License / terms:** Per-source: CDLA-Permissive-2.0 (273,351 rows: Meta, Microsoft, etc.), Apache-2.0 (19,267 rows: Foursquare, "Copyright 2024 Foursquare Labs, Inc. All rights reserved. Available under Apache 2.0."), CC0-1.0 (4,341 rows: AllThePlaces). The per-row source_license column is kept.
- **Terms URL:** https://docs.overturemaps.org/attribution/
- **Attribution:** Overture Maps Foundation, overturemaps.org. Data from Meta, Microsoft, Foursquare (Apache 2.0), AllThePlaces (CC0) et al. under CDLA Permissive 2.0.
- **Coverage:** 296,959 places in the bbox (Fulton, DeKalb, Cobb, Gwinnett, Clayton core). Community-anchor subset: 7,726 worship, 1,271 grocery, 1,222 convenience, 305 community/senior, 243 food bank/farmers market (operating_status open or null).
- **Public repo + video safe?** Yes (permissive). Include the Overture + Foursquare attribution and ship the Foursquare NOTICE if you redistribute the Apache-2.0 rows.

## Notes

- The overturemaps CLI (v0.x) failed: its STAC catalog fetch returned HTTP 403 via urllib, even with -r and --no-stac. DuckDB against the public S3 bucket worked. This is AWS, not Google Cloud.
- 15,044 rows are permanently_closed. They are excluded from the anchors subset but kept in _all.

## Files

### `places_atl_metro_all.parquet`: 296,959 rows

Columns: id, name, category, taxonomy_hierarchy, alt_categories, operating_status, basic_category, confidence, address, locality, postcode, region, website, phone, lon, lat, source_dataset, source_license

### `places_atl_metro_community_anchors.parquet`: 10,767 rows

Columns: id, name, category, taxonomy_hierarchy, alt_categories, operating_status, basic_category, confidence, address, locality, postcode, region, website, phone, lon, lat, source_dataset, source_license, anchor_type

### `places_ga_care_transport.parquet`: 8,401 rows (statewide GA, fetched 2026-10-27)

Same release and S3 path; filter `addresses[1].region` = GA and `taxonomy.primary` matching assisted_living, retirement_home, nursing, ambulance, medical_transportation, dialysis, senior_citizen_service, home_health, hospice, urgent_care, hospital. Licences: CDLA-Permissive-2.0 8,000, Apache-2.0 314, CC0-1.0 87. Phones, emails and websites were not pulled. No bed counts. Columns: id, name, category, confidence, address, locality, postcode, lon, lat, source_dataset, source_license, operating_status.
