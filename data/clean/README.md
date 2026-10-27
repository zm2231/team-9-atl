# Clean layer: care facilities, hazard tracts, power-dependent counties (Georgia)

Builds three clean tables from the Georgia snapshot, plus gap-fill and scenario tables, as local Parquet.
Nothing here writes to BigQuery or GCS; `POST.md` holds the load commands for when posting is approved.

```bash
cd data/clean
uv run python -m gaclean.build   # writes out/, CLEANING.md, GAPS.md, POST.md
uv run pytest -q                 # rule tests on fixtures, plus a regression on the real inputs
```

Inputs and licences are in [SOURCES.md](SOURCES.md). The build stops with a list of any missing inputs.

## Outputs (`out/`)

| File | Rows | Key | Leading columns |
|---|---:|---|---|
| `care_facilities.parquet` | 356 | `cms_certification_number_ccn` | the 10 columns of `evacuation_readiness.care_facilities_clean` |
| `hazard_tracts.parquet` | 2,791 | `geo_id` | the 11 columns of `evacuation_readiness.hazard_tracts_clean` |
| `power_dependent_counties.parquet` | 159 | `fips_code` | the 20 columns of `evacuation_readiness.power_dependent_counties_clean` |
| `dialysis_centers.parquet` | 355 | `ccn` | gap fill: CMS dialysis facilities with county and coordinates |
| `assisted_living.parquet` | 1,894 | `FACID` (opaque for small homes) | GaMap2Care assisted living communities and personal care homes |
| `contraflow_intersections.parquet` | 32 | `OBJECTID` | GEMA I-16 contraflow intersections |
| `gema_shelter_feed.parquet` | 0 | `GlobalID` | WebEOC shelter feed, facility and status fields only; an input for the teammate shelters table |
| `storm_events.parquet` | 6,934 | `event_id` | NCEI tropical-related storm events, GA and FL, 1996-2025 |
| `storm_history.parquet` | 192 | `storm_atcf_id`, `state` | per-storm, per-state totals for the scenario library |
| `numbers.json` | | | every count quoted here and in the generated docs |
| `rules.json` | | | the text of every rule named in a `_rule` column |
| `gaps.json` | | | the gap register behind `GAPS.md` |

The leading columns were read from the BigQuery schemas with `bq show --schema` and hold the
snapshot values unchanged, one row per source row. Every cleaned or added column follows with its own
`<column>_status` and `<column>_rule`; the build fails if one is missing. The exceptions are grouped:
`<field>_live_low` shares `<field>_live_status`, dialysis `latitude`, `longitude` and
`coordinates_confidence` share `coordinates_status`, and `storm_history` totals share
`aggregate_status`.

Overture listings are built to `out/held/` (gitignored) and are not committed or posted while their
licence question is open.

Status values: `recorded` (the source has a value), `unrecorded` (the source has none),
`imputed` (filled or assigned by a stated rule; a plain calculation on recorded inputs stays `recorded`), `assumption` (depends on an input not yet settled),
`suspect` (kept but contradicted by a better source), `external` (from a gap-fill source),
`aggregated_small_home` (identity removed, see below).

## Decisions

- **Live emPOWER is canonical.** Georgia has 18,026 Medicare dialysis beneficiaries in the live
  service. The snapshot column `facility_esrd_dialysis_any_dme` sums to 6,009, is kept as published
  and marked `suspect`; it is never labelled dialysis patients. Live power dependence is 106,561
  against the snapshot's 92,567.
- **Suppression.** emPOWER publishes counts of 1 to 10 as 11. Those cells carry value 11,
  `<field>_live_low` = 1 and status `imputed` (72 cells).
- **Dialysis stations.** CMS lists 5,956 stations in 355 centers across 91 counties, about 3.0
  live dialysis beneficiaries per station. Each center's county comes from its ZIP through the
  emPOWER ZIP table; coordinates come from the Census Geocoder, with match quality kept
  (242 exact, 81 non-exact, 32 unmatched).
- **Coastal flood.** `CFLD_EXPP` is NULL for 2,588 tracts outside the NRI coastal-flood layer;
  `cfld_expp_clean` sets those to 0 with status `imputed`.
- **Hurricane exposure.** `hrcn_ealp_pctile` (percentile of `HRCN_EALP`) is the canonical measure;
  `HRCN_AFREQ` is kept beside it.
- **Nursing-home occupancy.** CMS average residents per day over CMS certified beds: 80.8%
  statewide, 2 homes unrecorded. This is an average, not the census on the day of a storm.
- **County of a nursing home.** Imputed from the nearest tract centroid; 11 homes disagree with
  the CMS county text, and both are kept.
- **Medical-shelter distance.** Read-only from the snapshot `shelters` table (`is_medical`), median
  52.1 km. Status `assumption`, pending the teammate `shelters_clean` table.

- **Evacuation zones.** GEMA zone (A-D, X) from the tract centroid or facility point; null outside all
  27 zone polygons. 198 tracts are in a zone (697,384 residents), as are 26 nursing homes and 78
  assisted living or personal care homes.
- **Small personal care homes.** 1,044 of the 1,568 personal care homes have 6 or fewer licensed beds.
  In every output their `FACID` is an opaque key (`pch_small_<county>_<n>`, numbered by tract and
  beds); every other GaMap2Care field except `facility_type` and `licensed_beds` is null; their
  `Latitude`/`Longitude` is the tract centroid, and their distances and evacuation zone are taken
  from it. Status `aggregated_small_home`.
- **County of an assisted living home.** Imputed from the nearest tract centroid; 59 disagree with
  the GaMap2Care county text, and both are kept.
- **Shelter feed.** The WebEOC feed had no rows when fetched. `gema_shelter_feed` fixes its 16
  facility and status fields; 23 contact, phone, remarks and editor fields are never read.
- **Storm history.** NCEI events keep their HURDAT2 match: 6,347 by narrative name (`external`),
  577 by nearest active storm (`imputed`), 10 unmatched.

Rule-by-rule counts are in [CLEANING.md](CLEANING.md); unfilled gaps in [GAPS.md](GAPS.md).
