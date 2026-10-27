import { useStore } from "../../state/store";
import { useScenario } from "../../state/scenario";
import { listFlagCounts } from "../../lib/simulation";

/** Always visible and counted: in this challenge it is a finding, not a disclaimer (Constitution VII). */
export default function CouldNotTell() {
  const { state, countyByFips, shelterById } = useStore();
  const scenario = useScenario();
  if (state.mapData.status !== "ready" || !state.mapData.data) return null;

  const fips = state.hoverFips ?? state.selectedFips;
  const county = fips ? countyByFips.get(fips) : undefined;
  const receiving = scenario
    ? scenario.receiving.map((r) => shelterById.get(r.shelter_id)).filter((s) => s !== undefined)
    : [];
  const recvWc = listFlagCounts(receiving, "wheelchair_accessible");

  return (
    <div className="card" data-testid="could-not-tell">
      <h2>What we could not tell you</h2>
      <ul className="small">
        {state.mapData.data.notes.map((n) => (
          <li key={n}>{n}</li>
        ))}
        {county && county.shelter_count > 0 && (
          <>
            <li>
              {county.name}: {county.wheelchair.unrecorded} of {county.shelter_count} shelters never assessed for
              wheelchair access.
            </li>
            <li>
              {county.name}: {county.generator.unrecorded} of {county.shelter_count} shelters have no generator
              record.
            </li>
          </>
        )}
        {scenario && (
          <li>
            Receiving shelters: {recvWc.unrecorded} of {receiving.length} never assessed for wheelchair access.
            Distances are straight-line; drive times not included.
          </li>
        )}
      </ul>
    </div>
  );
}
