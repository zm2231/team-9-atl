// Distance units (feature 003). Pure: no React, no window access.
// Kilometres stay canonical in state, history and the agent context; this module converts only
// for display (research R1–R4).
import { CUTOFF_MAX_KM, CUTOFF_MIN_KM } from "./simulation";

export type DistanceUnit = "mi" | "km";

export const UNIT_STORAGE_KEY = "gsr.distanceUnit.v1";
export const DEFAULT_UNIT: DistanceUnit = "mi";
export const KM_PER_MI = 1.609344;

export const fromKm = (km: number, unit: DistanceUnit) => (unit === "mi" ? km / KM_PER_MI : km);
export const toKm = (value: number, unit: DistanceUnit) => (unit === "mi" ? value * KM_PER_MI : value);

export const unitLabel = (unit: DistanceUnit) => unit;
export const unitName = (unit: DistanceUnit) => (unit === "mi" ? "miles" : "kilometres");

/** A whole number in the selected unit; a short but nonzero distance reads "<1", never "0". */
export function formatDistance(km: number, unit: DistanceUnit): string {
  const v = fromKm(km, unit);
  const n = Math.round(v);
  return `${n === 0 && v > 0 ? "<1" : n} ${unit}`;
}

/** Every miles position lies inside the documented 25–200 km reach (research R3). */
export function sliderRange(unit: DistanceUnit): { min: number; max: number; step: number } {
  return unit === "mi"
    ? { min: Math.ceil(CUTOFF_MIN_KM / KM_PER_MI), max: Math.floor(CUTOFF_MAX_KM / KM_PER_MI), step: 1 }
    : { min: CUTOFF_MIN_KM, max: CUTOFF_MAX_KM, step: 5 };
}

/** Anything missing, unreadable or unexpected falls back to miles (contracts/unit-preference-storage.md). */
export function loadUnit(storage: Storage | null): DistanceUnit {
  try {
    const v = storage?.getItem(UNIT_STORAGE_KEY);
    return v === "mi" || v === "km" ? v : DEFAULT_UNIT;
  } catch {
    return DEFAULT_UNIT;
  }
}

export function saveUnit(storage: Storage | null, unit: DistanceUnit): boolean {
  if (!storage) return false;
  try {
    storage.setItem(UNIT_STORAGE_KEY, unit);
    return true;
  } catch {
    return false;
  }
}
