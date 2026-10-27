import json
import math
from functools import cache

import numpy as np

from . import data, engine, season, storms
from .model import N_TERMS, OutageModel
from .windfield import exposure

MIN_LABELLED_STORMS = 3
PROFILE_DRAWS = 400
PROFILE_SEED = 20261027


@cache
def _fit() -> dict:
    return json.loads((data.DATA_DIR / "county_storm_fit.json").read_text())


@cache
def _metrics() -> dict:
    return json.loads((data.DATA_DIR / "outage_model_metrics.json").read_text())


def model_label() -> str:
    m = _metrics()
    return (
        f"outage model fitted on {m['storms']} labelled storms ({m['rows']:,} county-storm rows); "
        f"held-out storms: {m['inside_10_90']:.0%} of counties inside the 10-90 range"
    )


def _fragility(county_fips: str) -> dict:
    model = OutageModel.load()
    effects = model.mean[1 + N_TERMS:]
    i = model.county_fips.index(county_fips)
    order = np.argsort(-effects)
    rank = int(np.where(order == i)[0][0]) + 1
    return {
        "effect_logit": round(float(effects[i]), 3),
        "odds_multiplier": round(math.exp(float(effects[i])), 2),
        "rank_most_fragile": rank,
        "of_counties": len(effects),
        "note": (
            "County effect on the odds of a customer losing power, after wind exposure, "
            "population and storm conditions; rank 1 is the most outage-prone county"
        ),
    }


def _yearly_chance(i: int, outlook: str) -> dict:
    ev = season.events()
    rate = season.event_rates(outlook, ev["storm_season"], ev["storm_of_event"])
    out = {}
    for key, flag in (("outage_25pct", ev["out25"][:, i]), ("outage_50pct", ev["down50"][:, i])):
        per_year = float(rate[flag].sum())
        out[key] = {
            "per_year": round(per_year, 4),
            "chance_per_season": round(1 - math.exp(-per_year), 4),
            "return_period_years": round(1 / per_year, 1) if per_year > 0 else None,
        }
    return {"outlook": outlook, "label": season.OUTLOOKS[outlook], **out}


def _worst_historical(county: dict) -> dict | None:
    lat, lon = np.array([county["lat"]]), np.array([county["lon"]])
    best = None
    for a in storms.climatology():
        e = exposure(a.track, lat, lon)
        w = float(e["peak_wind_kt"][0])
        if best is None or w > best[0]:
            best = (w, a, float(e["hours_34kt"][0]))
    if best is None:
        return None
    w, a, h34 = best
    i = [c["county_fips"] for c in data.counties()].index(county["county_fips"])
    r = engine.run([a.track], n_draws=PROFILE_DRAWS, seed=PROFILE_SEED)
    p10, p50, p90 = np.quantile(r.outage[:, i], [0.1, 0.5, 0.9])
    return {
        "storm": f"{a.name} {a.season}", "peak_wind_kt": round(w, 1),
        "hours_34kt": round(h34, 1),
        "modelled_outage": {"p10": round(float(p10), 3), "p50": round(float(p50), 3),
                            "p90": round(float(p90), 3)},
    }


def county_storm_profile(county_fips: str, outlook: str = "long_run") -> dict:
    counties = data.counties()
    county = next((c for c in counties if c["county_fips"] == county_fips), None)
    if county is None:
        return {"status": "unknown_county", "county_fips": county_fips}
    fit = _fit()
    names = fit["storms"]
    rows = sorted(fit["counties"].get(county_fips, []), key=lambda r: -r[1])
    labelled = [
        {"storm": names.get(r[0], r[0]), "observed": r[1],
         "modelled": {"p10": r[2], "p50": r[3], "p90": r[4]},
         "inside_10_90": r[2] <= r[1] <= r[4], "peak_wind_kt": r[5]}
        for r in rows
    ]
    max_wind = max((r[5] for r in rows), default=0.0)
    i = [c["county_fips"] for c in counties].index(county_fips)
    return {
        "status": "ok",
        "county_fips": county_fips,
        "county_name": county["county_name"],
        "model": model_label(),
        "labelled_storms": labelled,
        "labelled_note": (
            "Observed peak share of customers without power (EAGLE-I) against the model's "
            "prediction with that storm held out of the fit"
        ),
        "fragility": _fragility(county_fips),
        "yearly_chance": _yearly_chance(i, outlook),
        "worst_historical_wind": _worst_historical(county),
        "support": {
            "labelled_storms": len(rows),
            "max_labelled_peak_wind_kt": round(max_wind, 1),
            "inside": len(rows) >= MIN_LABELLED_STORMS,
            "rule": (
                f"inside when the county has at least {MIN_LABELLED_STORMS} labelled storms; "
                "winds above the highest labelled wind are an extrapolation"
            ),
        },
    }
