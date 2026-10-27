import csv
import tempfile
import urllib.request
from pathlib import Path

URL = ("https://www2.census.gov/programs-surveys/acs/summary_file/2022/"
       "table-based-SF/data/5YRData/acsdt5y2022-b03002.dat")
DEST = Path(__file__).resolve().parent / "data" / "ga_tract_race_acs2022.csv"
COLUMNS = {
    "B03002_E001": "total",
    "B03002_E003": "white_nh",
    "B03002_E004": "black_nh",
    "B03002_E006": "asian_nh",
    "B03002_E012": "hispanic",
}

with tempfile.TemporaryDirectory() as tmp:
    raw = Path(tmp) / "b03002.dat"
    urllib.request.urlretrieve(URL, raw)
    rows = []
    with raw.open() as f:
        for rec in csv.DictReader(f, delimiter="|"):
            if rec["GEO_ID"].startswith("1400000US13"):
                rows.append({"geo_id": rec["GEO_ID"][9:], **{v: int(rec[k]) for k, v in COLUMNS.items()}})

assert len(rows) == 2796, len(rows)
DEST.parent.mkdir(exist_ok=True)
with DEST.open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
print(f"{len(rows)} Georgia tracts -> {DEST}")
