# Scenario package contract

Module boundaries for the three build lanes. Runtime code is numpy plus the standard library; no network at import; artifacts under `data/` stay under 5 MB in total.

## Lane A: engine (`scenario-engine` branch)

| Module | Public API |
|---|---|
| `windfield.py` | `TrackPoint(hour, lat, lon, vmax_kt, rmw_km, r34_km)`; `interpolate_hourly(points)`; `exposure(track, lats, lons) -> dict[str, np.ndarray]` with keys `peak_wind_kt`, `hours_34kt`, `hours_50kt`, `hours_64kt`, `min_dist_km`, `first_34kt_hour` (NaN when never reached). Vectorized over counties; must match the scalar `county_exposure` to 1e-6 |
| `model.py` | `FEATURES = ["peak_wind_kt", "hours_34kt", "hours_50kt", "min_dist_km", "pop"]`; `transform(x)`; `OutageModel.load()`; `.sample(features, rng, n_draws) -> np.ndarray (n_draws, n_counties)`, one storm effect per draw shared across counties |
| `storms.py` | `analog_tracks(lat, lon, heading_deg, month, intensity_kt=None, max_tracks=40) -> list[Analog]`, each analog's track re-timed so hour 0 is the matched point and shifted so that point sits on the requested position; `drawn_track(lonlats, category, forward_kmh=20) -> list[TrackPoint]`; `climatology() -> list[Analog]` (every storm since 1950 within 250 km of Georgia, with annual weight); `classify_origin(lat, lon)` |
| `engine.py` | `run(tracks, *, n_draws, seed) -> Result` with per-county arrays (`outage` draws, `peak_wind_kt`, `hours_34kt`, `ts_arrival_h`) and per-track support flags; `people_at_risk(result, counties) -> dict` |
| `data.py` | `counties()`, `sites()`, `tracks()`, `model_npz()`, cached loaders over `data/*.json` and `data/outage_model.npz` |

`Analog`: `sid`, `name`, `season`, `track` (list of `TrackPoint`), `weight`, `intensity_kt_at_match`, `reached_ga_100km` (bool).

`counties.json` row: `county_fips`, `county_name`, `lat`, `lon`, `pop`, `power_dependent`, `oxygen`, `home_health`, `dialysis_patients`, `power_dependent_censored`, `nursing_home_beds`, `assisted_living_beds`.

## Lane B: season and site data (`scenario-season` branch)

| Piece | Output |
|---|---|
| Surge flags | `data/sites.json`: every medical shelter and dialysis centre gets `in_surge` = list of categories 1-5 whose SLOSH maximum-of-maximums zone covers it. Also `data/surge_zones.geojson` simplified per category for the map, under 1.5 MB |
| Facility beds | `nursing_home_beds` per county by spatial join of `care_facilities_clean` to Census county boundaries; `assisted_living_beds` from `ext_ga_assisted_living.county_fips` |
| Season build | `build/build_season.py`: about 2,000 events from `storms.climatology()`, `engine.run`, people at risk, receiving capacity; writes `evac_prod.scenario_season_county` and `evac_prod.scenario_fix_ranking`; back-test against 2018-2025 |

## Lane D: movement (`scenario-movement` branch)

| Module | Public API |
|---|---|
| `movement.py` | `drive_times(origin_latlon, dests) -> list[dict]` with `minutes`, `km`, `status` (`live` or `straight_line`); Routes `computeRouteMatrix`, `X-Goog-Api-Key` from `ROUTES_API_KEY`, else ADC + `X-Goog-User-Project`; 8 s timeout; never raises. `corridor_for(origin_county_fips, dest_latlon) -> str or None`; `delay_multiplier(corridor, origin_class, case) -> float` = 1 + 0.15 (v/c)^4 capped at 4, from `data/corridor_vc.json` |
| `receiving.py` | `receiving_sites(county, sites, usable, origin_class, case, ts_arrival_h, top=8) -> list[dict]` per `RUN_SCENARIO_SPEC.md` |

## Integration (orchestrator)

`readiness_agent/scenario_tools.py`: `run_scenario`, `season_county_risk`, `gap_sensitivity`; registration in `agent.py`; `numpy` pinned in `agent/requirements.txt`; tests in `agent/tests/`.
