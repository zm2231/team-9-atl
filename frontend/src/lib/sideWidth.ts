export const SIDE_WIDTH_KEY = "gsr.sideWidth.v1";
export const MIN_SIDE = 360;
export const MIN_MAP = 380;
export const SIDE_STEP = 32;

export function clampSideWidth(width: number, viewport: number): number {
  const max = Math.max(MIN_SIDE, viewport - MIN_MAP);
  return Math.round(Math.min(max, Math.max(MIN_SIDE, width)));
}

export function loadSideWidth(storage: Pick<Storage, "getItem"> | null): number | null {
  try {
    const n = Number(storage?.getItem(SIDE_WIDTH_KEY) ?? NaN);
    return Number.isFinite(n) && n > 0 ? n : null;
  } catch {
    return null;
  }
}

export function saveSideWidth(storage: Pick<Storage, "setItem"> | null, width: number): void {
  try {
    storage?.setItem(SIDE_WIDTH_KEY, String(Math.round(width)));
  } catch {
    return;
  }
}
