import json
from datetime import UTC, datetime
from types import SimpleNamespace

from ... import scenario_tools as st
from .build_season import load

SAVANNAH_TRACK = {"type": "LineString",
                  "coordinates": [[-85.5, 27.0], [-84.4, 30.0], [-82.6, 31.6], [-81.1, 32.6]]}
DEMO_COUNTY = "13051"
DEMO_RUNS = 20
DEMO_RUN_INDEX = 7
REPORTS = (
    ("state_long_run", "Georgia, long-run season", lambda: st.state_plan()),
    ("county_chatham", "Chatham County season plan", lambda: st.county_plan(DEMO_COUNTY)),
    ("runs_chatham_savannah_cat3", f"Gulf-to-Savannah category 3, {DEMO_RUNS} runs",
     lambda: _run(draws=DEMO_RUNS)),
    ("run_chatham_savannah_cat3", f"Gulf-to-Savannah category 3, run {DEMO_RUN_INDEX}",
     lambda: _run(draws=DEMO_RUNS, run_index=DEMO_RUN_INDEX)),
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
