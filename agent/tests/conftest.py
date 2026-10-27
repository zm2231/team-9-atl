import pytest


@pytest.fixture(autouse=True)
def no_bigquery_planner_reads(monkeypatch):
    from readiness_agent import scenario_tools

    monkeypatch.setattr(scenario_tools, "_fetch_site_updates", list)
    monkeypatch.setattr(scenario_tools, "_siting_pool", lambda: None)


@pytest.fixture(autouse=True)
def no_noaa_fetches(monkeypatch):
    from readiness_agent.scenario import conditions

    def offline(url):
        raise OSError(f"offline: {url}")

    monkeypatch.setattr(conditions, "_get", offline)
    conditions._cache.clear()
    yield
    conditions._cache.clear()
