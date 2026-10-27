import { memo, useMemo } from "react";
import { gaCounties, type CountyFeature } from "../../lib/geo";
import { useStore } from "../../state/store";
import { useScenario } from "../../state/scenario";
import { useMapGeometry } from "./MapView";

const CountyPath = memo(function CountyPath({
  feature,
  d,
  className,
  onEnter,
  onLeave,
  onSelect,
}: {
  feature: CountyFeature;
  d: string;
  className: string;
  onEnter: (fips: string) => void;
  onLeave: () => void;
  onSelect: (fips: string) => void;
}) {
  return (
    <path
      d={d}
      className={className}
      data-fips={feature.id}
      tabIndex={0}
      aria-label={`${feature.properties.name} County`}
      onPointerEnter={() => onEnter(feature.id)}
      onPointerLeave={onLeave}
      onFocus={() => onEnter(feature.id)}
      onBlur={onLeave}
      onClick={() => onSelect(feature.id)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") onSelect(feature.id);
      }}
    />
  );
});

/** County outlines render immediately, before and without the agent's data (FR-008b). */
export default function CountyLayer() {
  const { state, dispatch } = useStore();
  const { path } = useMapGeometry();
  const scenario = useScenario();
  const paths = useMemo(() => gaCounties.features.map((f) => [f, path(f) ?? ""] as const), [path]);
  const affected = useMemo(() => new Set(scenario?.affected_county_fips ?? []), [scenario]);

  // Hover does no network work (FR-008a): it only updates local state.
  const onEnter = (fips: string) => dispatch({ type: "hover", fips });
  const onLeave = () => dispatch({ type: "hover", fips: null });
  const onSelect = (fips: string) =>
    dispatch({ type: "selectCounty", fips: state.selectedFips === fips ? null : fips });

  return (
    <g className="counties">
      {paths.map(([f, d]) => {
        const cls = ["county"];
        if (affected.has(f.id)) cls.push("county--affected");
        if (state.highlight.countyFips.has(f.id)) cls.push("county--highlight");
        if (state.selectedFips === f.id) cls.push("county--selected");
        if (state.hoverFips === f.id) cls.push("county--hover");
        return (
          <CountyPath
            key={f.id}
            feature={f}
            d={d}
            className={cls.join(" ")}
            onEnter={onEnter}
            onLeave={onLeave}
            onSelect={onSelect}
          />
        );
      })}
    </g>
  );
}
