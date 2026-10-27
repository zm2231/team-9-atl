from dataclasses import dataclass
from functools import cache

import numpy as np

from .data import DATA_DIR

FEATURES = ["peak_wind_kt", "hours_34kt", "hours_50kt", "min_dist_km", "pop"]


def transform(x: np.ndarray) -> np.ndarray:
    return np.log1p(np.asarray(x, float))


def expit(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30, 30)))


@dataclass(frozen=True)
class OutageModel:
    mu: np.ndarray
    sd: np.ndarray
    mean: np.ndarray
    chol: np.ndarray
    county_fips: tuple[str, ...]
    tau_storm: float
    sigma: float

    @classmethod
    def load(cls) -> "OutageModel":
        return _load()

    def sample(self, features: np.ndarray, rng: np.random.Generator, n_draws: int) -> np.ndarray:
        z = (transform(features) - self.mu) / self.sd
        k = 1 + len(FEATURES)
        theta = self.mean[None, :] + rng.standard_normal((n_draws, len(self.mean))) @ self.chol.T
        latent = theta[:, :1] + theta[:, 1:k] @ z.T + theta[:, k:]
        latent = latent + rng.normal(0.0, self.tau_storm, size=(n_draws, 1))
        latent = latent + rng.normal(0.0, self.sigma, size=latent.shape)
        return expit(latent)


@cache
def _load() -> OutageModel:
    z = np.load(DATA_DIR / "outage_model.npz")
    return OutageModel(
        mu=z["mu"], sd=z["sd"], mean=z["mean"], chol=z["chol"],
        county_fips=tuple(str(f) for f in z["county_fips"]),
        tau_storm=float(z["tau_storm"]), sigma=float(z["sigma"]),
    )
