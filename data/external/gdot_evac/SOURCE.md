# Georgia DOT hurricane evacuation routes, contraflow route, I-16 contraflow gates

- **Source URL(s):** https://enterprisegis.dot.ga.gov/server/rest/services/EOC/EOC_RESPONSE_LAYERS/MapServer/11 (Hurricane Evacuation Routes), /12 (Contraflow Route); https://enterprisegis.dot.ga.gov/server/rest/services/EOC/Contraflow/MapServer/0 (I-16 gate arms & crossovers). Queried as GeoJSON, outSR 4326.
- **Fetched:** 2026-10-27
- **Publisher update date:** Evacuation routes carry an ADDED2026 field (reported as updated March 2026). Contraflow gates were first published Aug 2020 and are updated as needed.
- **License / terms:** Georgia DOT (state government). No license stated: the ArcGIS licenseInfo is empty and accessInformation reads 'GDOT EGIS'. The service is publicly queryable without login.
- **Terms URL:** https://enterprisegis.dot.ga.gov/server/rest/services/EOC
- **Attribution:** Source: Georgia Department of Transportation (GDOT) EGIS, Office of Transportation Data
- **Coverage:** 98 evacuation route segments (statewide coastal), 12 contraflow route features, 123 I-16 gate/crossover points
- **Public repo + video safe?** Probably OK but unlicensed (state public data, no stated terms). Attribute GDOT. Low risk, but there is no explicit grant.

## Files

### `hurricane_evacuation_routes.geojson`: 98 rows

Columns: OBJECTID, SHAPE.LEN, ROUTE_ID, FROM_MILEPOINT, TO_MILEPOINT, MILES, ADDED2026

### `hurricane_evacuation_contraflow_route.geojson`: 12 rows

Columns: OBJECTID, TITLE, DESCRIPTION, DATE_, SE_ANNO_CAD_DATA, SHAPE.LEN

### `i16_contraflow_gates_crossovers.geojson`: 123 rows

Columns: OBJECTID, INTERSTATE, DIRECTION, EXIT_NUM, ON_OFF_RAMP, TOP_BOTTOM, NUM_GATES, LATITUDE, LONGITUDE, PHOTO_NAME
