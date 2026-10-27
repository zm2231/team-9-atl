import json
from datetime import UTC, datetime
from types import SimpleNamespace

import numpy as np

from ... import report
from ... import scenario_tools as st
from ...evacuation_tools import _dataset_name, _project_id, _run_query
from .. import data, engine
from .build_season import load

SAVANNAH_TRACK = {"type": "LineString",
                  "coordinates": [[-85.5, 27.0], [-84.4, 30.0], [-82.6, 31.6], [-81.1, 32.6]]}
DEMO_COUNTY = "13051"
DEMO_RUNS = 20
DEMO_RUN_INDEX = 7
IRMA = "2017242N16333"
REPLAY_SOURCE = ("EAGLE-I observed peak outage per county (ext_eaglei_county_storm_2014_2025) "
                 "applied to HHS emPOWER, CMS and ACS county counts")
REPORTS = (
    ("state_long_run", "Georgia, long-run season", lambda: st.state_plan()),
    ("county_chatham", "Chatham County season plan", lambda: st.county_plan(DEMO_COUNTY)),
    ("runs_chatham_savannah_cat3", f"Gulf-to-Savannah category 3, {DEMO_RUNS} runs",
     lambda: _run(draws=DEMO_RUNS)),
    ("run_chatham_savannah_cat3", f"Gulf-to-Savannah category 3, run {DEMO_RUN_INDEX}",
     lambda: _run(draws=DEMO_RUNS, run_index=DEMO_RUN_INDEX)),
    ("replay_irma_2017", "Irma 2017 replayed on today's Georgia", lambda: replay(IRMA)),
)
SCHEMA = [
    ("report_id", "STRING", "Stable id the agent and frontend request"),
    ("scope", "STRING", "state, county, run or runs (report contract v1)"),
    ("title", "STRING", "Display title"),
    ("built_at", "TIMESTAMP", "When the report was computed"),
    ("report_json", "STRING", "The report object, specs/002-scenarios/contracts/report.md"),
]


def _run(**kw):
    payload = {"county_fips": DEMO_COUNTY,
               "scenario": {"track": SAVANNAH_TRACK, "category": 3}}
    parts = [SimpleNamespace(text="report"),
             SimpleNamespace(text=f"CONTEXT v1 {json.dumps(payload)}")]
    ctx = SimpleNamespace(user_content=SimpleNamespace(parts=parts))
    return st.run_scenario(county_fips=DEMO_COUNTY, tool_context=ctx, **kw)


def replay(sid: str) -> dict:
    from google.cloud import bigquery

    obs = _run_query(
        f"""SELECT fips_code, peak_share_total, peak_share_status
            FROM `{_project_id()}.{_dataset_name()}.ext_eaglei_county_storm_2014_2025`
            WHERE sid = @sid AND STARTS_WITH(fips_code, '13')""",
        [bigquery.ScalarQueryParameter("sid", "STRING", sid)])
    shares = {r["fips_code"]: float(r["peak_share_total"]) for r in obs
              if r["peak_share_status"] == "recorded" and r["peak_share_total"] is not None}
    skipped = sum(1 for r in obs if r["peak_share_status"] != "recorded")
    counties = data.counties()
    share = np.array([[shares.get(c["county_fips"], 0.0) for c in counties]])
    people = {k: float(v.sum()) for k, v in
              engine.people_at_risk(SimpleNamespace(outage=share), counties).items()}
    people = {"power_dependent_at_risk": people["power_dependent"],
              "oxygen_users_at_risk": people["oxygen"],
              "dialysis_patients_at_risk": people["dialysis"],
              "facility_beds_exposed": people["facility_beds"],
              "needing_transport_no_vehicle": people["no_vehicle"]}
    rows = [{"county_fips": c["county_fips"], "county_name": c["county_name"],
             "outage_share": round(shares[c["county_fips"]], 4)}
            for c in counties if c["county_fips"] in shares]
    storm = next(s for s in st._MODEL["per_storm"] if s["sid"] == sid)
    storm = {**storm, "name": storm["storm"]}
    return {"report": report.replay_report(storm, people, rows, skipped, REPLAY_SOURCE)}


def main() -> None:
    now = datetime.now(UTC).isoformat()
    rows = []
    for report_id, title, make in REPORTS:
        rep = make()["report"]
        rows.append({"report_id": report_id, "scope": rep["scope"], "title": title,
                     "built_at": now, "report_json": json.dumps(rep, default=str)})
        print(report_id, rep["scope"], len(rows[-1]["report_json"]))
    load("scenario_reports", rows, SCHEMA,
         "Precomputed demo reports (report contract v1), built by "
         "scenario/build/build_reports.py. Rebuild after any model or season-table change.")


if __name__ == "__main__":
    main()
