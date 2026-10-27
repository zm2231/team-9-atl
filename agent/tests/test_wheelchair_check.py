from types import SimpleNamespace

from readiness_agent.wheelchair_check import MAX_SHELTERS, check_wheelchair, parse

SRC = [{"title": "Glynn Academy", "uri": "https://maps.google.com/?cid=1", "placeId": "abc"}]


def test_listed_accessible_needs_a_maps_source():
    text = "PLACE: same\nWHEELCHAIR: accessible_entrance\nEVIDENCE: Wheelchair-accessible entrance."
    assert parse("1", text, SRC)["status"] == "listed_accessible"
    assert parse("1", text, [])["status"] == "not_found"


def test_unknown_and_gone_and_garbage():
    assert parse("1", "PLACE: same\nWHEELCHAIR: unknown\nEVIDENCE: none", SRC)["status"] == "no_info"
    gone = parse("1", "PLACE: gone\nWHEELCHAIR: unknown\nEVIDENCE: Permanently closed.", SRC)
    assert (gone["status"], gone["place"]) == ("no_info", "gone")
    assert parse("1", "I think it is accessible.", SRC)["status"] == "not_found"
    assert parse("1", "PLACE: same\nWHEELCHAIR: no_accessible_entrance\nEVIDENCE: x", SRC)[
        "status"] == "listed_not_accessible"


def test_batch_is_capped_and_one_failure_does_not_sink_it():
    calls = []

    def generate_content(model, contents, config):
        calls.append(contents)
        if "Shelter 1" in contents:
            raise RuntimeError("quota")
        return SimpleNamespace(text="PLACE: same\nWHEELCHAIR: unknown\nEVIDENCE: none", candidates=[])

    client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    shelters = [{"shelter_id": str(i), "name": f"Shelter {i}", "address": "x"} for i in range(15)]
    out = check_wheelchair(shelters, client=client)
    assert len(out) == len(calls) == MAX_SHELTERS
    assert out[1]["status"] == "error"
    assert out[0]["status"] == "not_found"  # no Maps source, so no claim
