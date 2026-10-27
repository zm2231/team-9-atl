import { useRef } from "react";
import type { DistanceUnit } from "../../lib/units";
import { useStore } from "../../state/store";

const OPTIONS: { unit: DistanceUnit; name: string }[] = [
  { unit: "mi", name: "Miles" },
  { unit: "km", name: "Kilometres" },
];

/** Display unit for every app-computed distance; never disabled (contracts/ui-controls.md). */
export default function UnitToggle() {
  const { state, dispatch } = useStore();
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  const pick = (i: number) => {
    const o = OPTIONS[(i + OPTIONS.length) % OPTIONS.length];
    dispatch({ type: "setUnit", unit: o.unit });
    refs.current[OPTIONS.indexOf(o)]?.focus();
  };

  return (
    <span className="seg" role="radiogroup" aria-label="Distance unit">
      {OPTIONS.map((o, i) => {
        const checked = state.unit === o.unit;
        return (
          <button
            key={o.unit}
            ref={(el) => {
              refs.current[i] = el;
            }}
            type="button"
            role="radio"
            aria-checked={checked}
            aria-label={o.name}
            tabIndex={checked ? 0 : -1}
            onClick={() => dispatch({ type: "setUnit", unit: o.unit })}
            onKeyDown={(e) => {
              if (e.key === "ArrowRight" || e.key === "ArrowDown") pick(i + 1);
              else if (e.key === "ArrowLeft" || e.key === "ArrowUp") pick(i - 1);
              else return;
              e.preventDefault();
            }}
          >
            {o.unit}
          </button>
        );
      })}
    </span>
  );
}
