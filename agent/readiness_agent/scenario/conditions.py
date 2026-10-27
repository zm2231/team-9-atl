import datetime as dt
import html
import json
import math
import re
import urllib.request
from functools import cache
from zoneinfo import ZoneInfo

import numpy as np

from . import season
from .data import DATA_DIR

TIMEOUT_S = 8
Z90 = 1.2815515655446004
NOAA_WEIGHT = 0.5
PLAN_CURRENT_ABOVE = 0.5
ONI_URL = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"
TNA_URL = "https://psl.noaa.gov/data/correlation/tna.data"
ENSO_URL = "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/ensodisc.shtml"
OUTLOOKS = {
    2026: {
        "url": season.NOAA_URL,
        "issued": "2026-08-06",
        "name": "NOAA CPC August 2026 Atlantic hurricane outlook",
        "named": (7, 13),
        "hurricanes": (2, 6),
        "major": (0, 2),
        "average": (14, 7, 3),
        "range_probability": 0.7,
    },
}
FALLBACK_ONI = {"value": 2.16, "season": "JAS 2026", "source": "data/oni.txt (NOAA CPC ONI)"}

_cache: dict[tuple[str, dt.date], dict] = {}


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "team-9-atl readiness agent"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as response:
        return response.read().decode("utf-8", "replace")


def _text(page: str) -> str:
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", page)))


def _daily(key: str, fetch, fallback, today: dt.date) -> dict:
    hit = _cache.get((key, today))
    if hit is not None:
        return hit
    try:
        value = fetch()
    except Exception as exc:  # noqa: BLE001
        value = {"status": "fallback", **fallback(), "fetch_error": type(exc).__name__}
    _cache[(key, today)] = value
    return value


def _oni() -> dict:
    rows = [line.split() for line in _get(ONI_URL).splitlines()[1:]]
    seas, year, _, anom = [r for r in rows if len(r) == 4][-1]
    return {"value": float(anom), "season": f"{seas} {year}", "source": "NOAA CPC ONI",
            "url": ONI_URL, "status": "live"}


def _oni_fallback() -> dict:
    rows = [ln.split() for ln in (DATA_DIR / "oni.txt").read_text().splitlines()[1:]]
    seas, year, _, anom = [r for r in rows if len(r) == 4][-1]
    return {"value": float(anom), "season": f"{seas} {year}", "source": FALLBACK_ONI["source"]}


def _tna() -> dict:
    latest = None
    for line in _get(TNA_URL).splitlines()[1:]:
        parts = line.split()
        if len(parts) != 13 or not parts[0].isdigit():
            continue
        for month, value in enumerate(parts[1:], start=1):
            if float(value) > -99:
                latest = (int(parts[0]), month, float(value))
    if latest is None:
        raise ValueError("no TNA values")
    year, month, value = latest
    return {"value": value, "month": f"{year}-{month:02d}", "url": TNA_URL, "status": "live",
            "source": "NOAA PSL Tropical North Atlantic SST anomaly (MDR proxy)"}


def _tna_fallback() -> dict:
    return {"value": None, "month": None, "source": "NOAA PSL TNA (unavailable)"}


def _enso_forecast() -> dict:
    text = _text(_get(ENSO_URL))
    status = re.search(r"ENSO Alert System Status:\s*(.+?)(?:Synopsis|$)", text)
    synopsis = re.search(r"Synopsis:\s*(.+?\.)(?:\s|$)", text)
    if not synopsis:
        raise ValueError("no synopsis")
    issued = re.search(r"issued by\s+CLIMATE PREDICTION CENTER.*?(\d{1,2} \w+ \d{4})", text)
    return {"status_line": status.group(1).strip() if status else None,
            "synopsis": synopsis.group(1).strip(), "issued": issued.group(1) if issued else None,
            "source": "NOAA CPC ENSO Diagnostic Discussion", "url": ENSO_URL, "status": "live"}


def _enso_fallback() -> dict:
    return {"synopsis": None, "source": "NOAA CPC ENSO Diagnostic Discussion (unavailable)",
            "url": ENSO_URL}


def _noaa_outlook(year: int) -> dict | None:
    cfg = OUTLOOKS.get(year)
    if cfg is None:
        return None

    def scrape() -> dict:
        text = _text(_get(cfg["url"]))
        found = {}
        for key, label in (("named", "Named Storms"), ("hurricanes", "Hurricanes"),
                           ("major", "Major Hurricanes")):
            m = re.search(rf"(\d+)\s*-\s*(\d+)\s+{label}", text)
            if not m:
                raise ValueError(f"no {key} range")
            found[key] = (int(m.group(1)), int(m.group(2)))
        return {**cfg, **found, "status": "live"}

    return _daily(f"noaa{year}", scrape, lambda: {**cfg, "status": "configured"}, _today())


def _today() -> dt.date:
    return dt.datetime.now(ZoneInfo("America/New_York")).date()


@cache
def model() -> dict:
    return json.loads((DATA_DIR / "season_conditions.json").read_text())


def _model_part(part: str, current: dict[str, float | None]) -> dict:
    m = model()
    names = m["selected"][part]
    if names == ["long_run"]:
        names = []
    if any(current.get(n) is None for n in names):
        names = []
    row = next(r for r in m["models"] if r["predictors"] == (names or ["long_run"]))
    key = {"storms": "count", "hurricane_share": "hurricane_share",
           "major_share": "major_share"}[part]
    beta, cov = np.array(row[key]["coef"]), np.array(row[key]["cov"])
    stats = m["predictors"]
    x = np.array([1.0] + [(current[n] - stats[n]["mean"]) / stats[n]["sd"] for n in names])
    eta, se = float(x @ beta), float(math.sqrt(x @ cov @ x))
    link = math.exp if part == "storms" else (lambda v: 1 / (1 + math.exp(-v)))
    return {"value": link(eta), "p10": link(eta - Z90 * se), "p90": link(eta + Z90 * se),
            "predictors": names or ["long_run"]}


def conditions_model(current: dict[str, float | None]) -> dict:
    storms = _model_part("storms", current)
    hurr = _model_part("hurricane_share", current)
    major_given = _model_part("major_share", current)
    major = {k: hurr[k] * major_given[k] for k in ("value", "p10", "p90")}
    return {"storms_per_year": storms, "hurricane_share": hurr,
            "major_share": {**major, "predictors": major_given["predictors"]}}


def noaa_implied(outlook: dict) -> dict:
    m = model()
    avg_named, avg_hurr, avg_major = outlook["average"]

    def mid(r):
        return (r[0] + r[1]) / 2

    named = outlook["named"]
    storms = {k: m["storms_per_year"] * v / avg_named
              for k, v in (("value", mid(named)), ("p10", named[0]), ("p90", named[1]))}

    def share(key, avg, base):
        r = outlook[key]
        out = {k: min(1.0, base * (v / max(mid(named), 1)) / (avg / avg_named))
               for k, v in (("value", mid(r)), ("p10", r[0]), ("p90", r[1]))}
        return out

    return {"storms_per_year": storms,
            "hurricane_share": share("hurricanes", avg_hurr, m["hurricane_share"]),
            "major_share": share("major", avg_major, m["major_share"])}


def blend(model_part: dict, noaa_part: dict | None, weight: float = NOAA_WEIGHT) -> dict:
    if noaa_part is None:
        return {k: model_part[k] for k in ("value", "p10", "p90")}
    return {k: (1 - weight) * model_part[k] + weight * noaa_part[k]
            for k in ("value", "p10", "p90")}


def _rounded(d: dict, digits: int) -> dict:
    return {k: round(v, digits) if isinstance(v, float) else v for k, v in d.items()}


def _season_outlook(year: int, as_of: dt.date, model_out: dict, m: dict) -> dict:
    outlook = _noaa_outlook(year)
    if outlook is not None and dt.date.fromisoformat(outlook["issued"]) > as_of:
        outlook = None
    noaa = noaa_implied(outlook) if outlook else None
    weight = NOAA_WEIGHT if noaa else 0.0
    blended = {k: blend(model_out[k], noaa[k] if noaa else None, weight) for k in model_out}
    return {
        "season": year,
        "noaa_outlook": outlook and {k: outlook[k] for k in (
            "name", "issued", "url", "named", "hurricanes", "major", "average",
            "range_probability", "status")},
        "noaa_note": None if outlook else (
            f"No NOAA seasonal hurricane outlook for {year} is available as of {as_of}."),
        "noaa_implied": noaa and {k: _rounded(v, 3) for k, v in noaa.items()},
        "blended": {k: _rounded(v, 3) for k, v in blended.items()},
        "weights": {"conditions_model": round(1 - weight, 2), "noaa_outlook": weight},
        "custom": {
            "storms_per_year": blended["storms_per_year"]["value"],
            "hurricane_share": blended["hurricane_share"]["value"],
            "major_share": min(blended["major_share"]["value"],
                               blended["hurricane_share"]["value"]),
            "source": _source_line(year, outlook, weight, m),
        },
    }


def _storms(blended: dict, share: float) -> dict:
    return {k: round(v * share, 2) for k, v in blended["storms_per_year"].items()
            if k in ("value", "p10", "p90")}


def season_conditions(as_of_date: dt.date | str | None = None) -> dict:
    as_of = dt.date.fromisoformat(as_of_date) if isinstance(as_of_date, str) else (
        as_of_date or _today())
    today = _today()
    oni = _daily("oni", _oni, _oni_fallback, today)
    tna = _daily("tna", _tna, _tna_fallback, today)
    enso = _daily("enso", _enso_forecast, _enso_fallback, today)
    m = model()
    model_out = conditions_model({"oni": oni["value"], "tna": tna["value"]})
    remaining = season.season_remaining_share(as_of)
    current = _season_outlook(as_of.year, as_of, model_out, m)
    day = f"{as_of.day} {as_of:%b}"
    if remaining > PLAN_CURRENT_ABOVE:
        planned, rest = current, None
        plan = {
            "season": as_of.year, "trimmed_to_as_of": True, "run_as_of_date": as_of.isoformat(),
            "reason": (f"Planning the rest of the {as_of.year} season: {remaining:.0%} of its "
                       f"storms historically arrive after {day}."),
            "expected_storms": _storms(current["blended"], remaining),
        }
    else:
        planned = _season_outlook(as_of.year + 1, as_of, model_out, m)
        plan = {
            "season": as_of.year + 1, "trimmed_to_as_of": False, "run_as_of_date": None,
            "reason": (f"Planning the {as_of.year + 1} season: {1 - remaining:.0%} of "
                       f"{as_of.year}'s storms historically arrive before {day}."),
            "expected_storms": _storms(planned["blended"], 1.0),
        }
        rest = {
            "season": as_of.year,
            "as_of_date": as_of.isoformat(),
            "share_of_season_remaining": round(remaining, 3),
            "expected_storms": _storms(current["blended"], remaining),
            **{k: current[k] for k in ("noaa_outlook", "noaa_note", "blended", "weights",
                                       "custom")},
        }
    base = next(r for r in m["models"] if r["predictors"] == ["long_run"])
    backtest = [
        {"predictors": r["predictors"],
         "loso_log_score_storms": r["loso_log_score"][m["count_family"]],
         "beats_long_run": r["loso_log_score"][m["count_family"]]
         > base["loso_log_score"][m["count_family"]],
         "county_coverage_2018_2025": r["county_coverage_2018_2025"]}
        for r in m["models"]
    ]
    return {
        "as_of_date": as_of.isoformat(),
        "plan": plan,
        "share_of_season_remaining": round(remaining, 3),
        "inputs": {"oni": oni, "mdr_sst_anomaly": tna, "enso_forecast": enso,
                   "noaa_outlook": planned["noaa_outlook"]},
        "noaa_note": planned["noaa_note"],
        "conditions_model": {k: _rounded(v, 3) for k, v in model_out.items()},
        "noaa_implied": planned["noaa_implied"],
        "blended": planned["blended"],
        "weights": planned["weights"],
        "custom": planned["custom"],
        "rest_of_current_season": rest,
        "backtest": {
            "count_family": m["count_family"],
            "models": backtest,
            "long_run_county_coverage_2018_2025": m["long_run_county_coverage_2018_2025"],
            "oni_only_per_unit": m["oni_only_per_unit"],
            "selected": m["selected"],
        },
        "method": (
            "Storms per year are counted within 250 km (155 mi) of Georgia; shares are of those storms. "
            "The conditions model uses a predictor only where its leave-one-season-out back-test "
            "beat the long-run rate; otherwise that part is the 1950-2025 long-run value. NOAA's "
            "basin counts are converted to Georgia by their ratio to the 1991-2020 average and "
            "blended with the conditions model at the stated weights, only when NOAA has issued "
            "an outlook for the planned season. Ranges are 10th-90th percentiles of the model's "
            "parameter uncertainty; NOAA's are its 70% ranges. When more than half of the current "
            "season remains, the plan keeps only its storms after as_of_date; otherwise it plans "
            "the next full season and reports the rest of the current season separately."
        ),
    }


def _source_line(year: int, outlook: dict | None, weight: float, m: dict) -> str:
    parts = []
    sel = m["selected"]
    if all(v == ["long_run"] for v in sel.values()):
        parts.append("conditions model: no predictor beat the 1950-2025 long-run rate out of "
                     "sample, so it is the long-run rate")
    else:
        parts.append("conditions model: " + "; ".join(
            f"{k} from {', '.join(v)}" for k, v in sel.items()))
    if outlook:
        parts.append(f"outside forecast input: {outlook['name']}, issued {outlook['issued']}, "
                     f"{outlook['url']}, weight {weight:g}")
    return f"Auto outlook for the {year} season (" + "; ".join(parts) + ")"
