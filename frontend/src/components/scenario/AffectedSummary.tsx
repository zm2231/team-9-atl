import { exclusionNote, flagCountsLine, formatNumber } from "../../lib/flags";
import { capacitySummary, listFlagCounts } from "../../lib/simulation";
import { useStore } from "../../state/store";
import { countyNames } from "../../lib/geo";
import { useScenario } from "../../state/scenario";

/** Shelters inside the simulated band (FR-018, FR-019). */
export default function AffectedSummary() {
  const { shelterById } = useStore();
  const scenario = useScenario();
  if (!scenario) return null;
  const shelters = scenario.affected_shelter_ids.map((id) => shelterById.get(id)).filter((s) => s !== undefined);
  const cap = capacitySummary(shelters);
  const excluded = exclusionNote(cap.excluded);
  const surgeYes = shelters.filter((s) => s.in_surge_slosh_area === "YES");
  const names = scenario.affected_county_fips.map((f) => countyNames.get(f) ?? f);

  return (
    <div className="card card--sim" data-testid="affected-summary">
      <span className="badge-sim">Illustrative scenario — not a forecast</span>
      <h2>
        Category {scenario.category} track · {scenario.half_width_km} km either side
      </h2>
      <div className="small">
        <strong>Affected counties ({names.length}):</strong> {names.join(", ") || "none in Georgia"}
      </div>
      <div className="row">
        <span className="row__label">Shelters inside the band</span>
        <span>{shelters.length}</span>
      </div>
      <div className="row">
        <span className="row__label">Recorded capacity</span>
        <span>
          {formatNumber(cap.total)}
          <span className="kind">Registry</span>
        </span>
      </div>
      {excluded && (
        <div className="note">
          {excluded}. Including them: {formatNumber(cap.totalInclSuspect)}.
        </div>
      )}
      <div className="row">
        <span className="row__label">Wheelchair access</span>
        <span>{flagCountsLine(listFlagCounts(shelters, "wheelchair_accessible"))}</span>
      </div>
      <div className="row">
        <span className="row__label">Generator on site</span>
        <span>{flagCountsLine(listFlagCounts(shelters, "generator_onsite"))}</span>
      </div>
      <div className="row">
        <span className="row__label">In a surge zone</span>
        <span>{flagCountsLine(listFlagCounts(shelters, "in_surge_slosh_area"))}</span>
      </div>
      {surgeYes.length > 0 && (
        <div className="small">
          <strong>Recorded in a surge zone and inside the band:</strong> {surgeYes.map((s) => s.name).join(", ")}
        </div>
      )}
    </div>
  );
}
