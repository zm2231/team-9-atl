import pytest


@pytest.fixture(autouse=True)
def no_bigquery_planner_reads(monkeypatch):
    from readiness_agent import scenario_tools

    monkeypatch.setattr(scenario_tools, "_fetch_site_updates", list)
    monkeypatch.setattr(scenario_tools, "_siting_pool", lambda: None)
