import copy
import math
import re
from typing import Any

from . import season

SITE_KINDS = ("medical_shelter", "dialysis")
FIELDS = ("generator", "seats", "stations", "open", "lat", "lon", "name", "county_fips")
KIND_FIELDS = {
    "medical_shelter": {"generator", "seats", "open", "lat", "lon", "name", "county_fips"},
    "dialysis": {"stations", "open", "lat", "lon", "name", "county_fips"},
}
REQUIRED_NEW = {
    "medical_shelter": ("lat", "lon", "seats", "generator"),
    "dialysis": ("lat", "lon", "stations"),
}
MAX_TEXT = 200
FIPS = re.compile(r"^13\d{3}$")


def _float(value: str, bounds: tuple[float, float]) -> str | None:
    try:
        x = float(value)
    except ValueError:
        return None
    return repr(x) if math.isfinite(x) and bounds[0] <= x <= bounds[1] else None


def validate(site_kind: Any, site_id: Any, field: Any, value: Any) -> tuple[str | None, str]:
    if site_kind not in SITE_KINDS:
        return None, f"site_kind must be one of {', '.join(SITE_KINDS)}"
    if not isinstance(site_id, str) or not site_id.strip() or len(site_id) > 64:
        return None, "site_id must be a non-empty string of at most 64 characters"
    if field not in FIELDS:
        return None, f"field must be one of {', '.join(FIELDS)}"
    if field not in KIND_FIELDS[site_kind]:
        return None, f"field {field} does not apply to a {site_kind}"
    if isinstance(value, bool):
        value = "true" if value else "false"
    if not isinstance(value, str | int | float):
        return None, "value must be a string or a number"
    text = str(value).strip()
    if field == "generator":
        flag = text.upper()
        return (
            (flag, "")
            if flag in season.GENERATOR_FLAGS
            else (None, "generator: YES, NO or UNRECORDED")
        )
    if field in ("seats", "stations"):
        n = season._count(text)
        return (str(n), "") if n is not None else (None, f"{field}: a whole number 0-100000")
    if field == "open":
        flag = text.lower()
        if flag in ("true", "yes", "open"):
            return "true", ""
        if flag in ("false", "no", "closed"):
            return "false", ""
        return None, "open: true or false"
    if field in ("lat", "lon"):
        bounds = season.GA_LAT if field == "lat" else season.GA_LON
        out = _float(text, bounds)
        return (out, "") if out else (None, f"{field}: a number inside Georgia {bounds}")
    if field == "county_fips":
        return (text, "") if FIPS.match(text) else (None, "county_fips: a Georgia FIPS like 13051")
    if not text or len(text) > MAX_TEXT:
        return None, f"name: 1-{MAX_TEXT} characters"
    return text, ""


def latest(rows: list[dict]) -> dict[tuple[str, str], dict[str, dict]]:
    out: dict[tuple[str, str], dict[str, dict]] = {}
    ordered = sorted(rows, key=lambda r: (str(r.get("entered_at") or ""), str(r.get("update_id"))))
    for r in ordered:
        value, _ = validate(r.get("site_kind"), r.get("site_id"), r.get("field"), r.get("value"))
        if value is None:
            continue
        out.setdefault((r["site_kind"], r["site_id"]), {})[r["field"]] = {**r, "value": value}
    return out


def label(row: dict) -> str:
    when = str(row.get("entered_at") or "")[:10] or "undated"
    return f"planner-reported ({row.get('entered_by') or 'planner'}, {when})"


def _nearest_county(lat: float, lon: float) -> str:
    clat, clon = season.county_centres()
    i = int(season._distance_km(clat, clon, lat, lon).argmin())
    return str(season.events()["county_fips"][i])


def planner_inputs(rows: list[dict], sites: dict) -> dict[str, Any]:
    by_id = {
        "medical_shelter": {s["shelter_id"]: s for s in sites.get("medical_shelters", [])},
        "dialysis": {d["ccn"]: d for d in sites.get("dialysis_centers", [])},
    }
    out: dict[str, Any] = {
        "generator_override": {},
        "seats_override": {},
        "stations_override": {},
        "location_override": {},
        "sites_off": [],
        "add_sites": [],
        "changes": [],
        "incomplete_added_sites": [],
    }
    for (kind, site_id), fields in sorted(latest(rows).items()):
        registry = by_id[kind].get(site_id)
        if registry is None:
            missing = [f for f in REQUIRED_NEW[kind] if f not in fields]
            if missing:
                out["incomplete_added_sites"].append(
                    {"site_kind": kind, "site_id": site_id, "missing": missing}
                )
                continue
            site = {"site_kind": kind, "id": site_id, **{f: fields[f]["value"] for f in fields}}
            out["add_sites"].append(site)
            out["changes"].append(
                {
                    "site_kind": kind,
                    "site_id": site_id,
                    "field": "added_site",
                    "registry": None,
                    "planner": {f: fields[f]["value"] for f in fields},
                    "label": label(max(fields.values(), key=lambda r: str(r.get("entered_at")))),
                    "surge": season.ADDED_SURGE_NOTE,
                }
            )
            continue
        for field, row in fields.items():
            value = row["value"]
            reg_value = registry.get(field)
            if field == "generator":
                out["generator_override"][site_id] = value
            elif field == "seats":
                out["seats_override"][site_id] = int(value)
            elif field == "stations":
                out["stations_override"][site_id] = int(value)
            elif field == "open":
                reg_value = True
                if value == "false":
                    out["sites_off"].append(site_id)
            elif field in ("lat", "lon"):
                out["location_override"].setdefault(site_id, {})[field] = float(value)
            out["changes"].append(
                {
                    "site_kind": kind,
                    "site_id": site_id,
                    "field": field,
                    "registry": reg_value,
                    "planner": value,
                    "label": label(row),
                }
            )
    return out


def effective_sites(sites: dict, planner: dict) -> dict:
    out = copy.deepcopy(sites)
    shelters = {s["shelter_id"]: s for s in out.get("medical_shelters", [])}
    centres = {d["ccn"]: d for d in out.get("dialysis_centers", [])}
    by_id = {**centres, **shelters}
    labels = {(c["site_id"], c["field"]): c["label"] for c in planner.get("changes", [])}
    for sid, flag in planner.get("generator_override", {}).items():
        if sid in shelters:
            shelters[sid]["generator"] = flag
    for sid, n in planner.get("seats_override", {}).items():
        if sid in shelters:
            shelters[sid]["seats"] = n
    for sid, n in planner.get("stations_override", {}).items():
        if sid in centres:
            centres[sid]["stations"] = n
    for sid, loc in planner.get("location_override", {}).items():
        if sid in by_id:
            by_id[sid].update(loc)
    for (sid, field), text in labels.items():
        if sid in by_id and field != "added_site":
            by_id[sid].setdefault("planner_reported", {})[field] = text
    for a in planner.get("add_sites", []):
        lat, lon = float(a["lat"]), float(a["lon"])
        base = {
            "name": a.get("name") or a["id"],
            "lat": lat,
            "lon": lon,
            "county_fips": a.get("county_fips") or _nearest_county(lat, lon),
            "in_surge": [],
            "surge": season.ADDED_SURGE_NOTE,
            "planner_added": True,
        }
        if a.get("site_kind", "medical_shelter") == "medical_shelter":
            out.setdefault("medical_shelters", []).append(
                {
                    **base,
                    "shelter_id": a["id"],
                    "seats": int(a["seats"]),
                    "generator": a["generator"],
                }
            )
        else:
            out.setdefault("dialysis_centers", []).append(
                {**base, "ccn": a["id"], "stations": int(a["stations"]), "late_shift": "UNRECORDED"}
            )
    return out


def request_overrides(
    seats_override: Any, stations_override: Any, add_sites: Any, sites: dict
) -> dict[str, Any]:
    shelters = {s["shelter_id"] for s in sites.get("medical_shelters", [])}
    centres = {d["ccn"] for d in sites.get("dialysis_centers", [])}
    out: dict[str, Any] = {
        "seats_override": {},
        "stations_override": {},
        "add_sites": [],
        "invalid": [],
    }
    for key, mapping, ids in (
        ("seats_override", seats_override, shelters),
        ("stations_override", stations_override, centres),
    ):
        if mapping is None:
            continue
        if not isinstance(mapping, dict):
            out["invalid"].append(repr(mapping))
            continue
        for sid, raw in mapping.items():
            n = season._count(raw)
            if not isinstance(sid, str) or sid not in ids or n is None:
                out["invalid"].append(f"{sid}={raw!r}")
                continue
            out[key][sid] = n
    if add_sites is not None and not isinstance(add_sites, list):
        out["invalid"].append(repr(add_sites))
        add_sites = []
    for i, raw in enumerate(add_sites or []):
        site = season.new_site(raw, i + 1)
        if site is None:
            out["invalid"].append(repr(raw))
            continue
        out["add_sites"].append({**site, "id": f"request-{site['id']}"})
    return out


def season_kwargs(planner: dict, request: dict) -> dict[str, Any]:
    return {
        "generator_override": planner.get("generator_override") or None,
        "seats_override": {**planner.get("seats_override", {}), **request["seats_override"]},
        "stations_override": {
            **planner.get("stations_override", {}),
            **request["stations_override"],
        },
        "location_override": planner.get("location_override") or None,
        "add_sites": [*planner.get("add_sites", []), *request["add_sites"]],
    }
