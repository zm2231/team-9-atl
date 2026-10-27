import math

from .movement import corridor_for, delay_multiplier, drive_times, haversine_km

CASES = ("low", "base", "high")
PER_KIND = 5


def _flag(value) -> str:
    if value is None:
        return "UNRECORDED"
    if isinstance(value, str):
        return value.upper() if value.upper() in ("YES", "NO") else "UNRECORDED"
    return "YES" if value else "NO"


def _usable(site: dict, down_counties: set[str], surge_category: int | None) -> bool:
    if site.get("county_fips") in down_counties:
        return False
    return surge_category is None or surge_category not in (site.get("in_surge") or [])


def _site_id(site: dict) -> str | None:
    return site.get("shelter_id") or site.get("ccn")


def _nearest(origin: tuple[float, float], rows: list[dict], down_counties: set[str],
             surge_category: int | None, sites_off: frozenset[str]) -> list[tuple[float, dict]]:
    usable = [(haversine_km(*origin, s["lat"], s["lon"]), s) for s in rows
              if _site_id(s) not in sites_off and _usable(s, down_counties, surge_category)]
    return sorted(usable, key=lambda pair: pair[0])[:PER_KIND]


def receiving_sites(county: dict, sites: dict, down_counties: set[str],
                    surge_category: int | None, origin_class: str, case: str,
                    ts_arrival_h: float | None, *, relocation_share: float,
                    power_dependent_at_risk: float,
                    sites_off: frozenset[str] = frozenset(),
                    assume_generator: frozenset[str] = frozenset()) -> dict:
    if ts_arrival_h is not None and math.isnan(ts_arrival_h):
        ts_arrival_h = None
    shelters = sites.get("medical_shelters", [])
    centres = sites.get("dialysis_centers", [])
    shelter_ids = {s["shelter_id"] for s in shelters}
    known = shelter_ids | {d["ccn"] for d in centres}
    sites_off, assume_generator = frozenset(sites_off), frozenset(assume_generator)
    ignored = sorted((sites_off - known) | (assume_generator - shelter_ids))
    origin = (county["lat"], county["lon"])
    picked = [("medical_shelter", km, s) for km, s in
              _nearest(origin, shelters, down_counties, surge_category, sites_off)]
    picked += [("dialysis_centre", km, s) for km, s in
               _nearest(origin, centres, down_counties, surge_category, sites_off)]
    times = drive_times(origin, [(s["lat"], s["lon"]) for _, _, s in picked])
    rows = []
    for (kind, km, site), trip in zip(picked, times, strict=True):
        corridor = corridor_for(county["county_fips"], (site["lat"], site["lon"]), origin)
        delay = {c: trip["minutes"] * (delay_multiplier(corridor, origin_class, c) - 1)
                 for c in CASES}
        base_h = (trip["minutes"] + delay["base"]) / 60
        row = {"kind": kind}
        if kind == "medical_shelter":
            row |= {"shelter_id": site["shelter_id"], "seats": site.get("seats")}
        else:
            row |= {"ccn": site["ccn"], "stations": site.get("stations")}
        rows.append(row | {
            "name": site.get("name"),
            "county_fips": site.get("county_fips"),
            "generator": _flag(site.get("generator")),
            "generator_assumed": _site_id(site) in assume_generator and kind == "medical_shelter",
            "generator_assumption": (
                {"UNRECORDED": "confirm_unrecorded", "NO": "add_where_recorded_no"}.get(
                    _flag(site.get("generator")))
                if _site_id(site) in assume_generator and kind == "medical_shelter" else None),
            "straight_line_km": round(km, 1),
            "drive_minutes": {"value": round(trip["minutes"]), "status": trip["status"]},
            "evacuation_delay_minutes": {c: round(v) for c, v in delay.items()},
            "corridor": corridor,
            "arrives_before_ts_winds": None if ts_arrival_h is None else base_h < ts_arrival_h,
        })
    rows.sort(key=lambda r: r["drive_minutes"]["value"])
    seeking = relocation_share * power_dependent_at_risk
    powered = [r for r in rows if r["kind"] == "medical_shelter"
               and (r["generator"] == "YES" or r["generator_assumed"])]
    reachable = sum(r["seats"] or 0 for r in powered)
    in_time = sum(r["seats"] or 0 for r in powered if r["arrives_before_ts_winds"] is not False)
    all_live = bool(rows) and all(r["drive_minutes"]["status"] == "live" for r in rows)
    return {
        "sites": rows,
        "lacking_shelter": {"seeking_powered_seat": round(seeking),
                            "powered_seats_reachable": int(reachable),
                            "no_powered_seat": max(0, round(seeking - reachable))},
        "needing_transport": {
            "cannot_arrive_in_time": max(0, round(min(seeking, reachable) - in_time))},
        "drive_time_source": "live" if all_live else "straight_line",
        "ignored_ids": ignored,
    }
