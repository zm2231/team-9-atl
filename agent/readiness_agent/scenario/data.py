import json
from functools import cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"


@cache
def _json(name: str):
    return json.loads((DATA_DIR / name).read_text())


def counties() -> list[dict]:
    return _json("counties.json")


def sites() -> dict:
    if not (DATA_DIR / "sites.json").exists():
        return {"medical_shelters": [], "dialysis_centers": []}
    return _json("sites.json")


def tracks() -> dict:
    return _json("tracks.json")


def model_npz() -> Path:
    return DATA_DIR / "outage_model.npz"


def clear_cache() -> None:
    _json.cache_clear()
