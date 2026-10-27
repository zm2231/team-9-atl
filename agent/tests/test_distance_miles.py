from readiness_agent.evacuation_tools import query_capped, with_miles


def test_nested_km_keys_gain_miles_twins():
    out = with_miles(
        {"nearest_km": 16.0, "sites": [{"straight_line_km": 100, "storm_speed_kmh": 20.0}], "name": "x"}
    )
    assert out["nearest_mi"] == 9.9
    assert out["sites"][0]["straight_line_mi"] == 62.1
    assert out["sites"][0]["storm_speed_mph"] == 12.4
    assert out["name"] == "x"


def test_bare_km_key_gains_mi():
    assert with_miles({"minutes": 30.0, "km": 50.0})["mi"] == 31.1


def test_non_numeric_and_missing_values_are_left_alone():
    out = with_miles({"nearest_km": None, "share_reaching_georgia_100km": 0.4, "flag_km": True})
    assert "nearest_mi" not in out
    assert "flag_mi" not in out
    assert "share_reaching_georgia_100mi" not in out


def test_registered_tools_return_miles():
    assert query_capped(lambda: {"min_dist_km": 50.0})()["min_dist_mi"] == 31.1
