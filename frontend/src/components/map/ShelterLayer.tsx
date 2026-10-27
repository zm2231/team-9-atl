import { useMemo } from "react";
import { useStore } from "../../state/store";
import { useScenario } from "../../state/scenario";
import { flagLabel } from "../../lib/flags";
import { useMapGeometry } from "./MapView";
import type { Shelter } from "../../lib/types";

function usageClass(usage: string | null): string {
  const u = (usage ?? "").toUpperCase();
  if (u.includes("EVAC")) return "shelter--evac";
  if (u.includes("POST")) return "shelter--post";
  return "shelter--unknown";
}

export default function ShelterLayer() {
  const { state, dispatch } = useStore();
  const { projection } = useMapGeometry();
  const scenario = useScenario();
  const affected = useMemo(() => new Set(scenario?.affected_shelter_ids ?? []), [scenario]);
  const receiving = useMemo(() => new Set(scenario?.receiving.map((r) => r.shelter_id) ?? []), [scenario]);

  if (state.mapData.status !== "ready" || !state.mapData.data) return null;

  const r = 3.2;
  return (
    <g className="shelters">
      {state.mapData.data.shelters.map((s: Shelter) => {
        const xy = projection([s.lon, s.lat]);
        if (!xy) return null;
        const [x, y] = xy;
        const cls = ["shelter", usageClass(s.usage)];
        const surge = s.in_surge_slosh_area === "YES";
        if (affected.has(s.shelter_id)) cls.push(surge ? "shelter--affected-surge" : "shelter--affected");
        else if (receiving.has(s.shelter_id)) cls.push("shelter--receiving");
        if (state.highlight.shelterIds.has(s.shelter_id)) cls.push("shelter--highlight");
        if (state.selectedShelterId === s.shelter_id) cls.push("shelter--selected");
        return (
          <g key={s.shelter_id} data-shelter-id={s.shelter_id}>
            <circle
              cx={x}
              cy={y}
              r={r}
              className={cls.join(" ")}
              onClick={() => dispatch({ type: "selectShelter", id: s.shelter_id })}
              // A dot sits on top of its county: keep that county's summary showing.
              onPointerEnter={() => s.county_fips && dispatch({ type: "hover", fips: s.county_fips })}
            >
              <title>
                {`${s.name} · capacity ${s.evacuation_capacity ?? "not recorded"} · wheelchair ${flagLabel(s.wheelchair_accessible)}`}
              </title>
            </circle>
            {surge && <circle cx={x} cy={y} r={r + 2.2} className="shelter-surge" />}
            {s.quality_flags.length > 0 && (
              <text x={x + r + 1} y={y - r} className="shelter-warn">
                !
              </text>
            )}
          </g>
        );
      })}
    </g>
  );
}
