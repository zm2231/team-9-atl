import { describe, expect, it } from "vitest";
import { MIN_MAP, MIN_SIDE, SIDE_WIDTH_KEY, clampSideWidth, loadSideWidth, saveSideWidth } from "../../src/lib/sideWidth";

const store = (data = new Map<string, string>()) => ({
  data,
  getItem: (k: string) => data.get(k) ?? null,
  setItem: (k: string, v: string) => void data.set(k, v),
});
const broken = { getItem: () => { throw new Error("x"); }, setItem: () => { throw new Error("x"); } };

describe("side panel width", () => {
  it("clamps between the minimum panel and the minimum map", () => {
    expect(clampSideWidth(720, 1440)).toBe(720);
    expect(clampSideWidth(100, 1440)).toBe(MIN_SIDE);
    expect(clampSideWidth(5000, 1440)).toBe(1440 - MIN_MAP);
    expect(clampSideWidth(500, 600)).toBe(MIN_SIDE);
  });

  it("persists and reloads, ignoring junk and blocked storage", () => {
    const s = store();
    expect(loadSideWidth(s)).toBeNull();
    saveSideWidth(s, 640.4);
    expect(s.data.get(SIDE_WIDTH_KEY)).toBe("640");
    expect(loadSideWidth(s)).toBe(640);
    expect(loadSideWidth(store(new Map([[SIDE_WIDTH_KEY, "abc"]])))).toBeNull();
    expect(loadSideWidth(broken)).toBeNull();
    expect(() => saveSideWidth(broken, 1)).not.toThrow();
  });
});
