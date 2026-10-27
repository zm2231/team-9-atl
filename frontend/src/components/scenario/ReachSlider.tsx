import { CUTOFF_MAX_KM, CUTOFF_MIN_KM } from "../../lib/simulation";

/** "Within reach" is one visible, documented setting, not a hidden constant (FR-018b). */
export default function ReachSlider({
  value,
  onChange,
  disabled,
}: {
  value: number;
  onChange: (km: number) => void;
  disabled?: boolean;
}) {
  return (
    <label>
      Within reach: <strong>{value} km</strong> (straight-line){" "}
      <input
        type="range"
        min={CUTOFF_MIN_KM}
        max={CUTOFF_MAX_KM}
        step={5}
        value={value}
        disabled={disabled}
        aria-label="Within reach cutoff in kilometres"
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </label>
  );
}
