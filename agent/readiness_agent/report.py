from typing import Any

REPORT_VERSION = 1
SECTIONS = (
    "who_cannot_leave",
    "power_outage",
    "people_at_risk",
    "where_they_would_go",
    "what_to_fix",
    "storm_history",
    "planner_updates",
    "could_not_tell",
    "audit",
)
SEASON_RANGE = ("typical", "one_in_10", "one_in_100")


def figure(key: str, label: str, unit: str, provenance: str, source: str, *,
           value: float | None = None, range_: dict | None = None,
           range_kind: str | None = None) -> dict[str, Any]:
    return {"key": key, "label": label, "unit": unit, "provenance": provenance,
            "source": source, "value": value, "range": range_, "range_kind": range_kind}


def section(source: str, *, figures: list | None = None, items: list | None = None,
            note: str | None = None, status: str = "ok") -> dict[str, Any]:
    return {"status": status, "source": source, "figures": figures or [],
            "items": items or [], "note": note}


def missing(reason: str, source: str = "") -> dict[str, Any]:
    return {**section(source, status="not_determined"), "reason": reason}


def not_applicable(reason: str) -> dict[str, Any]:
    return {**section("", status="not_applicable"), "reason": reason}


def _ok(block: Any) -> bool:
    return isinstance(block, dict) and block.get("status") not in ("not_determined", "error")


def _season(block: dict, keys: tuple[str, ...]) -> dict[str, Any] | None:
    for k in keys:
        block = block.get(k) if isinstance(block, dict) else None
    if not isinstance(block, dict):
        return None
    return {k: block[k] for k in SEASON_RANGE if k in block}


def _draws(block: Any) -> tuple[Any, dict | None]:
    if isinstance(block, dict) and {"p10", "p50", "p90"} <= set(block):
        if block["p10"] == block["p90"]:
            return block["p50"], None
        return None, {k: block[k] for k in ("p10", "p50", "p90")}
    return block, None


def _people_season(row: dict, source: str) -> list[dict[str, Any]]:
    out = []
    for key, label, path in (
        ("power_dependent_affected", "Power-dependent residents losing power",
         ("power_dependent_affected",)),
        ("no_powered_seat", "Lacking shelter: no powered seat",
         ("lacking_shelter", "no_powered_seat")),
        ("no_dialysis_chair", "Lacking shelter: no dialysis chair",
         ("lacking_shelter", "no_dialysis_chair")),
        ("lacking_shelter_total", "Lacking shelter: total", ("lacking_shelter", "total")),
        ("needing_transport_no_vehicle", "Needing transport: no vehicle (65+ households)",
         ("needing_transport", "no_vehicle")),
        ("needing_transport_no_vehicle_low", "Needing transport: no vehicle (all households)",
         ("needing_transport", "no_vehicle_low")),
    ):
        r = _season(row, path)
        if r:
            out.append(figure(key, label, "people", "simulated", source, range_=r,
                              range_kind="season"))
    return out


def _outlook(plan: dict) -> dict[str, Any] | None:
    by = (plan.get("power_outage_frequency") or {}).get("by_outlook") or {}
    chosen = by.get(plan.get("outlook")) or next(iter(by.values()), None)
    if not chosen:
        return None
    return {"outlook": plan.get("outlook"), "label": chosen.get("label"),
            "storms_per_year": chosen.get("storms_per_year"), "note": chosen.get("note"),
            "auto": plan.get("auto")}


PEOPLE_NOTE = ("Lacking shelter and needing transport are separate needs and are never added: "
               "one person can be in both.")


def county_report(plan: dict, profile: dict | None) -> dict[str, Any]:
    brief_block = plan.get("readiness_brief") or {}
    brief = brief_block.get("brief") if _ok(brief_block) else None
    brief_src = brief_block.get("source", "")
    s: dict[str, Any] = {}

    if brief:
        w = brief["who_cannot_leave"]
        s["who_cannot_leave"] = section(
            "; ".join(w.get("sources") or []) or brief_src,
            figures=[figure("power_dependent_residents", "Power-dependent residents (Medicare)",
                            "people", "registry", "HHS emPOWER",
                            value=w.get("power_dependent_residents"))],
            items=[{"kind": "tract", **t} for t in w.get("tracts", [])]
            + [{"kind": "facility", **f} for f in w.get("facilities", [])],
            note=w.get("basis"))
        g = brief["where_they_would_go"]
        s["where_they_would_go"] = section(
            g.get("source", brief_src), items=g.get("destinations", []),
            note=" ".join(x for x in (g.get("reachable"), g.get("live_check")) if x))
        c = brief["could_not_tell"]
        s["could_not_tell"] = section(
            brief_src,
            figures=[figure(k, k.replace("_", " "), "count", "registry", brief_src, value=v)
                     for k, v in c.items() if isinstance(v, int)],
            items=c.get("notes", []))
        fixes = [{"kind": k, "entries": v} for k, v in brief["what_to_fix"].items()
                 if isinstance(v, list)]
    else:
        reason = brief_block.get("reason", "readiness brief unavailable")
        for key in ("who_cannot_leave", "where_they_would_go", "could_not_tell"):
            s[key] = missing(reason, brief_src)
        fixes = []

    freq = plan.get("power_outage_frequency") or {}
    by = freq.get("by_outlook") or {}
    row = by.get(plan.get("outlook")) or next(iter(by.values()), None)
    if _ok(freq) and row:
        src = freq.get("source", "")
        p25 = row.get("p_outage25_per_year")
        s["power_outage"] = section(src, figures=[figure(
            "p_outage25_per_year", "Chance per year of a 25%+ customer outage", "share",
            "simulated", src, value=p25)], note=row.get("note"))
        s["people_at_risk"] = section(src, figures=_people_season(row, src), note=PEOPLE_NOTE)
    else:
        s["power_outage"] = missing(freq.get("reason", "season model unavailable"))
        s["people_at_risk"] = missing(freq.get("reason", "season model unavailable"))

    gen = plan.get("generator_switch_effect") or {}
    if _ok(gen) and "county_lacking_shelter" in gen:
        src = gen.get("source", "")
        fixes.append({"kind": "confirm_unrecorded_generators", "switch": gen.get("switch"),
                      "shelters_switched": gen.get("shelters_switched"),
                      "figures": [
                          figure("lacking_shelter_recorded_only",
                                 "Lacking shelter, generators as recorded", "people",
                                 "simulated", src,
                                 range_=gen["county_lacking_shelter"]["recorded_only"],
                                 range_kind="season"),
                          figure("lacking_shelter_unrecorded_assumed",
                                 "Lacking shelter, unrecorded generators assumed present",
                                 "people", "simulated", src,
                                 range_=gen["county_lacking_shelter"]["all_assumed"],
                                 range_kind="season")],
                      "reading": gen.get("reading")})
    s["what_to_fix"] = section(brief_src, items=fixes) if fixes else missing(
        "no fix lists could be computed")

    if profile and _ok(profile):
        src = profile.get("model", "")
        yc = profile.get("yearly_chance") or {}
        figs = [figure(f"return_period_{k}", f"Years between {k.split('_')[1]} outages",
                       "years", "simulated", src, value=(yc.get(k) or {}).get(
                           "return_period_years"))
                for k in ("outage_25pct", "outage_50pct") if k in yc]
        fr = profile.get("fragility") or {}
        figs.append(figure("fragility_rank", "Grid fragility rank (1 = most outage-prone)",
                           "rank", "simulated", src, value=fr.get("rank_most_fragile")))
        s["storm_history"] = section(src, figures=figs, items=profile.get("labelled_storms", []),
                                     note=profile.get("labelled_note"))
    else:
        s["storm_history"] = missing("county storm profile unavailable")

    s["planner_updates"] = plan.get("planner_updates") or section(
        "scenario_site_updates", note="No planner updates in effect.")

    audit = plan.get("audit") or {}
    s["audit"] = section(audit.get("source", ""), items=audit.get("rows", []),
                         note=audit.get("question")) if _ok(audit) else missing(
        audit.get("reason", "audit unavailable"), audit.get("source", ""))

    return _wrap("county", {"county_fips": plan.get("county_fips"),
                            "county_name": plan.get("county_name")}, _outlook(plan), s,
                 plan.get("source", ""))


def state_report(run: dict, worst: list[dict] | None, gaps: dict | None) -> dict[str, Any]:
    src = run.get("source", "")
    s: dict[str, Any] = {}
    counties = sorted(run.get("counties", []),
                      key=lambda c: -c["lacking_shelter"]["total"]["one_in_10"])
    s["who_cannot_leave"] = section(
        src, items=[{"kind": "county", "county_fips": c["county_fips"],
                     "county_name": c["county_name"],
                     "lacking_shelter_one_in_10": c["lacking_shelter"]["total"]["one_in_10"],
                     "power_dependent_affected_one_in_10":
                         c["power_dependent_affected"]["one_in_10"]}
                    for c in counties[:10]],
        note="Counties with the most people lacking shelter in a 1-in-10 season; ask for a "
             "county plan for tract and facility detail.")
    sw = run.get("statewide", {})
    s["power_outage"] = section(src, figures=[figure(
        "p_any_county_outage25_per_year",
        "Chance per year that any Georgia county has a 25%+ customer outage", "share",
        "simulated", src, value=sw.get("p_any_county_outage25_per_year"))])
    s["people_at_risk"] = section(src, figures=_people_season(sw, src), note=PEOPLE_NOTE)
    s["where_they_would_go"] = not_applicable(
        "Destinations are matched per county; ask for a county plan.")
    s["what_to_fix"] = section(
        (gaps or {}).get("source", ""), items=(gaps or {}).get("gaps", [])) if gaps and _ok(
        gaps) else missing("fix ranking unavailable")
    s["storm_history"] = section("scenario_worst_events", items=worst) if worst else missing(
        "worst-events table unavailable")
    s["planner_updates"] = section("scenario_site_updates",
                                   note="No planner updates in effect.")
    s["could_not_tell"] = not_applicable("Record gaps are counted per county.")
    s["audit"] = not_applicable("The audit compares a county plan's ranked tracts.")
    outlook = {"outlook": run.get("outlook"), "label": run.get("label"),
               "storms_per_year": run.get("storms_per_year"), "note": run.get("outlook_note")}
    return _wrap("state", {"county_fips": None, "county_name": "Georgia"}, outlook, s, src)


def run_report(result: dict) -> dict[str, Any]:
    sc = result.get("scenario", {})
    src = sc.get("source_label") or result.get("source", "")
    runs = sc.get("runs") or {}
    one = runs.get("run_index") is not None
    kind = None if one else "runs"
    s: dict[str, Any] = {}

    def fig(key, label, unit, block, provenance="simulated"):
        value, rng = _draws(block)
        return figure(key, label, unit, provenance, src, value=value, range_=rng,
                      range_kind=None if rng is None else kind)

    sw = result.get("statewide", {})
    rows = result.get("counties", [])
    s["power_outage"] = section(src, figures=[
        fig("counties_affected", "Counties with 10%+ outage", "count",
            sw.get("counties_affected"))],
        items=[{"county_fips": c["county_fips"], "county_name": c["county_name"],
                "outage_share": c["outage_share"], "peak_wind_kt": c["peak_wind_kt"],
                "ts_winds_arrive_h": c["ts_winds_arrive_h"], "status": c.get("status")}
               for c in rows])
    s["people_at_risk"] = section(src, figures=[
        fig("power_dependent_at_risk", "Power-dependent residents losing power", "people",
            sw.get("power_dependent_at_risk")),
        fig("oxygen_users_at_risk", "Oxygen users losing power", "people",
            sw.get("oxygen_users_at_risk")),
        fig("dialysis_patients_at_risk", "Dialysis patients whose centre is down", "people",
            sw.get("dialysis_patients_at_risk")),
        fig("facility_beds_exposed", "Nursing-home and assisted-living beds exposed", "beds",
            sw.get("facility_beds_exposed")),
        fig("needing_transport_no_vehicle", "Needing transport: no vehicle (65+ households)",
            "people", sw.get("needing_transport_no_vehicle")),
        fig("needing_transport_no_vehicle_low",
            "Needing transport: no vehicle (all households)", "people",
            sw.get("needing_transport_no_vehicle_low")),
    ], note=PEOPLE_NOTE)
    rec = result.get("receiving")
    if rec:
        ls, nt = rec.get("lacking_shelter", {}), rec.get("needing_transport", {})
        s["where_they_would_go"] = section(
            src, figures=[
                figure("seeking_powered_seat", "Seeking a powered seat", "people",
                       "simulated", src, value=ls.get("seeking_powered_seat")),
                figure("powered_seats_reachable", "Powered seats reachable", "seats",
                       "registry", src, value=ls.get("powered_seats_reachable")),
                figure("no_powered_seat", "Lacking shelter: no powered seat", "people",
                       "simulated", src, value=ls.get("no_powered_seat")),
                figure("cannot_arrive_in_time", "Needing transport: cannot arrive in time",
                       "people", "simulated", src, value=nt.get("cannot_arrive_in_time"))],
            items=rec.get("sites", []),
            note=f"Drive times: {rec.get('drive_time_source')}.")
        fixes = [{"kind": "switch_effect", "delta": rec["delta"]}] if rec.get("delta") else []
        short = ls.get("no_powered_seat") or 0
        if short:
            fixes.append({"kind": "powered_seat_shortfall", "people": short,
                          "candidates": [x for x in rec.get("sites", [])
                                         if x.get("kind") == "medical_shelter"
                                         and x.get("generator") != "YES"]})
        s["what_to_fix"] = section(src, items=fixes) if fixes else section(
            src, note="No shortfall at the reachable sites in this scenario.")
    else:
        s["where_they_would_go"] = not_applicable("Select a county to match destinations.")
        s["what_to_fix"] = not_applicable("Select a county to match destinations.")
    s["storm_history"] = section(sc.get("source", ""), items=[sc.get("likelihood")],
                                 note=f"Support: {sc.get('support')}; "
                                      f"{sc.get('range_label')}.")
    s["who_cannot_leave"] = not_applicable("Ask for a county plan for tracts and facilities.")
    s["planner_updates"] = section("scenario_site_updates",
                                   note="No planner updates in effect.")
    s["could_not_tell"] = section(src, items=[
        "Outage is modelled from wind exposure; local tree and line conditions are not known.",
        "Whether a shelter will open during this storm is not known from this data."])
    s["audit"] = not_applicable("The audit compares a county plan's ranked tracts.")
    scope = "run" if one else "runs"
    subject = {"county_fips": result.get("selected_county_fips"),
               "county_name": result.get("selected_county_name"),
               "runs": runs, "scenario": {k: sc.get(k) for k in
                                          ("source", "origin", "category", "month")}}
    return _wrap(scope, subject, None, s, result.get("source", ""))


def _wrap(scope: str, subject: dict, outlook: dict | None, sections: dict,
          source: str) -> dict[str, Any]:
    return {"report_version": REPORT_VERSION, "scope": scope, "subject": subject,
            "season": outlook, "sections": {k: sections[k] for k in SECTIONS},
            "source": source}
