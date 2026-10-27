import { exclusionNote, flagCountsLine, formatNumber, kindLabel, sourceLabel } from "../../lib/flags";
import type { County, SourcedValue } from "../../lib/types";
import { useStore } from "../../state/store";

function Kind({ v }: { v: SourcedValue }) {
  return <span className={`kind kind--${v.kind}`}>{kindLabel(v.kind)}</span>;
}

function Figure({ label, v, percent }: { label: string; v: SourcedValue; percent?: boolean }) {
  return (
    <div>
      <div className="row">
        <span className="row__label">{label}</span>
        <span>
          {formatNumber(v.value, { percent })}
          <Kind v={v} />
        </span>
      </div>
      <div className="small muted">{sourceLabel(v)}</div>
    </div>
  );
}

export function CountySummaryView({ county }: { county: County }) {
  const excluded = exclusionNote(county.capacity_excluded);
  return (
    <div className="card" data-testid="county-summary">
      <h2>{county.name} County</h2>
      {county.shelter_count === 0 ? (
        <p>No shelters on file.</p>
      ) : (
        <>
          <div className="row">
            <span className="row__label">Shelters on file</span>
            <span>{county.shelter_count}</span>
          </div>
          <div className="row">
            <span className="row__label">Recorded evacuation capacity</span>
            <span>
              {formatNumber(county.capacity_total.value)}
              <Kind v={county.capacity_total} />
            </span>
          </div>
          {excluded && (
            <div className="note" data-testid="exclusion-note">
              {excluded}. Including them: {formatNumber(county.capacity_total_incl_suspect.value)}.
            </div>
          )}
          <div className="small muted">{sourceLabel(county.capacity_total)}</div>
          <h3>Recorded flags (yes · no · not recorded)</h3>
          <div className="row">
            <span className="row__label">Wheelchair access</span>
            <span>{flagCountsLine(county.wheelchair)}</span>
          </div>
          <div className="row">
            <span className="row__label">Generator on site</span>
            <span>{flagCountsLine(county.generator)}</span>
          </div>
          <div className="row">
            <span className="row__label">Medical-needs designation</span>
            <span>{flagCountsLine(county.medical)}</span>
          </div>
          <div className="row">
            <span className="row__label">In a surge zone</span>
            <span>{flagCountsLine(county.in_surge)}</span>
          </div>
        </>
      )}
      <h3>Who may struggle to leave</h3>
      <Figure label="Households with no vehicle" v={county.households_no_vehicle} />
      <Figure label="Residents aged 65+" v={county.share_65_plus} percent />
      <Figure label="Residents with a disability" v={county.share_disability} percent />
    </div>
  );
}

/** The hovered county, falling back to the selected one (FR-003, FR-003a, FR-007). */
export default function CountySummary() {
  const { state, countyByFips } = useStore();
  const fips = state.hoverFips ?? state.selectedFips;
  const county = fips ? countyByFips.get(fips) : undefined;
  return (
    <div aria-live="polite">
      {county ? (
        <CountySummaryView county={county} />
      ) : (
        <div className="card muted">
          {state.mapData.status === "ready"
            ? "Hover over or select a county to see what is on file."
            : "County figures appear once shelter data has loaded."}
        </div>
      )}
    </div>
  );
}
