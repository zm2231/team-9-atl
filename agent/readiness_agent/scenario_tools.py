import json
from datetime import UTC, datetime
from datetime import date as Date
from pathlib import Path
from typing import Any

from . import report
from .evacuation_tools import QueryTooLargeError, _dataset_name, _project_id, _run_query

CONTEXT_PREFIX = "CONTEXT v1 "
_MODEL = json.loads(
    (Path(__file__).parent / "scenario" / "data" / "outage_model_metrics.json").read_text()
)
_YEARS = sorted(int(p["storm"].rsplit(" ", 1)[-1]) for p in _MODEL["per_storm"])
MODEL_FACTS = (
    f"{_MODEL['storms']} storms {_YEARS[0]}-{_YEARS[-1]}, {_MODEL['rows']:,} county-storm rows; "
    f"held-out storms: {_MODEL['inside_10_90']:.0%} of counties inside the 10-90 range"
)
RANGE_LABEL = f"scenario range from {_MODEL['storms']} past storms"
SOURCES = {
    "scenario": (
        f"Simulated · outage model fitted on DOE EAGLE-I county outages ({MODEL_FACTS}; "
        f"{_MODEL['label_table']}) and NOAA IBTrACS tracks; residents at risk from HHS emPOWER "
        "(power_dependent_counties_clean)"
    ),
    "season": (
        "Simulated · storm exposure from NOAA IBTrACS tracks since 1950; outage response fitted on "
        f"EAGLE-I labels ({MODEL_FACTS}) (scenario_season_county)"
    ),
    "gaps": "Simulated · season model rerun with each unknown set low and high (scenario_fix_ranking)",
    "reports": "Precomputed · scenario_reports, built by scenario/build/build_reports.py",
    "audit": "Survey · ACS 2020-2024 B03002, audit only, never a model input (ext_ga_acs_race_tract)",
}
NOT_DETERMINED = "not_determined"
TOP_COUNTIES = 20
N_DRAWS = 400
MAX_DRAWS = 2000
SEED = 20261027
CASES = ("low", "base", "high")
AFFECTED_SHARE = 0.10
DIALYSIS_DOWN_SHARE = 0.50
CATEGORY_FLOOR_KT = {0: 34, 1: 64, 2: 83, 3: 96, 4: 113, 5: 137}
RELOCATION_SHARE = {"low": 0.10, "base": 0.20, "high": 0.40}
SITE_UPDATES_TABLE = "scenario_site_updates"
SITING_TABLE = "scenario_siting"
SITING_POOL = 60
SOURCES["planner"] = (
    "Planner-reported site updates (scenario_site_updates), shown next to the registry"
)
SOURCES["conditions"] = (
    "Live NOAA inputs (CPC ONI, PSL Tropical North Atlantic SST, CPC ENSO discussion, CPC seasonal "
    "hurricane outlook) with a conditions model back-tested on 1950-2025 storms near Georgia"
)
AUTO = "auto"
SOURCES["siting"] = (
    "Simulated · season model rerun with each candidate site added (scenario_siting); "
    "shelters from shelters_clean, counties from Census population centres"
)


def _context(tool_context: Any) -> dict[str, Any]:
    content = getattr(tool_context, "user_content", None)
    for part in getattr(content, "parts", None) or []:
        text = (getattr(part, "text", None) or "").strip()
        if text.startswith(CONTEXT_PREFIX):
            try:
                value = json.loads(text[len(CONTEXT_PREFIX) :])
            except json.JSONDecodeError:
                return {}
            return value if isinstance(value, dict) else {}
    return {}


def _track_lonlats(scenario: dict[str, Any]) -> list[tuple[float, float]]:
    geometry = scenario.get("track")
    if isinstance(geometry, dict) and geometry.get("type") == "Feature":
        geometry = geometry.get("geometry")
    if not isinstance(geometry, dict):
        return []
    coords = geometry.get("coordinates")
    if geometry.get("type") == "Point":
        coords = [coords]
    if not isinstance(coords, list):
        return []
    points = []
    for c in coords:
        try:
            lon, lat = float(c[0]), float(c[1])
        except (TypeError, ValueError, IndexError, KeyError):
            continue
        if -180 <= lon <= 180 and -90 <= lat <= 90:
            points.append((lon, lat))
    return points


def _category(value: Any) -> int | None:
    try:
        category = int(value)
    except (TypeError, ValueError):
        return None
    return category if 0 <= category <= 5 else None


def _ids(value: Any) -> tuple[set[str], list[str]]:
    if value is None:
        return set(), []
    if not isinstance(value, list):
        return set(), [repr(value)]
    valid = {v for v in value if isinstance(v, str) and v}
    invalid = [repr(v) for v in value if not (isinstance(v, str) and v)]
    return valid, invalid


def _switches(scenario_ctx: dict[str, Any], sites_off: Any, assume_generator: Any) -> dict:
    overrides = scenario_ctx.get("site_overrides")
    invalid: list[str] = []
    if overrides is not None and not isinstance(overrides, dict):
        invalid.append(repr(overrides))
        overrides = {}
    overrides = overrides or {}
    out: dict[str, Any] = {}
    for key, arg, ctx_key in (
        ("sites_off", sites_off, "off"),
        ("assume_generator", assume_generator, "assume_generator"),
    ):
        a_valid, a_bad = _ids(arg)
        c_valid, c_bad = _ids(overrides.get(ctx_key))
        out[key] = frozenset(a_valid | c_valid)
        invalid += a_bad + c_bad
    out["invalid"] = invalid
    return out


def _status(status: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"status": status, "message": message, **extra, "source": SOURCES["scenario"]}


def _fetch_site_updates() -> list[dict[str, Any]]:
    table = f"`{_project_id()}.{_dataset_name()}.{SITE_UPDATES_TABLE}`"
    rows = _run_query(
        f"SELECT update_id, site_kind, site_id, field, value, entered_by, entered_at, note "
        f"FROM {table} ORDER BY entered_at",
        [],
    )
    for r in rows:
        if r.get("entered_at") is not None:
            r["entered_at"] = r["entered_at"].isoformat()
    return rows


def _planner(sites: dict[str, Any]) -> dict[str, Any]:
    from .scenario import site_updates

    try:
        rows = _fetch_site_updates()
    except Exception as exc:  # noqa: BLE001
        state = site_updates.planner_inputs([], sites)
        state["status"] = "registry_only"
        state["message"] = (
            f"Planner updates could not be read ({type(exc).__name__}); registry values only."
        )
        return state
    state = site_updates.planner_inputs(rows, sites)
    state["status"] = "applied" if state["changes"] else "none"
    state["message"] = (
        f"{len(state['changes'])} planner-reported changes applied; registry values kept alongside."
        if state["changes"]
        else "No planner-reported changes."
    )
    return state


def _planner_report(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": state["status"],
        "message": state["message"],
        "changes": state["changes"],
        "incomplete_added_sites": state["incomplete_added_sites"],
        "source": SOURCES["planner"],
    }


def _band(values) -> dict[str, float]:
    import numpy as np

    p10, p50, p90 = np.quantile(values, [0.1, 0.5, 0.9], axis=0)
    return {"p10": round(float(p10), 3), "p50": round(float(p50), 3), "p90": round(float(p90), 3)}


def _people(values) -> dict[str, int]:
    return {k: round(v) for k, v in _band(values).items()}


def run_scenario(
    lat: float | None = None,
    lon: float | None = None,
    heading_deg: float | None = None,
    date: str | None = None,
    intensity_kt: float | None = None,
    category: int | None = None,
    county_fips: str | None = None,
    case: str = "base",
    sites_off: list[str] | None = None,
    assume_generator: list[str] | None = None,
    draws: int | None = None,
    run_index: int | None = None,
    seats_override: dict[str, int] | None = None,
    stations_override: dict[str, int] | None = None,
    add_sites: list[dict[str, Any]] | None = None,
    tool_context: Any = None,
) -> dict[str, Any]:
    """Model a hurricane scenario for Georgia counties: outage share ranges, power-dependent residents, oxygen, home-health and dialysis patients at risk, and, for a selected county, reachable medical shelters and dialysis centres with live drive times and evacuation delay.

    Uses the track drawn on the map (sent in CONTEXT v1) when there is one; otherwise matches past storms that passed near (lat, lon) with a similar heading, time of year and intensity. Call it whenever the user asks what a storm would do, who is at risk, or where people could go. All numbers come from this tool; report them with the range_label the tool returns.

    sites_off (shelter_id or ccn) and assume_generator (shelter_id) are operator what-ifs (assume_generator on a shelter recorded NO means adding a generator there; on UNRECORDED it means confirming one; each site's generator_assumption says which), merged with CONTEXT v1 scenario.site_overrides; the result then carries baseline, with_switches and delta for people lacking shelter and needing transport. seats_override {shelter_id: seats}, stations_override {ccn: stations} and add_sites [{lat, lon, seats, generator}] are further what-ifs; invalid values land in ignored_ids. Planner-reported site updates (record_site_update) are always applied and listed under planner_updates next to the registry values.

    draws sets how many simulated runs to make (1-2000, default 400); ranges are taken across them. run_index picks one of those runs (0-based) and reports it alone, as the storm the simulation plays. The result's report holds the same sections as county_plan for that run or set of runs.
    """
    case = case if case in CASES else "base"
    ctx = _context(tool_context)
    scenario_ctx = ctx.get("scenario")
    scenario_ctx = scenario_ctx if isinstance(scenario_ctx, dict) else {}
    lonlats = _track_lonlats(scenario_ctx)
    if len(lonlats) < 2 and (lat is None or lon is None):
        return _status(
            "needs_track_or_position",
            "Draw a track on the map, or give the storm's lat, lon, heading and date.",
        )
    try:
        month = Date.fromisoformat(date).month if date else datetime.now(UTC).month
    except (TypeError, ValueError):
        return _status("bad_date", "Give the date as YYYY-MM-DD.", date=date)

    import numpy as np

    from .scenario import data, engine, site_updates, storms
    from .scenario.receiving import receiving_sites

    switches = _switches(scenario_ctx, sites_off, assume_generator)
    if not isinstance(county_fips, str) or not county_fips:
        county_fips = ctx.get("county_fips") if isinstance(ctx.get("county_fips"), str) else None
    category = _category(category if category is not None else scenario_ctx.get("category"))

    drawn = (
        storms.drawn_track(lonlats, 3 if category is None else category)
        if len(lonlats) >= 2
        else []
    )
    if len(drawn) < 2 and (lat is None or lon is None):
        return _status(
            "needs_track_or_position",
            "The drawn track has no length. Draw a longer track, or give the storm's lat, lon, "
            "heading and date.",
        )

    match: dict[str, Any] | None = None
    if len(drawn) >= 2:
        tracks = [drawn]
        source, used = "drawn_track", []
        likelihood = storms.pattern_frequency(
            track=tracks[0], min_intensity_kt=CATEGORY_FLOOR_KT[category or 0]
        )
        origin = storms.classify_origin(lonlats[0][1], lonlats[0][0])
    else:
        analogs = storms.analog_tracks(lat, lon, heading_deg or 0.0, month, intensity_kt)
        if category is not None:
            analogs = [storms.rescale(a, category) for a in analogs]
        if not analogs:
            return _status(
                "no_matching_past_storms",
                "No storm since 1950 passed within 300 km of this point with a similar heading "
                "and time of year.",
                lat=lat,
                lon=lon,
                month=month,
            )
        tracks = [a.track for a in analogs]
        source = "matched_past_storms"
        likelihood = storms.pattern_frequency(
            lat=lat, lon=lon, heading_deg=heading_deg, month=month, min_intensity_kt=intensity_kt
        )
        used = [f"{a.name} {a.season}" for a in analogs]
        origin = storms.classify_origin(lat, lon)
        match = {
            "matched": len(analogs),
            "share_reaching_georgia_100km": round(
                sum(a.reached_ga_100km for a in analogs) / len(analogs), 2
            ),
        }

    n_runs = draws if isinstance(draws, int) and not isinstance(draws, bool) and 1 <= draws <= MAX_DRAWS else N_DRAWS
    result = engine.run(tracks, n_draws=n_runs, seed=SEED)
    one = isinstance(run_index, int) and not isinstance(run_index, bool) and 0 <= run_index < n_runs
    if one:
        result = engine.one_draw(result, run_index)
    counties = data.counties()
    risk = engine.people_at_risk(result, counties)
    outage = result.outage
    p50 = np.median(outage, axis=0)

    order = np.argsort(-np.median(risk["power_dependent"], axis=0))
    picked = list(order[:TOP_COUNTIES])
    index = {c["county_fips"]: i for i, c in enumerate(counties)}
    if county_fips in index and index[county_fips] not in picked:
        picked.append(index[county_fips])

    support_outside = any(result.outside_support)
    registry = data.sites()
    planner = _planner(registry)
    sites = site_updates.effective_sites(registry, planner)
    request = site_updates.request_overrides(seats_override, stations_override, add_sites, sites)
    what_if = site_updates.effective_sites(sites, {**request, "changes": []})
    planner_off = frozenset(planner["sites_off"])
    has_request = bool(
        request["seats_override"] or request["stations_override"] or request["add_sites"]
    )
    shelters_by_county: dict[str, list[dict[str, Any]]] = {}
    for s in sites.get("medical_shelters", []):
        shelters_by_county.setdefault(s["county_fips"], []).append(s)
    centres_by_county: dict[str, list[dict[str, Any]]] = {}
    for d in sites.get("dialysis_centers", []):
        centres_by_county.setdefault(d["county_fips"], []).append(d)

    def in_surge(site: dict[str, Any]) -> bool:
        return category is not None and category in site.get("in_surge", [])

    rows = []
    for i in picked:
        c = counties[i]
        shelters = shelters_by_county.get(c["county_fips"], [])
        centres = centres_by_county.get(c["county_fips"], [])
        rows.append(
            {
                "county_fips": c["county_fips"],
                "county_name": c["county_name"],
                "outage_share": _band(outage[:, i]),
                "peak_wind_kt": round(float(result.peak_wind_kt[i]), 1),
                "hours_ts_winds": round(float(result.hours_34kt[i]), 1),
                "ts_winds_arrive_h": None
                if np.isnan(result.ts_arrival_h[i])
                else round(float(result.ts_arrival_h[i]), 1),
                "power_dependent": {
                    "residents": c["power_dependent"],
                    "at_risk": _people(risk["power_dependent"][:, i]),
                },
                "needing_transport": {
                    "no_vehicle": _people(risk["no_vehicle"][:, i]),
                    "no_vehicle_low": _people(risk["no_vehicle_low"][:, i]),
                },
                "oxygen_users": {
                    "residents": c["oxygen"],
                    "at_risk": _people(risk["oxygen"][:, i]),
                },
                "home_health_users": {
                    "residents": c["home_health"],
                    "at_risk": _people(risk["home_health"][:, i]),
                },
                "dialysis_patients": {
                    "patients": c["dialysis_patients"],
                    "centres": len(centres),
                    "stations": sum(d.get("stations") or 0 for d in centres),
                    "centres_down": bool(p50[i] >= DIALYSIS_DOWN_SHARE),
                },
                "nursing_home_beds": c.get("nursing_home_beds", 0),
                "assisted_living_beds": c.get("assisted_living_beds", 0),
                "in_surge_zone": {
                    "shelter_ids": [s["shelter_id"] for s in shelters if in_surge(s)],
                    "dialysis_ccns": [d["ccn"] for d in centres if in_surge(d)],
                },
                "status": [
                    "modelled",
                    *(["outside_labeled_support"] if support_outside else []),
                    *(["censored_count"] if c.get("power_dependent_censored") else []),
                ],
            }
        )

    receiving = None
    if county_fips in index:
        i = index[county_fips]
        down = {counties[j]["county_fips"] for j in np.where(p50 >= DIALYSIS_DOWN_SHARE)[0]}

        def receive(
            off: frozenset[str], assumed: frozenset[str], site_set: dict[str, Any]
        ) -> dict[str, Any]:
            return receiving_sites(
                counties[i],
                site_set,
                down,
                category or None,
                origin,
                case,
                None if np.isnan(result.ts_arrival_h[i]) else float(result.ts_arrival_h[i]),
                relocation_share=RELOCATION_SHARE[case],
                power_dependent_at_risk=float(np.median(risk["power_dependent"][:, i])),
                sites_off=off | planner_off,
                assume_generator=assumed,
            )

        receiving = receive(switches["sites_off"], switches["assume_generator"], what_if)
        receiving["ignored_ids"] = [
            *receiving.get("ignored_ids", []),
            *switches["invalid"],
            *request["invalid"],
        ]
        if switches["sites_off"] or switches["assume_generator"] or has_request:
            baseline = receive(frozenset(), frozenset(), sites)
            receiving["baseline"] = {
                k: baseline[k] for k in ("lacking_shelter", "needing_transport")
            }
            receiving["delta"] = {
                block: {k: receiving[block][k] - baseline[block][k] for k in receiving[block]}
                for block in ("lacking_shelter", "needing_transport")
            }

    statewide = {
        "counties_affected": _people((outage >= AFFECTED_SHARE).sum(axis=1)),
        "counties_affected_in_most_draws": int((result.p_affected >= 0.5).sum()),
        "power_dependent_at_risk": _people(risk["power_dependent"].sum(axis=1)),
        "oxygen_users_at_risk": _people(risk["oxygen"].sum(axis=1)),
        "dialysis_patients_at_risk": _people(risk["dialysis"].sum(axis=1)),
        "facility_beds_exposed": _people(risk["facility_beds"].sum(axis=1)),
        "needing_transport_no_vehicle": _people(risk["no_vehicle"].sum(axis=1)),
        "needing_transport_no_vehicle_low": _people(risk["no_vehicle_low"].sum(axis=1)),
    }
    affected = [counties[j]["county_fips"] for j in np.where(result.p_affected >= 0.5)[0]]
    affected_set = set(affected)
    affected_shelters = [
        s["shelter_id"]
        for s in sites.get("medical_shelters", [])
        if s["county_fips"] in affected_set or in_surge(s)
    ]
    receiving_shelters = [
        r["shelter_id"] for r in (receiving or {}).get("sites", []) if r.get("shelter_id")
    ]
    out = {
        "affected_county_fips": affected,
        "affected_shelter_ids": affected_shelters,
        "receiving_top": receiving_shelters,
        "scenario": {
            "source": source,
            "origin": origin,
            "category": category,
            "month": month,
            "past_storms_used": used[:12],
            "match": match,
            "likelihood": likelihood,
            "support": "outside_labeled_support" if support_outside else "within_labeled_support",
            "range_label": RANGE_LABEL,
            "runs": {"n": n_runs, "seed": SEED, "run_index": run_index if one else None},
            "assumptions": {
                "affected_threshold_share": AFFECTED_SHARE,
                "affected_county_rule": "at least 10% outage in at least half of the draws",
                "dialysis_down_share": DIALYSIS_DOWN_SHARE,
                "share_of_power_dependent_at_risk_seeking_a_powered_seat": RELOCATION_SHARE[case],
                "no_vehicle_rate": "county share of households headed by someone 65+ with no "
                "vehicle (ACS 2023 B25045); low case uses all households",
                "sites_off": sorted(switches["sites_off"]),
                "assume_generator": sorted(switches["assume_generator"]),
                "ignored_switch_values": switches["invalid"],
                "case": case,
            },
        },
        "statewide": statewide,
        "source": SOURCES["scenario"],
        "counties": rows,
        "receiving": receiving,
        "selected_county_fips": county_fips if county_fips in index else None,
        "selected_county_name": counties[index[county_fips]]["county_name"]
        if county_fips in index else None,
        "planner_updates": _planner_report(planner),
        "ignored_ids": [*switches["invalid"], *request["invalid"]],
    }
    out["report"] = report.run_report(out)
    return out


def _season_query(sql: str, params: list[Any], key: str, source: str) -> dict[str, Any]:
    from google.api_core.exceptions import GoogleAPIError
    from google.auth.exceptions import GoogleAuthError

    try:
        rows = _run_query(sql, params)
    except (GoogleAPIError, GoogleAuthError, RuntimeError) as exc:
        detail = str(exc) if isinstance(exc, QueryTooLargeError) else type(exc).__name__
        return {
            "status": "query_too_large" if isinstance(exc, QueryTooLargeError) else "error",
            "message": f"Could not read the season table: {detail}",
            key: [],
            "source": source,
        }
    return {key: rows, "source": source}


def season_conditions(as_of_date: str | None = None) -> dict[str, Any]:
    """Current NOAA conditions and the season outlook worked out from them, with sources, dates, back-test, blend weights and the share of the season remaining. as_of_date: YYYY-MM-DD, default today."""
    from .scenario import conditions

    try:
        out = conditions.season_conditions(as_of_date)
    except ValueError as exc:
        return _status("bad_date", f"as_of_date must be YYYY-MM-DD ({exc}).")
    return {**out, "source": SOURCES["conditions"]}


def _auto_note(cond: dict[str, Any]) -> str:
    b = cond["blended"]
    sel = cond["backtest"]["selected"]
    model = (
        "No conditions predictor beat the 1950-2025 long-run rate in the leave-one-season-out "
        "back-test, so the conditions part is the long-run rate"
        if all(v == ["long_run"] for v in sel.values())
        else "Conditions model predictors: " + "; ".join(f"{k}: {', '.join(v)}"
                                                         for k, v in sel.items())
    )
    noaa = cond["inputs"]["noaa_outlook"]
    noaa_text = (
        f"blended {cond['weights']['noaa_outlook']:g} with the outside forecast input "
        f"{noaa['name']} (issued {noaa['issued']}, {noaa['url']})" if noaa
        else cond["noaa_note"].rstrip(".")
    )
    note = (
        f"{cond['plan']['reason']} {model}; {noaa_text}. "
        f"Blended: {b['storms_per_year']['value']:.2f} storms per year within 250 km of Georgia "
        f"(10-90: {b['storms_per_year']['p10']:.2f}-{b['storms_per_year']['p90']:.2f}), "
        f"{b['hurricane_share']['value']:.0%} hurricanes, {b['major_share']['value']:.0%} major."
    )
    rest = cond["rest_of_current_season"]
    if rest:
        note += (
            f" Rest of {rest['season']} after {rest['as_of_date']}: "
            f"{rest['share_of_season_remaining']:.0%} of the season remains, about "
            f"{rest['expected_storms']['value']:.2f} storms, reported separately."
        )
    return note


def _outlook_args(
    outlook: str, as_of_date: str | None
) -> tuple[str, dict, dict | None, dict | None]:
    from .scenario import conditions

    if outlook != AUTO:
        return outlook, {}, None, None
    cond = conditions.season_conditions(as_of_date)
    rest = cond["rest_of_current_season"]
    auto = {
        "note": _auto_note(cond),
        **{k: cond[k] for k in ("as_of_date", "plan", "share_of_season_remaining", "inputs",
                                "noaa_note", "conditions_model", "noaa_implied", "blended",
                                "weights", "backtest", "method")},
        "rest_of_current_season": rest and {k: v for k, v in rest.items() if k != "custom"},
    }
    run_as_of = cond["plan"]["run_as_of_date"]
    extra = {"custom": cond["custom"], **({"as_of_date": run_as_of} if run_as_of else {})}
    rest_extra = rest and {"custom": rest["custom"], "as_of_date": rest["as_of_date"]}
    return "custom", extra, auto, rest_extra


def _ranked(rows: list[dict[str, Any]], county_fips: str | None, limit: int) -> list:
    if county_fips:
        return [c for c in rows if c["county_fips"] == county_fips]
    return sorted(rows, key=lambda c: -c["lacking_shelter"]["total"]["one_in_10"])[
        : max(1, min(int(limit), 159))
    ]


def season_county_risk(
    county_fips: str | None = None,
    limit: int = 10,
    outlook: str = AUTO,
    sites_off: list[str] | None = None,
    assume_generator: list[str] | None = None,
    case: str = "base",
    seats_override: dict[str, int] | None = None,
    stations_override: dict[str, int] | None = None,
    add_sites: list[dict[str, Any]] | None = None,
    as_of_date: str | None = None,
) -> dict[str, Any]:
    """Season-long hurricane risk per Georgia county from 3,200 simulated events built on every storm since 1950 near Georgia (800 replays of the historical tracks and 2,400 synthetic variants shifted, re-intensified, re-timed and resized): chance per year of losing power to at least 25% of customers, power-dependent residents affected, people lacking shelter (no powered seat, no dialysis chair) and people needing transport (no vehicle), each in a typical, a 1-in-10 and a 1-in-100 season.

    outlook picks the storm rate: auto (default) works it out from current conditions (season_conditions): the rest of the current season after as_of_date (default today) when more than half of it remains, otherwise the next full season with the rest of the current season in auto.rest_of_current_season; long_run (1950-2025), recent (2000-2025), la_nina, neutral, el_nino (seasons with that ENSO state), or noaa_aug_2026 (scaled to NOAA's August 2026 outlook, an outside forecast input). sites_off and assume_generator rerun the season with shelters or dialysis centres switched off, or generators assumed. seats_override, stations_override and add_sites [{lat, lon, seats, generator}] are further what-ifs. Planner-reported site updates are always applied. Each result carries probability: the share of simulated seasons with anyone lacking shelter, with 50 or more, and with anyone lacking a dialysis chair. Without county_fips, returns the counties with the most people lacking shelter.
    """
    from .scenario import data, season, site_updates

    if outlook != AUTO and outlook not in season.OUTLOOKS:
        return {
            "status": "unknown_outlook",
            "message": f"Outlook must be one of: {AUTO}, {', '.join(season.OUTLOOKS)}.",
            "counties": [],
            "source": SOURCES["season"],
        }
    case = case if case in CASES else "base"
    try:
        name, extra, auto, rest_extra = _outlook_args(outlook, as_of_date)
    except ValueError as exc:
        return _status("bad_date", f"as_of_date must be YYYY-MM-DD ({exc}).")
    note = auto["note"] if auto else season_outlook_note(outlook)
    switches = _switches({}, sites_off, assume_generator)
    planner = _planner(data.sites())
    request = site_updates.request_overrides(
        seats_override,
        stations_override,
        add_sites,
        site_updates.effective_sites(data.sites(), planner),
    )
    def run_with(run_name: str, kwargs: dict) -> dict[str, Any]:
        return season.run_season(
            run_name,
            sites_off=sorted(switches["sites_off"] | set(planner["sites_off"])),
            assume_generator=sorted(switches["assume_generator"]),
            case=case,
            **site_updates.season_kwargs(planner, request),
            **kwargs,
        )

    run = run_with(name, extra)
    rows = _ranked(run["counties"], county_fips, limit)
    if auto and rest_extra:
        rest_run = run_with("custom", rest_extra)
        auto["rest_of_current_season"]["result"] = {
            "as_of": rest_run.get("as_of"),
            "statewide": rest_run["statewide"],
            "counties": _ranked(rest_run["counties"], county_fips, limit),
        }
    return {
        "outlook": outlook,
        "label": run["label"],
        "outlook_note": note,
        **({"auto": auto, "as_of": run.get("as_of"), "severity": run.get("severity")}
           if auto else {}),
        "storms_per_year": run["storms_per_year"],
        "case": case,
        "sites_off": run["sites_off"],
        "assume_generator": run["assume_generator"],
        "generator_assumptions": run["generator_assumptions"],
        "ignored_ids": [*run["ignored_ids"], *switches["invalid"], *request["invalid"]],
        "added_sites": run["added_sites"],
        "planner_updates": _planner_report(planner),
        "statewide": run["statewide"],
        "counties": rows,
        "source": SOURCES["season"],
    }


def season_outlook_note(outlook: str) -> str:
    from .scenario import data

    backtest = data.season_backtest()
    long_run = backtest["share_inside"]
    if outlook == "recent":
        return (
            f"Back-test 2018-2025: {backtest['rates_from_2000']['share_inside']:.0%} of counties "
            f"inside the range against {long_run:.0%} long-run. The 2000-2025 rates include the "
            "test years, so this is not an independent check."
        )
    if outlook in ("la_nina", "neutral", "el_nino"):
        enso = backtest["enso_conditional"]["share_inside"]
        counties = 159
        change = "a small improvement" if enso > long_run else "no improvement"
        return (
            f"Back-test 2018-2025 conditioning each year on its ENSO state: {enso:.1%} of "
            f"counties inside the range against {long_run:.1%} long-run "
            f"({round(enso * counties)} vs {round(long_run * counties)} of {counties} counties), "
            f"{change}, {'meeting' if enso >= 0.8 else 'still short of'} the 80% target."
        )
    if outlook == "noaa_aug_2026":
        return (
            "Outside forecast input: NOAA CPC August 2026 outlook, issued 6 August 2026, 7-13 "
            "named storms against a 1991-2020 average of 14; long-run rate scaled by 10/14. "
            "https://www.cpc.ncep.noaa.gov/products/outlooks/hurricane2026/August/hurricane.shtml"
        )
    return (
        f"Back-test 2018-2025: {long_run:.0%} of counties inside the range (target 80%). "
        "2018-2025 had more storms than the long-run average, so this view understates it."
    )


def gap_sensitivity() -> dict[str, Any]:
    """Unknowns in Georgia's records ranked by how much each changes the number of power-dependent and dialysis patients left without a powered seat or a chair in a 1-in-10 season, with the record to collect to resolve each one."""
    table = f"`{_project_id()}.{_dataset_name()}.scenario_fix_ranking`"
    return _season_query(f"SELECT * FROM {table} ORDER BY swing DESC", [], "gaps", SOURCES["gaps"])


def _section(source: str, build) -> dict[str, Any]:
    from google.api_core.exceptions import GoogleAPIError
    from google.auth.exceptions import GoogleAuthError

    try:
        return {**build(), "source": source}
    except QueryTooLargeError:
        raise
    except (GoogleAPIError, GoogleAuthError, RuntimeError, KeyError, ValueError) as exc:
        return {"status": NOT_DETERMINED, "reason": type(exc).__name__, "source": source}


def _geo_ids(value: Any) -> list[str]:
    if isinstance(value, dict):
        own = [value[k] for k in ("geo_id", "tract_id") if isinstance(value.get(k), str)]
        return own + [g for v in value.values() for g in _geo_ids(v)]
    if isinstance(value, list):
        return [g for v in value for g in _geo_ids(v)]
    return []


def _readiness_brief(county_fips: str) -> dict[str, Any]:
    from .readiness_brief import build_readiness_brief

    return build_readiness_brief(county_fips)


def county_plan(
    county_fips: str, outlook: str = AUTO, as_of_date: str | None = None
) -> dict[str, Any]:
    """One call that assembles a county's season readiness plan: the readiness brief (who cannot leave, where they would go, what to fix, what we could not tell), how often the power goes out under the chosen outlook and the long run, people lacking shelter and needing transport in a typical and a 1-in-10 season, what confirming every unrecorded medical-shelter generator would change, and an audit of the brief's ranked tracts against the state. Sections that cannot be filled are marked not_determined. Write the plan from these sections only, and verify the top shelters live with Google Maps.

    outlook: auto (default: worked out from current conditions; the rest of the current season after as_of_date, default today, when more than half of it remains, otherwise the next full season with the rest of the current season reported separately), long_run, recent, la_nina, neutral, el_nino or noaa_aug_2026.
    """
    from google.cloud import bigquery

    from .scenario import data, season, site_updates

    if not isinstance(county_fips, str) or not county_fips.startswith("13"):
        return _status("needs_county", "Give a Georgia county_fips, for example 13051.")
    if outlook != AUTO and outlook not in season.OUTLOOKS:
        outlook = AUTO
    county = next((c for c in data.counties() if c["county_fips"] == county_fips), None)
    if county is None:
        return _status("unknown_county", "No Georgia county has that FIPS code.")

    planner = _planner(data.sites())
    no_request = site_updates.request_overrides(None, None, None, {})
    planner_kwargs = site_updates.season_kwargs(planner, no_request)

    try:
        auto_args = _outlook_args(AUTO, as_of_date) if outlook == AUTO else None
    except ValueError as exc:
        return _status("bad_date", f"as_of_date must be YYYY-MM-DD ({exc}).")

    def run_season(name: str, assume_generator: list[str] | None = None) -> dict[str, Any]:
        run_name, extra = name, {}
        if name == AUTO and auto_args:
            run_name, extra = auto_args[0], auto_args[1]
        return season.run_season(
            run_name,
            sites_off=planner["sites_off"],
            assume_generator=assume_generator or (),
            **planner_kwargs,
            **extra,
        )

    def note(name: str) -> str:
        if name == AUTO and auto_args:
            return auto_args[2]["note"]
        return season_outlook_note(name)

    def pick(run: dict[str, Any]) -> dict[str, Any]:
        return next(c for c in run["counties"] if c["county_fips"] == county_fips)

    def brief():
        return {"brief": _readiness_brief(county_fips)}

    def outage():
        rows = {}
        for name in dict.fromkeys((outlook, "long_run")):
            run = run_season(name)
            rows[name] = {
                "label": run["label"],
                "storms_per_year": run["storms_per_year"],
                "note": note(name),
                **pick(run),
            }
        out: dict[str, Any] = {"by_outlook": rows}
        if auto_args and auto_args[3]:
            rest = season.run_season(
                "custom", sites_off=planner["sites_off"], **planner_kwargs, **auto_args[3]
            )
            out["rest_of_current_season"] = {
                "season": auto_args[2]["rest_of_current_season"]["season"],
                "as_of": rest.get("as_of"),
                "storms_per_year": rest["storms_per_year"],
                **pick(rest),
            }
        return out

    def generator_switch():
        unrecorded = [
            s["shelter_id"]
            for s in data.sites().get("medical_shelters", [])
            if s.get("generator") == "UNRECORDED"
        ]
        base = run_season(outlook)
        fixed = run_season(outlook, assume_generator=unrecorded)
        return {
            "switch": "every medical shelter without a recorded generator assumed to have one",
            "shelters_switched": len(unrecorded),
            "county_lacking_shelter": {
                "recorded_only": pick(base)["lacking_shelter"]["total"],
                "all_assumed": pick(fixed)["lacking_shelter"]["total"],
            },
            "statewide_lacking_shelter": {
                "recorded_only": base["statewide"]["lacking_shelter"]["total"],
                "all_assumed": fixed["statewide"]["lacking_shelter"]["total"],
            },
            "reading": "Shortfalls count a shelter as powered only when a generator is recorded; "
            "the truth lies between recorded_only and all_assumed.",
        }

    plan: dict[str, Any] = {
        "county_fips": county_fips,
        "county_name": county["county_name"],
        "outlook": outlook,
        **({"auto": auto_args[2]} if auto_args else {}),
        "planner_updates": _planner_report(planner),
    }
    plan["readiness_brief"] = _section("readiness brief (see its own sources)", brief)
    plan["power_outage_frequency"] = _section(SOURCES["season"], outage)
    plan["generator_switch_effect"] = _section(SOURCES["season"], generator_switch)

    def audit():
        brief = plan["readiness_brief"].get("brief") or {}
        ranked = list(dict.fromkeys(_geo_ids((brief.get("who_cannot_leave") or {}).get("tracts"))))
        if not ranked:
            raise ValueError("the brief ranked no tracts")
        rows = _run_query(
            f"""SELECT IF(geo_id IN UNNEST(@ranked), 'ranked', 'rest_of_state') AS tract_set,
                  COUNT(*) AS tracts, SUM(total_pop) AS pop,
                  ROUND(SUM(white_nh) / SUM(total_pop), 3) AS white_nh,
                  ROUND(SUM(black_nh) / SUM(total_pop), 3) AS black_nh,
                  ROUND(SUM(hispanic) / SUM(total_pop), 3) AS hispanic
                FROM `{_project_id()}.{_dataset_name()}.ext_ga_acs_race_tract`
                GROUP BY 1""",
            [bigquery.ArrayQueryParameter("ranked", "STRING", ranked)],
        )
        return {
            "question": "Did the ranked tracts land where people cannot leave, or where "
            "records happen to be filled in? Compare their make-up with the rest of the state.",
            "rows": rows,
        }

    plan["audit"] = _section(SOURCES["audit"], audit)
    plan["source"] = "Assembled from the readiness brief and the season model; each section names its source"
    storm_profile = county_storm_profile(county_fips, outlook)
    plan["scope"] = "county"
    plan["report"] = report.county_report(plan, storm_profile)
    return plan


def state_plan(outlook: str = "long_run") -> dict[str, Any]:
    """Georgia's season readiness plan in the same report shape as county_plan: the counties with the most people lacking shelter, the chance any county has a 25% outage, people lacking shelter and needing transport statewide in typical, 1-in-10 and 1-in-100 seasons, the ranked unknowns worth fixing, and the worst simulated storms. Write the plan from its report sections only.

    outlook: long_run (default), recent, la_nina, neutral, el_nino or noaa_aug_2026.
    """
    from google.api_core.exceptions import GoogleAPIError
    from google.auth.exceptions import GoogleAuthError

    from .scenario import season

    if outlook not in season.OUTLOOKS:
        outlook = "long_run"
    run = season.run_season(outlook)
    run["source"] = SOURCES["season"]
    run["outlook_note"] = season_outlook_note(outlook)
    try:
        worst = _run_query(
            f"""SELECT * FROM `{_project_id()}.{_dataset_name()}.scenario_worst_events`
                ORDER BY power_dependent_affected DESC LIMIT 10""", [])
    except (GoogleAPIError, GoogleAuthError, RuntimeError):
        worst = None
    gaps = gap_sensitivity()
    return {"scope": "state", "outlook": outlook,
            "report": report.state_report(run, worst, gaps), "source": SOURCES["season"]}


def record_site_update(
    site_kind: str,
    site_id: str,
    field: str,
    value: str,
    note: str | None = None,
    tool_context: Any = None,
) -> dict[str, Any]:
    """Record one thing a planner knows about a medical shelter or dialysis centre, so every later scenario, season and county plan uses it. site_kind is medical_shelter or dialysis; site_id is the shelter_id or ccn, or a new id for a site not in the registry (a new medical shelter needs lat, lon, seats and generator, one update each); field is generator (YES, NO, UNRECORDED), seats, stations, open (true or false), lat, lon, name or county_fips. Registry values are never overwritten; results show both."""
    from .scenario import site_updates

    clean, reason = site_updates.validate(site_kind, site_id, field, value)
    if clean is None:
        return {"status": "invalid", "message": reason, "source": SOURCES["planner"]}
    if note is not None and (not isinstance(note, str) or len(note) > 500):
        return {
            "status": "invalid",
            "message": "note: text of at most 500 characters",
            "source": SOURCES["planner"],
        }
    import uuid

    from google.api_core.exceptions import GoogleAPIError
    from google.auth.exceptions import GoogleAuthError
    from google.cloud import bigquery

    user = getattr(tool_context, "user_id", None)
    entered_by = user if isinstance(user, str) and user else "planner"
    update_id = str(uuid.uuid4())
    table = f"`{_project_id()}.{_dataset_name()}.{SITE_UPDATES_TABLE}`"
    params = [
        bigquery.ScalarQueryParameter("update_id", "STRING", update_id),
        bigquery.ScalarQueryParameter("site_kind", "STRING", site_kind),
        bigquery.ScalarQueryParameter("site_id", "STRING", site_id.strip()),
        bigquery.ScalarQueryParameter("field", "STRING", field),
        bigquery.ScalarQueryParameter("value", "STRING", clean),
        bigquery.ScalarQueryParameter("entered_by", "STRING", entered_by),
        bigquery.ScalarQueryParameter("note", "STRING", note),
    ]
    try:
        _run_query(
            f"INSERT INTO {table} (update_id, site_kind, site_id, field, value, entered_by, "
            "entered_at, note) VALUES (@update_id, @site_kind, @site_id, @field, @value, "
            "@entered_by, CURRENT_TIMESTAMP(), @note)",
            params,
        )
    except (GoogleAPIError, GoogleAuthError, RuntimeError) as exc:
        too_large = isinstance(exc, QueryTooLargeError)
        return {
            "status": "query_too_large" if too_large else "error",
            "message": str(exc)
            if too_large
            else f"Could not record the update: {type(exc).__name__}",
            "source": SOURCES["planner"],
        }
    return {
        "status": "recorded",
        "update_id": update_id,
        "site_kind": site_kind,
        "site_id": site_id.strip(),
        "field": field,
        "value": clean,
        "entered_by": entered_by,
        "source": SOURCES["planner"],
    }


def _siting_pool() -> list[dict[str, Any]] | None:
    from google.cloud import bigquery

    table = f"`{_project_id()}.{_dataset_name()}.{SITING_TABLE}`"
    try:
        rows = _run_query(
            f"SELECT candidate_id, kind, name, county_fips, shelter_id, lat, lon, seats_assumed, "
            f"lacking_shelter_1in10_reduction FROM {table} "
            "ORDER BY lacking_shelter_1in10_reduction DESC LIMIT @n",
            [bigquery.ScalarQueryParameter("n", "INT64", SITING_POOL)],
        )
    except Exception:  # noqa: BLE001
        return None
    return [{**r, "seats": r["seats_assumed"]} for r in rows]


def recommend_sites(
    outlook: str = "long_run",
    county_fips: str | None = None,
    limit: int = 5,
    lat: float | None = None,
    lon: float | None = None,
    seats: int | None = None,
) -> dict[str, Any]:
    """Where a new or upgraded medical shelter would cut people lacking shelter the most: existing medical shelters without a recorded generator upgraded to powered, large general shelters outside the surge zone converted to medical, and new sites at county population centres. Returns the top sites by modelled reduction (statewide, or for county_fips), each with p_helps (share of simulated seasons in which it helps) and expected reduction per year, plus the best combination of 3 picked one at a time. A planner-proposed site (lat, lon, seats) is evaluated too. Reductions do not add up across sites."""
    from .scenario import data, season, site_updates, siting

    if outlook not in season.OUTLOOKS:
        return {
            "status": "unknown_outlook",
            "message": f"Outlook must be one of: {', '.join(season.OUTLOOKS)}.",
            "source": SOURCES["siting"],
        }
    fips = {c["county_fips"] for c in data.counties()}
    if county_fips is not None and county_fips not in fips:
        return {
            "status": "unknown_county",
            "message": "No Georgia county has that FIPS code.",
            "source": SOURCES["siting"],
        }
    extra = []
    ignored: list[str] = []
    if lat is not None or lon is not None or seats is not None:
        proposed = siting.proposal(lat, lon, seats)
        if proposed is None:
            ignored.append(repr({"lat": lat, "lon": lon, "seats": seats}))
        else:
            extra.append(proposed)
    planner = _planner(data.sites())
    no_request = site_updates.request_overrides(None, None, None, {})
    pool = _siting_pool()
    result = siting.recommend(
        outlook,
        county_fips,
        max(1, min(int(limit), 20)),
        pool=pool,
        extra=extra,
        site_kwargs={
            "sites_off": planner["sites_off"],
            **site_updates.season_kwargs(planner, no_request),
        },
    )
    result["ignored_ids"] = [*result["ignored_ids"], *ignored]
    result["planner_updates"] = _planner_report(planner)
    result["source"] = SOURCES["siting"]
    return result


def county_storm_profile(county_fips: str, outlook: str = "long_run") -> dict[str, Any]:
    """How storms have hit one Georgia county and how the outage model treats it: every labelled storm with the observed outage against the model's held-out prediction, the county's learned outage-proneness ranked against the state, the yearly chance of 25% and 50% outages from the season engine, the strongest historical wind with its modelled outage, and whether the county is inside the model's data support.

    county_fips: a Georgia county FIPS code, for example 13275.
    outlook: long_run (default), recent, la_nina, neutral, el_nino or noaa_aug_2026.
    """
    from .scenario import profile, season

    if not isinstance(county_fips, str) or not county_fips.startswith("13"):
        return _status("needs_county", "Give a Georgia county_fips, for example 13275.")
    if outlook not in season.OUTLOOKS:
        outlook = "long_run"
    try:
        result = profile.county_storm_profile(county_fips, outlook)
    except (OSError, KeyError, ValueError, IndexError) as exc:
        return _status("error", f"Could not build the county profile: {type(exc).__name__}")
    if result["status"] != "ok":
        return _status("unknown_county", "No Georgia county has that FIPS code.")
    return {**result, "source": SOURCES["scenario"]}


def get_report(report_id: str | None = None) -> dict[str, Any]:
    """Return a precomputed report (same shape as county_plan, state_plan and run_scenario reports) by report_id, or list the available ones when report_id is empty. Use it when the planner asks for one of the prepared reports; run the live tools for anything else.
    """
    from google.api_core.exceptions import GoogleAPIError
    from google.auth.exceptions import GoogleAuthError
    from google.cloud import bigquery

    table = f"`{_project_id()}.{_dataset_name()}.scenario_reports`"
    try:
        if not report_id:
            rows = _run_query(f"SELECT report_id, scope, title, built_at FROM {table} "
                              "ORDER BY report_id", [])
            return {"reports": rows, "source": SOURCES["reports"]}
        rows = _run_query(f"SELECT * FROM {table} WHERE report_id = @id",
                          [bigquery.ScalarQueryParameter("id", "STRING", report_id)])
    except (GoogleAPIError, GoogleAuthError, RuntimeError) as exc:
        return {"status": "error", "message": type(exc).__name__, "source": SOURCES["reports"]}
    if not rows:
        return {"status": "unknown_report",
                "message": "No precomputed report has that id; call get_report() with no id "
                "to list them.", "source": SOURCES["reports"]}
    row = rows[0]
    return {"report_id": row["report_id"], "title": row["title"], "built_at": str(row["built_at"]),
            "report": json.loads(row["report_json"]), "source": SOURCES["reports"]}
