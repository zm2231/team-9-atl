import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

HERE = Path(sys.argv[1])
SEED = 20261027
N_DRAWS = 1000
FEATURES = ["peak_wind_kt", "hours_34kt", "hours_50kt", "min_dist_km", "pop"]
BIG = 0.10


def logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def expit(x):
    return 1 / (1 + np.exp(-np.clip(x, -30, 30)))


def transformed(f):
    return np.column_stack([np.log1p(f[c]) for c in FEATURES])


def fit_hierarchical(train, test, rng, em_iters):
    a, b = transformed(train), transformed(test)
    mu, sd = a.mean(0), a.std(0)
    sd[sd == 0] = 1
    a, b = (a - mu) / sd, (b - mu) / sd
    counties = sorted(train.fips.unique())
    storms = sorted(train.storm.unique())
    ci = {v: i for i, v in enumerate(counties)}
    si = {v: i for i, v in enumerate(storms)}
    k = 1 + len(FEATURES)
    p = k + len(counties) + len(storms)

    def design(frame, z):
        x = np.zeros((len(frame), p))
        x[:, 0] = 1
        x[:, 1:k] = z
        for r, c in enumerate(frame.fips):
            if c in ci:
                x[r, k + ci[c]] = 1
        for r, s in enumerate(frame.storm):
            if s in si:
                x[r, k + len(counties) + si[s]] = 1
        return x

    x, xt = design(train, a), design(test, b)
    y = logit((train.peak_share.to_numpy() * train.customers + 0.5) / (train.customers + 1.0))
    tau_c, tau_s = 0.70, 0.80
    s0 = k + len(counties)
    for _ in range(max(1, em_iters)):
        prior = np.r_[4.0, np.repeat(1.5, len(FEATURES)), np.repeat(tau_c, len(counties)), np.repeat(tau_s, len(storms))]
        precision = x.T @ x + np.diag(1 / prior**2)
        cov_unit = np.linalg.pinv(precision)
        coef = cov_unit @ x.T @ y
        sigma = max(np.sqrt(np.mean((y - x @ coef) ** 2)), 0.25)
        cov = sigma**2 * cov_unit
        if em_iters == 0:
            break
        se = coef[s0:]
        tau_s = float(np.sqrt(np.mean(se**2 + np.diag(cov)[s0:])))
        ce = coef[k:s0]
        tau_c = float(np.sqrt(np.mean(ce**2 + np.diag(cov)[k:s0])))
    draws = rng.multivariate_normal(coef, cov, size=N_DRAWS)
    latent = draws @ xt.T
    latent += rng.normal(0, tau_s, size=(N_DRAWS, 1))
    latent += rng.normal(0, sigma, size=(N_DRAWS, len(test)))
    pred = expit(latent)
    return pred.mean(0), np.quantile(pred, [0.1, 0.9], axis=0), {"tau_storm": tau_s, "tau_county": tau_c, "sigma": sigma}


def run(data, label, em_iters):
    rows = []
    for fold, storm in enumerate(sorted(data.storm.unique())):
        train, test = data[data.storm != storm], data[data.storm == storm]
        rng = np.random.default_rng(SEED + fold)
        mean, (lo, hi), diag = fit_hierarchical(train, test, rng, em_iters)
        y = test.peak_share.to_numpy()
        hgb = HistGradientBoostingRegressor(max_iter=100, learning_rate=0.06, max_leaf_nodes=12, l2_regularization=2.0, random_state=SEED)
        hgb.fit(transformed(train), train.peak_share)
        h = np.clip(hgb.predict(transformed(test)), 0, 1)
        rows.append({
            "storm": storm, "n": len(test), "obs_mean": y.mean(), "pred_mean": mean.mean(),
            "hier_mae": np.abs(y - mean).mean(), "cover80": np.mean((y >= lo) & (y <= hi)),
            "hgb_mae": np.abs(y - h).mean(), "const_mae": np.abs(y - train.peak_share.mean()).mean(),
            "storm_total_in_band": bool(lo.mean() <= y.mean() <= hi.mean()), **diag,
        })
    r = pd.DataFrame(rows)
    big = r[r.obs_mean >= BIG]
    summary = {
        "label": label, "rows": len(data), "storms": int(r.shape[0]),
        "hier_mae": float(np.average(r.hier_mae, weights=r.n)), "hgb_mae": float(np.average(r.hgb_mae, weights=r.n)),
        "const_mae": float(np.average(r.const_mae, weights=r.n)), "cover80": float(np.average(r.cover80, weights=r.n)),
        "big_storms": big.storm.tolist(), "big_hier_mae": float(big.hier_mae.mean()), "big_hgb_mae": float(big.hgb_mae.mean()),
        "big_cover80": float(big.cover80.mean()), "tau_storm_median": float(r.tau_storm.median()),
    }
    return r, summary


raw = pd.read_parquet(HERE / "features_v2.parquet")
base = raw[(raw.peak_share_status == "recorded") & (raw.season >= 2018)].dropna(subset=FEATURES + ["peak_share", "customers"])
out = {}
for label, data, em in [
    ("ga_fl_27storms_em", base, 8),
    ("ga_fl_27storms_floor", base, 0),
    ("ga_only_27storms_em", base[base.state == "GA"], 8),
]:
    r, s = run(data, label, em)
    out[label] = {"summary": s, "per_storm": r.round(4).to_dict(orient="records")}
    print(json.dumps(s))
    if label == "ga_fl_27storms_em":
        print(r[["storm", "n", "obs_mean", "pred_mean", "hier_mae", "cover80", "hgb_mae", "storm_total_in_band", "tau_storm"]].round(3).to_string())
(HERE / "loso_v2.json").write_text(json.dumps(out, indent=2, default=float) + "\n")
