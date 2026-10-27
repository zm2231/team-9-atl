# NHC National Storm Surge Hazard Maps (SLOSH MOM inundation v4), Georgia coast clip

- **Source URL(s):** https://www.nhc.noaa.gov/gis/hazardmaps/US_SLOSH_MOM_Inundation_v4.zip (landing page https://www.nhc.noaa.gov/nationalsurge/)
- **Fetched:** 2026-10-27; 1,649,453,905 bytes downloaded with `curl -C -` in 26 s (15:43:23 to 15:43:49 UTC). The zip was deleted after clipping; re-fetch from the URL above.
- **Publisher update date:** zip Last-Modified 2026-06-18; folder US_SLOSH_MOM_Inundation_v4_20260617; metadata date 2026-06-14 (NHC Storm Surge Unit).
- **License / terms:** NOAA/NWS, U.S. Government work (public domain). NWS disclaimer: "The information on National Weather Service (NWS) Web pages are in the public domain, unless specifically noted otherwise, and may be used without charge for any lawful purpose".
- **Terms URL:** https://www.weather.gov/disclaimer
- **Attribution:** Source: NOAA National Hurricane Center, National Storm Surge Hazard Maps (SLOSH MOMs), v4, high-tide scenario.
- **Coverage:** Bounding box lon -81.85 to -80.75, lat 30.65 to 32.25 (whole GA coast: Chatham, Bryan, Liberty, McIntosh, Glynn, Camden; also takes in the edges of Beaufort/Jasper Co. SC and Nassau Co. FL). Categories 1-5, high-tide initial water level. 12,245 x 17,811 cells at 8.98e-5 degrees (about 8.5 m x 9.9 m), EPSG:4269.
- **Public repo + video safe?** Yes (public domain). Label as a worst-case planning composite (Maximum of MEOWs), not a forecast of any one storm.

## Notes

- No GA-only or basin-level product exists on the NHC server: https://www.nhc.noaa.gov/gis/hazardmaps/ lists only the US national zips (2017 214 MB, 2022 1.6 GB, 2026 1.5 GB) plus territories, Bahamas, Caymans, Hispaniola, Yucatan. The old SLOSH Display Program per-basin MOM shapefiles (sv4mom.zip) 404 (see earlier probe).
- Raster values are uint8 classes, 255 = nodata (not inundated or outside SLOSH coverage). Class meaning is in the *_vat.csv files: value N (1-20) = "N-1 to N feet above ground", 21 = "Greater than 20 feet above ground", 99 = "Levee Areas - Consult Local Officials for flood risk" (no 99 cells fall inside the GA clip).
- Source rasters are LERC-compressed; clips were re-written as tiled deflate GeoTIFFs with the same values. Script (scratchpad, not in repo): slosh_clip.py.

## Files

### `ga_coast_cat{1..5}_mom_inundation_high.tif`: 5 GeoTIFFs, 10.3 / 12.9 / 16.5 / 16.6 / 15.9 MB

Single band uint8, nodata 255, EPSG:4269, 12,245 x 17,811 cells.

### `ga_coast_cat{1..5}_vat.csv`: 5 files, one row per class value

Columns: Value, Count (national cell count from the source VAT), data_range

### `ga_coast_class_counts.csv`: one row per category x class within the clip

Columns: category, value, cells, approx_area_km2 (cells x 8.5 m x 9.9 m at lat 31.45)
