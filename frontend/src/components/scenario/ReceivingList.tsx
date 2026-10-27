import { Fragment, useEffect } from "react";
import { exclusionNote, flagClass, flagCountsLine, flagLabel, formatNumber, NOAA_SURGE_SOURCE } from "../../lib/flags";
import { capacitySummary, listFlagCounts } from "../../lib/simulation";
import { useWheelchairChecker } from "../../lib/useWheelchairChecker";
import type { HurricaneScenario, Shelter, WheelchairCheck } from "../../lib/types";
import { useStore } from "../../state/store";
import { useScenario } from "../../state/scenario";
import { MapsWheelchair, SurgeFlag } from "../FlagNotes";

/** The server checks at most this many per request (wheelchair_check.MAX_SHELTERS). */
export const MAPS_CHECK_BATCH = 3;

/** Top-ranked not-recorded shelters are looked up on Google Maps automatically; the rest on request. */
export const MAPS_AUTO_CHECK = 3;

export function ReceivingListView({
  scenario,
  shelterById,
  onSelect,
  wheelchairChecks = new Map(),
  onCheckWheelchair,
  checking = false,
  checkError,
}: {
  scenario: HurricaneScenario;
  shelterById: Map<string, Shelter>;
  onSelect: (id: string) => void;
  wheelchairChecks?: Map<string, WheelchairCheck>;
  onCheckWheelchair?: (ids: string[]) => void;
  checking?: boolean;
  checkError?: string;
}) {
  const rows = scenario.receiving
    .map((r) => ({ r, s: shelterById.get(r.shelter_id) }))
    .filter((x): x is { r: (typeof x)["r"]; s: Shelter } => !!x.s);
  const shelters = rows.map((x) => x.s);
  const cap = capacitySummary(shelters);
  const excluded = exclusionNote(cap.excluded);
  const blankWheelchair = shelters.filter((s) => s.wheelchair_accessible === "UNRECORDED");
  const toCheck = blankWheelchair.filter((s) => !wheelchairChecks.has(s.shelter_id)).slice(0, MAPS_CHECK_BATCH);
  const mapsListed = blankWheelchair.filter(
    (s) => wheelchairChecks.get(s.shelter_id)?.status === "listed_accessible",
  ).length;
  const checked = blankWheelchair.filter((s) => wheelchairChecks.has(s.shelter_id)).length;
  const surgeFromNoaa = shelters.filter((s) => s.in_surge_source === "noaa_slosh").length;

  return (
    <div className="card card--sim" data-testid="receiving-list">
      <span className="badge-sim">Illustrative scenario — not a forecast</span>
      <h2>Where people would go</h2>
      {rows.length === 0 ? (
        <p data-testid="receiving-empty">
          No shelters within {scenario.cutoff_km} km outside the affected area — try raising the reach cutoff.
        </p>
      ) : (
        <>
          <p className="small" data-testid="receiving-header">
            {rows.length} shelters within {scenario.cutoff_km} km outside the affected area · wheelchair access:{" "}
            {flagCountsLine(listFlagCounts(shelters, "wheelchair_accessible"))}
          </p>
          {checked > 0 && (
            <p className="small" data-testid="maps-summary">
              <span className="kind kind--live">Live check</span> Of {checked} not-recorded shelters looked up,{" "}
              <span translate="no">Google Maps</span> lists an accessible entrance for {mapsListed}. Unverified: not
              proof of a usable entrance or that the shelter admits people.
            </p>
          )}
          {onCheckWheelchair && toCheck.length > 0 && (
            <p className="small">
              <button
                type="button"
                className="btn"
                disabled={checking}
                onClick={() => onCheckWheelchair(toCheck.map((s) => s.shelter_id))}
                data-testid="maps-check-button"
              >
                {checking
                  ? "Checking Google Maps…"
                  : `Check ${toCheck.length} more not-recorded shelter${toCheck.length === 1 ? "" : "s"} on Google Maps`}
              </button>
              {checkError && <span className="note"> {checkError}</span>}
            </p>
          )}
          <p className="small">
            Recorded capacity: {formatNumber(cap.total)}
            {excluded && <span className="note"> · {excluded}</span>}
          </p>
          <div className="table-scroll">
          <table className="receiving">
            <thead>
              <tr>
                <th>#</th>
                <th>Shelter</th>
                <th>Capacity</th>
                <th title="Distance (straight-line)">km*</th>
                <th>Records</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(({ r, s }) => {
                const check = wheelchairChecks.get(s.shelter_id);
                return (
                <Fragment key={r.shelter_id}>
                <tr onClick={() => onSelect(s.shelter_id)} data-testid="receiving-row" className="receiving__main">
                  <td>{r.rank}</td>
                  <td>
                    {s.name}
                    {s.quality_flags.length > 0 && <span className="shelter-warn"> !</span>}
                    <div className="muted">{s.county_name}</div>
                  </td>
                  <td>{s.evacuation_capacity === null ? "Not recorded" : formatNumber(s.evacuation_capacity)}</td>
                  <td>{Math.round(r.distance_km.value ?? 0)} km</td>
                  <td className="receiving__flags">
                    <div>
                      <span className="muted">Wheelchair</span>{" "}
                      <span className={flagClass(s.wheelchair_accessible)}>{flagLabel(s.wheelchair_accessible)}</span>
                      {check && s.wheelchair_accessible === "UNRECORDED" && <MapsWheelchair check={check} />}
                      {!check && checking && s.wheelchair_accessible === "UNRECORDED" && (
                        <div className="maps-check muted">Checking Google Maps…</div>
                      )}
                    </div>
                    <div>
                      <span className="muted">Generator</span>{" "}
                      <span className={flagClass(s.generator_onsite)}>{flagLabel(s.generator_onsite)}</span>
                    </div>
                    <div>
                      <span className="muted">Surge zone</span> <SurgeFlag s={s} />
                    </div>
                  </td>
                </tr>
                <tr onClick={() => onSelect(s.shelter_id)} className="receiving__reason">
                  <td />
                  <td colSpan={4}>{r.reason}</td>
                </tr>
                </Fragment>
                );
              })}
            </tbody>
          </table>
          </div>
          <p className="small muted">* Straight-line distance from the nearest affected county's center, not drive time.</p>
          {surgeFromNoaa > 0 && (
            <p className="small muted" data-testid="surge-noaa-note">
              <span className="kind kind--noaa">NOAA map</span> {surgeFromNoaa} surge flags had no registry record
              and come from {NOAA_SURGE_SOURCE}: worst case within about 100 m, a planning composite, not a forecast.
            </p>
          )}
        </>
      )}
    </div>
  );
}

/** Receiving shelters: within reach, sorted by capacity (FR-018a–d). */
export default function ReceivingList() {
  const { dispatch, shelterById } = useStore();
  const scenario = useScenario();
  const { checks, checking, error, check, checkOnce } = useWheelchairChecker();

  const autoIds = (scenario?.receiving ?? [])
    .map((r) => shelterById.get(r.shelter_id))
    .filter((s): s is Shelter => !!s && s.wheelchair_accessible === "UNRECORDED")
    .slice(0, MAPS_AUTO_CHECK)
    .map((s) => s.shelter_id);
  const autoKey = autoIds.join(",");
  useEffect(() => {
    checkOnce(autoIds);
  }, [autoKey]);

  if (!scenario) return null;
  return (
    <ReceivingListView
      scenario={scenario}
      shelterById={shelterById}
      onSelect={(id) => dispatch({ type: "selectShelter", id })}
      wheelchairChecks={checks}
      onCheckWheelchair={check}
      checking={checking}
      checkError={error}
    />
  );
}
