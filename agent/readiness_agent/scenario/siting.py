import json
from typing import Any

from . import data, season

CANDIDATES_FILE = data.DATA_DIR / "siting_candidates.json"
NEW_SITE_SEATS = 100
GENERAL_MIN_CAPACITY = 500
GREEDY_PICKS = 3
LIVE_POOL = 40
SCORE_KEYS = (
    "counties_helped",
    "added_reduction_1in10",
    "p_helps",
    "expected_reduction_per_year",
)
LABEL = (
    "modelled reduction; assumes {n} powered seats for new or converted sites and the recorded "
    "seats for upgraded medical shelters; straight-line reach of {km:.0f} km ({mi:.0f} mi)"
)
NOT_ADDITIVE = (
    "Reductions do not add up across sites: two sites can serve the same people. The combination "
    "below is picked one site at a time, rerunning the season after each pick."
)


def upgrade_candidates(ev: dict) -> list[dict]:
    names = {s["shelter_id"]: s for s in data.sites().get("medical_shelters", [])}
    out = []
    for sid, seats, flag in zip(
        ev["shelter_id"], ev["shelter_seats"], ev["shelter_generator"], strict=True
    ):
        sid = str(sid)
        if flag == "YES" or sid not in names:
            continue
        site = names[sid]
        out.append(
            {
                "candidate_id": f"upgrade-{sid}",
                "kind": "upgrade",
                "shelter_id": sid,
                "name": site.get("name"),
                "county_fips": site.get("county_fips"),
                "lat": site.get("lat"),
                "lon": site.get("lon"),
                "seats": float(seats),
                "recorded_generator": str(flag),
            }
        )
    return out


def county_candidates(seats: int = NEW_SITE_SEATS) -> list[dict]:
    return [
        {
            "candidate_id": f"county-{c['county_fips']}",
            "kind": "county_centre",
            "name": f"{c['county_name']} County population centre",
            "county_fips": c["county_fips"],
            "lat": c["lat"],
            "lon": c["lon"],
            "seats": seats,
        }
        for c in data.counties()
    ]


def candidates() -> tuple[list[dict], str]:
    if CANDIDATES_FILE.exists():
        rows = json.loads(CANDIDATES_FILE.read_text())["candidates"]
        return rows, "siting_candidates.json"
    base = season.events()
    return upgrade_candidates(base) + county_candidates(), "local data only (no general shelters)"


def proposal(lat: Any, lon: Any, seats: Any) -> dict | None:
    site = season.new_site({"lat": lat, "lon": lon, "seats": seats, "generator": "YES"}, 1)
    if site is None:
        return None
    return {
        "candidate_id": "proposed",
        "kind": "proposed",
        "name": "Planner-proposed site",
        "county_fips": None,
        "lat": site["lat"],
        "lon": site["lon"],
        "seats": site["seats"],
    }


def _public(row: dict) -> dict:
    keep = (
        "candidate_id",
        "kind",
        "name",
        "county_fips",
        "shelter_id",
        "lat",
        "lon",
        "recorded_generator",
    )
    out = {k: row[k] for k in keep if row.get(k) is not None}
    out["seats_assumed"] = round(float(row["seats"]))
    for k, v in row.items():
        if k.startswith("lacking_shelter_") or k in SCORE_KEYS:
            out[k] = v
    return out


def recommend(
    outlook: str = "long_run",
    county_fips: str | None = None,
    limit: int = 5,
    pool: list[dict] | None = None,
    extra: list[dict] | None = None,
    site_kwargs: dict | None = None,
) -> dict[str, Any]:
    site_kwargs = site_kwargs or {}
    base = season.siting_base(outlook, **site_kwargs)
    ev = base["ev"]
    county = None
    if county_fips is not None:
        fips = [str(f) for f in ev["county_fips"]]
        county = fips.index(county_fips)
    rows, source = (pool, "scenario_siting") if pool is not None else candidates()
    if county is not None:
        rows = [
            r
            for r in rows
            if r["kind"] == "upgrade" or season.reach_of(float(r["lat"]), float(r["lon"]))[county]
        ]
    rows = sorted(rows, key=lambda r: -float(r.get("lacking_shelter_1in10_reduction") or 0))
    rows = rows[:LIVE_POOL] + list(extra or [])
    scored = season.evaluate_candidates(base, rows, county)
    combo = season.greedy(
        base, scored[: max(LIVE_POOL // 2, len(extra or []))], GREEDY_PICKS, county
    )
    return {
        "outlook": outlook,
        "county_fips": county_fips,
        "scope": "county" if county is not None else "statewide",
        "label": LABEL.format(n=NEW_SITE_SEATS, km=season.RECEIVE_KM, mi=season.RECEIVE_KM * 0.621371),
        "note": NOT_ADDITIVE,
        "candidates_from": source,
        "lacking_shelter_1in10_now": round(
            float(
                base["before"]["state_1in10"]
                if county is None
                else base["before"]["county_1in10"][county]
            )
        ),
        "probability_label": f"p_helps: {season.PROBABILITY_LABEL} in which the site cuts people "
        "lacking shelter by at least 1, same seasons before and after",
        "top": [_public(r) for r in scored[:limit]],
        "proposed": [_public(r) for r in scored if r["kind"] == "proposed"],
        "best_combination_of_3": [_public(r) for r in combo],
        "ignored_ids": base["meta"]["ignored_ids"],
    }
