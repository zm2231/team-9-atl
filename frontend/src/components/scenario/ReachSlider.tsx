import { formatDistance, fromKm, sliderRange, toKm, unitName, type DistanceUnit } from "../../lib/units";

/**
 * "Within reach" is one visible, documented setting, not a hidden constant (FR-018b). The value is
 * always kilometres; the scale and label follow the display unit (feature 003, research R3).
 */
export default function ReachSlider({
  value,
  unit,
  onChange,
  disabled,
}: {
  value: number;
  unit: DistanceUnit;
  onChange: (km: number) => void;
  disabled?: boolean;
}) {
  const { min, max, step } = sliderRange(unit);
  return (
    <label>
      Within reach: <strong>{formatDistance(value, unit)}</strong> (straight-line){" "}
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={Math.round(fromKm(value, unit) / step) * step}
        disabled={disabled}
        aria-label={`Within reach cutoff in ${unitName(unit)}`}
        onChange={(e) => onChange(toKm(Number(e.target.value), unit))}
      />
    </label>
  );
}
