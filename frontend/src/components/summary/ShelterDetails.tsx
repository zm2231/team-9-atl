import { flagClass, flagLabel, formatNumber, NOAA_SURGE_SOURCE } from "../../lib/flags";
import type { Flag } from "../../lib/types";
import { useEffect } from "react";
import { useWheelchairChecker } from "../../lib/useWheelchairChecker";
import { useStore } from "../../state/store";
import { MapsWheelchair, SurgeFlag } from "../FlagNotes";

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
  const { checkOnce, checking } = useWheelchairChecker();
  const s = state.selectedShelterId ? shelterById.get(state.selectedShelterId) : undefined;
  const needsCheck = s?.wheelchair_accessible === "UNRECORDED";
  const selectedId = s?.shelter_id;
  useEffect(() => {
    if (needsCheck && selectedId) checkOnce([selectedId]);
  }, [needsCheck, selectedId]);
  if (!s) return null;
  const live = state.liveChecks.get(s.shelter_id);
  const wheelchairCheck = state.wheelchairChecks.get(s.shelter_id);
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
      {needsCheck && (wheelchairCheck || checking) && (
        <div className="row">
          <span className="row__label">Google Maps says</span>
          {wheelchairCheck ? <MapsWheelchair check={wheelchairCheck} /> : <span className="muted">Checking…</span>}
        </div>
      )}
      <FlagRow label="Generator on site" flag={s.generator_onsite} />
      <FlagRow label="Medical-needs designation" flag={s.is_medical} />
      <div className="row">
        <span className="row__label">In a surge zone</span>
        <SurgeFlag s={s} />
      </div>
      {s.quality_flags.includes("suspect_capacity") && (
        <div className="note">Capacity looks implausible; FEMA's value shown unedited and left out of totals.</div>
      )}
      {s.quality_flags.includes("location_disagrees") && (
        <div className="note">Coordinates disagree with the recorded state/county; shown under its recorded county.</div>
      )}
      {s.quality_flags.includes("surge_disagrees") && (
        <div className="note">The registry surge flag disagrees with the NOAA surge maps; the registry value is shown.</div>
      )}
      {s.surge_noaa && (
        <div className="small muted">
          <span className="kind kind--noaa">NOAA map</span> {NOAA_SURGE_SOURCE}, worst case within about 100 m.
        </div>
      )}
      {live && (
        <div className={live.status === "renamed" || live.status === "closed" ? "note" : "small"} data-testid="live-check">
          <span className="kind kind--live">Live check</span>{" "}
          {live.status === "renamed" || live.status === "closed" ? (
            <>
              Live check: {live.status} per <span translate="no">Google Maps</span> at{" "}
              {new Date(live.checked_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} — registry
              record shown unedited
            </>
          ) : (
            <>
              {live.status === "exists" ? "Still there" : "Not confirmed"} per <span translate="no">Google Maps</span>{" "}
              at {new Date(live.checked_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
            </>
          )}
        </div>
      )}
      <div className="small muted">
        <span className="kind">Registry</span> Registry record (FEMA National Shelter System · shelters)
      </div>
    </div>
  );
}
