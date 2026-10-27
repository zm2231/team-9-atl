import { flagClass, flagLabel, formatNumber } from "../../lib/flags";
import type { Flag } from "../../lib/types";
import { useStore } from "../../state/store";

function FlagRow({ label, flag }: { label: string; flag: Flag }) {
  return (
    <div className="row">
      <span className="row__label">{label}</span>
      <span className={flagClass(flag)}>{flagLabel(flag)}</span>
    </div>
  );
}

/** One registry record, shown unedited (FR-004, FR-005, FR-008). */
export default function ShelterDetails() {
  const { state, dispatch, shelterById } = useStore();
  const s = state.selectedShelterId ? shelterById.get(state.selectedShelterId) : undefined;
  if (!s) return null;
  const live = state.liveChecks.get(s.shelter_id);
  return (
    <div className="card" data-testid="shelter-details">
      <div className="row">
        <h2>{s.name}</h2>
        <button type="button" className="btn" onClick={() => dispatch({ type: "selectShelter", id: null })}>
          Close
        </button>
      </div>
      <div className="muted">{s.address || "Address not recorded"}</div>
      <div className="muted">{s.county_name} County</div>
      <div className="row">
        <span className="row__label">Evacuation capacity</span>
        <span>{s.evacuation_capacity === null ? "Not recorded" : formatNumber(s.evacuation_capacity)}</span>
      </div>
      <div className="row">
        <span className="row__label">Post-impact capacity</span>
        <span>{s.post_impact_capacity == null ? "Not recorded" : formatNumber(s.post_impact_capacity)}</span>
      </div>
      <div className="row">
        <span className="row__label">Use</span>
        <span>{s.usage ?? "Not recorded"}</span>
      </div>
      <FlagRow label="Wheelchair access" flag={s.wheelchair_accessible} />
      <FlagRow label="Generator on site" flag={s.generator_onsite} />
      <FlagRow label="Medical-needs designation" flag={s.is_medical} />
      <FlagRow label="In a surge zone" flag={s.in_surge_slosh_area} />
      {s.quality_flags.includes("suspect_capacity") && (
        <div className="note">Capacity looks implausible; FEMA's value shown unedited and left out of totals.</div>
      )}
      {s.quality_flags.includes("location_disagrees") && (
        <div className="note">Coordinates disagree with the recorded state/county; shown under its recorded county.</div>
      )}
      {live && (
        <div className="small">
          <span className="kind kind--live">Live check</span> Checked against{" "}
          <span translate="no">Google Maps</span> at {new Date(live.checked_at).toLocaleTimeString()}
        </div>
      )}
      <div className="small muted">
        <span className="kind">Registry</span> Registry record (FEMA National Shelter System · shelters)
      </div>
    </div>
  );
}
