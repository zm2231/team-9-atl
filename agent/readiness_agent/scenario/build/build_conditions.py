import itertools
import json
import math
import urllib.request

import numpy as np

from readiness_agent.scenario import season
from readiness_agent.scenario.data import DATA_DIR

OUT = DATA_DIR / "season_conditions.json"
YEARS = list(range(season.YEARS[0], season.YEARS[1] + 1))
WINDOW = (2018, 2025)
ASO = (8, 9, 10)
PSL = {
    "tna": (
        "https://psl.noaa.gov/data/correlation/tna.data",
        (
            "NOAA PSL Tropical North Atlantic index (SST anomaly 5.5-23.5N, 15-57.5W, HadISST, "
            "1991-2020 base), used as the Atlantic Main Development Region SST anomaly"
        ),
    ),
}
ONI_SOURCE = "NOAA CPC Oceanic Nino Index, Aug-Oct season (data/oni.txt)"
PREDICTORS = ("oni", "tna")


def psl_monthly(url: str) -> dict[tuple[int, int], float]:
    text = urllib.request.urlopen(url, timeout=30).read().decode()
    out = {}
    for line in text.splitlines()[1:]:
        parts = line.split()
        if len(parts) != 13 or not parts[0].isdigit():
            continue
        for month, value in enumerate(parts[1:], start=1):
            v = float(value)
            if v > -99:
                out[(int(parts[0]), month)] = v
    return out


def aso_mean(monthly: dict[tuple[int, int], float], year: int) -> float:
    return float(np.mean([monthly[(year, m)] for m in ASO]))


def fit_poisson(x: np.ndarray, y: np.ndarray, iters: int = 50) -> tuple[np.ndarray, np.ndarray]:
    beta = np.zeros(x.shape[1])
    beta[0] = math.log(max(y.mean(), 1e-6))
    for _ in range(iters):
        mu = np.exp(x @ beta)
        info = x.T @ (x * mu[:, None])
        step = np.linalg.solve(info, x.T @ (y - mu))
        beta += step
        if np.abs(step).max() < 1e-10:
            break
    mu = np.exp(x @ beta)
    return beta, np.linalg.inv(x.T @ (x * mu[:, None]))


def fit_binomial(x: np.ndarray, k: np.ndarray, n: np.ndarray, iters: int = 50):
    beta = np.zeros(x.shape[1])
    p0 = k.sum() / n.sum()
    beta[0] = math.log(p0 / (1 - p0))
    for _ in range(iters):
        p = 1 / (1 + np.exp(-(x @ beta)))
        w = n * p * (1 - p)
        info = x.T @ (x * w[:, None])
        step = np.linalg.solve(info, x.T @ (k - n * p))
        beta += step
        if np.abs(step).max() < 1e-10:
            break
    p = 1 / (1 + np.exp(-(x @ beta)))
    return beta, np.linalg.inv(x.T @ (x * (n * p * (1 - p))[:, None]))


def nb_size(y: np.ndarray, mu: np.ndarray) -> float:
    excess = float(np.mean((y - mu) ** 2 - mu))
    return math.inf if excess <= 0 else float(np.mean(mu**2) / excess)


def poisson_logpmf(k: float, mu: float) -> float:
    return k * math.log(mu) - mu - math.lgamma(k + 1)


def nb_logpmf(k: float, mu: float, size: float) -> float:
    if math.isinf(size):
        return poisson_logpmf(k, mu)
    return (math.lgamma(k + size) - math.lgamma(size) - math.lgamma(k + 1)
            + size * math.log(size / (size + mu)) + k * math.log(mu / (size + mu)))


def binom_logpmf(k: float, n: float, p: float) -> float:
    if n == 0:
        return 0.0
    return (math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
            + k * math.log(p) + (n - k) * math.log(1 - p))


def poisson_quantile(mu: float, q: float) -> int:
    k, cdf = 0, math.exp(-mu)
    while cdf < q:
        k += 1
        cdf += math.exp(poisson_logpmf(k, mu))
    return k


def design(z: dict[str, np.ndarray], names: tuple[str, ...], rows) -> np.ndarray:
    return np.column_stack([np.ones(len(rows))] + [z[n][rows] for n in names])


def standardize(raw: dict[str, np.ndarray], rows=None) -> tuple[dict, dict]:
    pick = slice(None) if rows is None else rows
    stats = {n: (float(v[pick].mean()), float(v[pick].std())) for n, v in raw.items()}
    return {n: (v - stats[n][0]) / stats[n][1] for n, v in raw.items()}, stats


def loso(raw, names, storms, hurr, major) -> dict:
    n = len(storms)
    count_lp = {"poisson": 0.0, "negbin": 0.0}
    share_lp = {"hurricane": 0.0, "major": 0.0}
    mult = np.zeros(n)
    for t in range(n):
        train = np.array([i for i in range(n) if i != t])
        z, _ = standardize(raw, train)
        xt, x1 = design(z, names, train), design(z, names, [t])[0]
        beta, _ = fit_poisson(xt, storms[train])
        mu = float(math.exp(x1 @ beta))
        size = nb_size(storms[train], np.exp(xt @ beta))
        count_lp["poisson"] += poisson_logpmf(storms[t], mu)
        count_lp["negbin"] += nb_logpmf(storms[t], mu, size)
        mult[t] = mu / float(storms[train].mean())
        for key, k, total in (("hurricane", hurr, storms), ("major", major, hurr)):
            keep = total[train] > 0
            bb, _ = fit_binomial(xt[keep], k[train][keep], total[train][keep])
            p = 1 / (1 + math.exp(-(x1 @ bb)))
            share_lp[key] += binom_logpmf(k[t], total[t], p)
    return {"count": count_lp, "share": share_lp, "multiplier": mult}


def county_coverage(rows: list[dict], mult_window: np.ndarray) -> float:
    years = WINDOW[1] - WINDOW[0] + 1
    scale = float(mult_window.sum()) / years
    inside = 0
    for r in rows:
        mu = max(r["expected"] * scale, 1e-9)
        lo, hi = poisson_quantile(mu, 0.1), poisson_quantile(mu, 0.9)
        inside += lo <= r["observed"] <= hi
    return inside / len(rows)


def main() -> None:
    ev = season.events()
    seasons = ev["storm_season"]
    peak = np.full(len(seasons), -1)
    np.maximum.at(peak, ev["storm_of_event"], ev["category"])
    idx = {y: i for i, y in enumerate(YEARS)}
    storms = np.zeros(len(YEARS))
    hurr = np.zeros(len(YEARS))
    major = np.zeros(len(YEARS))
    for s, c in zip(seasons, peak, strict=True):
        storms[idx[int(s)]] += 1
        hurr[idx[int(s)]] += c >= 1
        major[idx[int(s)]] += c >= 3

    oni = season.aso_oni()
    monthly = {k: psl_monthly(url) for k, (url, _) in PSL.items()}
    raw = {
        "oni": np.array([oni[y] for y in YEARS]),
        "tna": np.array([aso_mean(monthly["tna"], y) for y in YEARS]),
    }
    z, stats = standardize(raw)
    backtest = json.loads((DATA_DIR / "season_backtest.json").read_text())
    window = np.array([idx[y] for y in range(WINDOW[0], WINDOW[1] + 1)])

    models = [()] + [c for r in (1, 2) for c in itertools.combinations(PREDICTORS, r)]
    table = []
    for names in models:
        res = loso(raw, names, storms, hurr, major)
        cover = county_coverage(backtest["rows"], res["multiplier"][window])
        x = design(z, names, list(range(len(YEARS))))
        beta, cov = fit_poisson(x, storms)
        hb, hcov = fit_binomial(x, hurr, storms)
        keep = hurr > 0
        mb, mcov = fit_binomial(x[keep], major[keep], hurr[keep])
        table.append({
            "predictors": list(names) or ["long_run"],
            "loso_log_score": {k: round(v, 3) for k, v in res["count"].items()},
            "loso_share_log_score": {k: round(v, 3) for k, v in res["share"].items()},
            "county_coverage_2018_2025": round(cover, 4),
            "count": {"coef": beta.tolist(), "cov": cov.tolist(),
                      "rate_ratio_per_sd": {n: round(math.exp(beta[i + 1]), 3)
                                            for i, n in enumerate(names)},
                      "negbin_size": nb_size(storms, np.exp(x @ beta))},
            "hurricane_share": {"coef": hb.tolist(), "cov": hcov.tolist()},
            "major_share": {"coef": mb.tolist(), "cov": mcov.tolist()},
        })

    base = table[0]
    family = max(base["loso_log_score"], key=base["loso_log_score"].get)

    def best(score):
        winners = [t for t in table[1:] if score(t) > score(base)]
        return max(winners, key=score) if winners else base

    picks = {
        "storms": best(lambda t: t["loso_log_score"][family]),
        "hurricane_share": best(lambda t: t["loso_share_log_score"]["hurricane"]),
        "major_share": best(lambda t: t["loso_share_log_score"]["major"]),
    }
    oni_only = next(t for t in table if t["predictors"] == ["oni"])
    b, c = oni_only["count"]["coef"][1] / stats["oni"][1], oni_only["count"]["cov"][1][1]
    se = math.sqrt(c) / stats["oni"][1]
    out = {
        "years": [YEARS[0], YEARS[-1]],
        "storms_per_year": round(float(storms.mean()), 3),
        "hurricane_share": round(float(hurr.sum() / storms.sum()), 4),
        "major_share": round(float(major.sum() / storms.sum()), 4),
        "count_family": family,
        "count_family_reason": "the family with the better leave-one-season-out log score for long_run",
        "predictors": {
            "oni": {"source": ONI_SOURCE, "mean": stats["oni"][0], "sd": stats["oni"][1]},
            **{k: {"source": PSL[k][1], "url": PSL[k][0], "mean": stats[k][0], "sd": stats[k][1]}
               for k in ("tna",)},
        },
        "oni_only_per_unit": {
            "rate_ratio": round(math.exp(b), 3),
            "ci95": [round(math.exp(b - 1.96 * se), 3), round(math.exp(b + 1.96 * se), 3)],
            "p": round(math.erfc(abs(b / se) / math.sqrt(2)), 3),
        },
        "long_run_county_coverage_2018_2025": backtest["share_inside"],
        "models": table,
        "selected": {k: v["predictors"] for k, v in picks.items()},
        "method": (
            "Poisson and negative-binomial regression of storms per season within 250 km of "
            "Georgia, and binomial regression of the hurricane and major-hurricane shares, on "
            "standardized Aug-Oct predictors. Each model is scored by leave-one-season-out log "
            "score against the intercept-only long_run model; a part uses predictors only when "
            "its out-of-sample score beats long_run. County coverage rescales the 2018-2025 "
            "long-run expected counts by the leave-one-season-out rate multipliers."
        ),
    }
    OUT.write_text(json.dumps(out, indent=1))
    for t in table:
        print(t["predictors"], t["loso_log_score"], t["loso_share_log_score"],
              t["county_coverage_2018_2025"], t["count"]["rate_ratio_per_sd"])
    print("selected", out["selected"], "oni", out["oni_only_per_unit"], "family", family)


if __name__ == "__main__":
    main()
