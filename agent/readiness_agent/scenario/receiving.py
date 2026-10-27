from .movement import corridor_for, delay_multiplier, drive_times, haversine_km

CASES = ("low", "base", "high")


def _flag(value: bool | None) -> str:
    return "UNRECORDED" if value is None else ("YES" if value else "NO")


def _identity(site: dict) -> dict:
    if "shelter_id" in site:
        return {"kind": "medical_shelter", "shelter_id": site["shelter_id"], "seats": site.get("seats")}
    return {"kind": "dialysis_center", "ccn": site["ccn"], "stations": site.get("stations"),
            "late_shift": _flag(site.get("late_shift"))}


def receiving_sites(county: dict, sites: list[dict], usable: list[bool], origin_class: str,
                    case: str = "base", ts_arrival_h: float | None = None,
                    top: int = 8) -> list[dict]:
    origin = (county["lat"], county["lon"])
    nearest = sorted(
        ((haversine_km(*origin, s["lat"], s["lon"]), s) for s, ok in zip(sites, usable, strict=True)
         if ok),
        key=lambda pair: pair[0],
    )[:top]
    times = drive_times(origin, [(s["lat"], s["lon"]) for _, s in nearest])
    rows = []
    for (km, site), trip in zip(nearest, times, strict=True):
        corridor = corridor_for(county["county_fips"], (site["lat"], site["lon"]), origin)
        delay = {c: trip["minutes"] * (delay_multiplier(corridor, origin_class, c) - 1)
                 for c in CASES}
        total_h = (trip["minutes"] + delay[case]) / 60
        rows.append({
            **_identity(site),
            "name": site.get("name"),
            "county_fips": site.get("county_fips"),
            "generator": _flag(site.get("generator")),
            "straight_line_km": round(km, 1),
            "drive_minutes": {"value": round(trip["minutes"]), "status": trip["status"]},
            "corridor": corridor,
            "evacuation_delay_minutes": {c: round(v) for c, v in delay.items()},
            "arrives_before_ts_winds": None if ts_arrival_h is None else total_h < ts_arrival_h,
        })
    return sorted(rows, key=lambda r: r["drive_minutes"]["value"])


def shortfall(seekers: float, rows: list[dict]) -> dict:
    powered = sum(r.get("seats") or 0 for r in rows
                  if r.get("kind") == "medical_shelter" and r["generator"] == "YES"
                  and r["arrives_before_ts_winds"] is not False)
    return {"seekers": round(seekers), "generator_recorded_seats_in_time": powered,
            "uncovered": max(0, round(seekers - powered))}
