import { flagClass, flagLabel } from "../../lib/flags";
import type { Flag } from "../../lib/types";

const dot = (cls: string, extra?: React.ReactNode) => (
  <svg width="12" height="12" aria-hidden="true">
    <circle cx="6" cy="6" r="3.5" className={`shelter ${cls}`} />
    {extra}
  </svg>
);

/** Explains every color, marker and flag on screen, including "Not recorded" (FR-009). */
export default function Legend() {
  return (
    <div className="legend" aria-label="Legend">
      <span className="legend__item">{dot("shelter--evac")} Before landfall (EVAC)</span>
      <span className="legend__item">{dot("shelter--post")} After impact (POST)</span>
      <span className="legend__item">{dot("shelter--unknown")} Use not recorded</span>
      <span className="legend__item">
        {dot("shelter--unknown", <circle cx="6" cy="6" r="5.7" className="shelter-surge" />)} Recorded in surge zone
      </span>
      <span className="legend__item">
        <svg width="12" height="12" aria-hidden="true">
          <text x="3" y="10" className="shelter-warn">!</text>
        </svg>
        Data problem (suspect capacity / location)
      </span>
      <span className="legend__item">{dot("shelter--unknown shelter--affected")} Inside simulated band</span>
      <span className="legend__item">{dot("shelter--unknown shelter--receiving")} Receiving shelter</span>
      <span className="legend__item">
        <svg width="14" height="10" aria-hidden="true">
          <rect width="14" height="10" style={{ fill: "var(--county-hover)" }} />
        </svg>
        Hovered county
      </span>
      {(["YES", "NO", "UNRECORDED"] as Flag[]).map((f) => (
        <span key={f} className="legend__item">
          <span className={flagClass(f)}>{flagLabel(f)}</span>
        </span>
      ))}
      <span className="legend__item">
        <span className="kind">Registry</span> FEMA record
        <span className="kind">Survey</span> census estimate
        <span className="kind kind--live">Live check</span> Google Maps now
        <span className="kind kind--simulation">Simulation</span> illustrative
      </span>
    </div>
  );
}
