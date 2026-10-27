import { flagClass, flagLabel, NOAA_SURGE_SOURCE, surgeNoaaLabel, wheelchairCheckLabel } from "../lib/flags";
import type { Shelter, WheelchairCheck } from "../lib/types";

/** Surge flag plus where it came from: registry, or NOAA surge maps where the registry was blank. */
export function SurgeFlag({ s }: { s: Shelter }) {
  const fromNoaa = s.in_surge_source === "noaa_slosh";
  const reading = surgeNoaaLabel(s);
  return (
    <span title={fromNoaa ? `Registry blank; filled from ${NOAA_SURGE_SOURCE}` : undefined}>
      <span className={flagClass(s.in_surge_slosh_area)}>{flagLabel(s.in_surge_slosh_area)}</span>
      {fromNoaa && <span className="kind kind--noaa">NOAA map</span>}
      {reading && s.surge_noaa?.status !== "dry" && <div className="muted">{reading}</div>}
    </span>
  );
}

/** A Google Maps wheelchair lookup, shown beside the registry flag and never in place of it. */
export function MapsWheelchair({ check }: { check: WheelchairCheck }) {
  const source = check.sources[0];
  const listed = check.status === "listed_accessible" || check.status === "listed_not_accessible";
  return (
    <div className="maps-check" title={check.evidence || check.error || undefined} data-testid="maps-wheelchair">
      <span className={listed ? "kind kind--live" : "kind"}>{wheelchairCheckLabel(check)}</span>
      {listed && <span className="muted"> · unverified</span>}
      {source && (
        <>
          {" "}
          <a href={source.uri} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}>
            <span translate="no">Google Maps</span>
          </a>
        </>
      )}
    </div>
  );
}
