import { Fragment } from "react";
import { exclusionNote, flagClass, flagCountsLine, flagLabel, formatNumber } from "../../lib/flags";
import { capacitySummary, listFlagCounts } from "../../lib/simulation";
import type { HurricaneScenario, Shelter } from "../../lib/types";
import { useStore } from "../../state/store";
import { useScenario } from "../../state/scenario";

export function ReceivingListView({
  scenario,
  shelterById,
  onSelect,
}: {
  scenario: HurricaneScenario;
  shelterById: Map<string, Shelter>;
  onSelect: (id: string) => void;
}) {
  const rows = scenario.receiving
    .map((r) => ({ r, s: shelterById.get(r.shelter_id) }))
    .filter((x): x is { r: (typeof x)["r"]; s: Shelter } => !!x.s);
  const shelters = rows.map((x) => x.s);
  const cap = capacitySummary(shelters);
  const excluded = exclusionNote(cap.excluded);

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
          <p className="small">
            Recorded capacity: {formatNumber(cap.total)}
            {excluded && <span className="note"> · {excluded}</span>}
          </p>
          <table className="receiving">
            <thead>
              <tr>
                <th>#</th>
                <th>Shelter</th>
                <th>Capacity</th>
                <th title="Distance (straight-line)">km*</th>
                <th>Wheelchair</th>
                <th>Generator</th>
                <th>Surge</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(({ r, s }) => (
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
                  <td>
                    <span className={flagClass(s.wheelchair_accessible)}>{flagLabel(s.wheelchair_accessible)}</span>
                  </td>
                  <td>
                    <span className={flagClass(s.generator_onsite)}>{flagLabel(s.generator_onsite)}</span>
                  </td>
                  <td>
                    <span className={flagClass(s.in_surge_slosh_area)}>{flagLabel(s.in_surge_slosh_area)}</span>
                  </td>
                </tr>
                <tr onClick={() => onSelect(s.shelter_id)} className="receiving__reason">
                  <td />
                  <td colSpan={6}>{r.reason}</td>
                </tr>
                </Fragment>
              ))}
            </tbody>
          </table>
          <p className="small muted">* Straight-line distance from the nearest affected county's center, not drive time.</p>
        </>
      )}
    </div>
  );
}

/** Receiving shelters: within reach, sorted by capacity (FR-018a–d). */
export default function ReceivingList() {
  const { dispatch, shelterById } = useStore();
  const scenario = useScenario();
  if (!scenario) return null;
  return (
    <ReceivingListView
      scenario={scenario}
      shelterById={shelterById}
      onSelect={(id) => dispatch({ type: "selectShelter", id })}
    />
  );
}
