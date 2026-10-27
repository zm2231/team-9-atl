import { describe, expect, it } from "vitest";
import {
  KM_PER_MI,
  UNIT_STORAGE_KEY,
  formatDistance,
  fromKm,
  loadUnit,
  saveUnit,
  sliderRange,
  toKm,
} from "../../src/lib/units";

function memoryStorage(init: Record<string, string> = {}): Storage {
  const m = new Map(Object.entries(init));
  return {
    get length() {
      return m.size;
    },
    clear: () => m.clear(),
    getItem: (k) => m.get(k) ?? null,
    key: (i) => [...m.keys()][i] ?? null,
    removeItem: (k) => void m.delete(k),
    setItem: (k, v) => void m.set(k, String(v)),
  };
}

const throwing = (): Storage => ({
  ...memoryStorage(),
  getItem: () => {
    throw new Error("blocked");
  },
  setItem: () => {
    throw new Error("quota");
  },
});

describe("units: conversion and formatting (research R2)", () => {
  it("uses the international mile", () => {
    expect(KM_PER_MI).toBe(1.609344);
  });

  it("formats whole numbers in the selected unit", () => {
    expect(formatDistance(80, "mi")).toBe("50 mi");
    expect(formatDistance(80, "km")).toBe("80 km");
    expect(formatDistance(200, "mi")).toBe("124 mi");
  });

  it('shows "<1" for a short distance, never "0"', () => {
    expect(formatDistance(0.3, "mi")).toBe("<1 mi");
    expect(formatDistance(0.4, "km")).toBe("<1 km");
    expect(formatDistance(0, "km")).toBe("0 km");
  });

  it("converts both ways", () => {
    expect(toKm(50, "mi")).toBeCloseTo(80.4672, 4);
    expect(toKm(80, "km")).toBe(80);
    expect(fromKm(80.4672, "mi")).toBeCloseTo(50, 6);
    expect(fromKm(80, "km")).toBe(80);
  });
});

describe("units: reach slider range (research R3)", () => {
  it("keeps every miles position inside 25–200 km", () => {
    const mi = sliderRange("mi");
    expect(mi).toEqual({ min: 16, max: 124, step: 1 });
    expect(toKm(mi.min, "mi")).toBeGreaterThanOrEqual(25);
    expect(toKm(mi.max, "mi")).toBeLessThanOrEqual(200);
  });

  it("is unchanged in kilometres", () => {
    expect(sliderRange("km")).toEqual({ min: 25, max: 200, step: 5 });
  });
});

describe("units: stored preference (contracts/unit-preference-storage.md)", () => {
  it("defaults to miles", () => {
    expect(loadUnit(null)).toBe("mi");
    expect(loadUnit(memoryStorage())).toBe("mi");
    expect(loadUnit(throwing())).toBe("mi");
  });

  it("reads a stored km and ignores anything unexpected", () => {
    expect(loadUnit(memoryStorage({ [UNIT_STORAGE_KEY]: "km" }))).toBe("km");
    expect(loadUnit(memoryStorage({ [UNIT_STORAGE_KEY]: "mi" }))).toBe("mi");
    expect(loadUnit(memoryStorage({ [UNIT_STORAGE_KEY]: "KM" }))).toBe("mi");
    expect(loadUnit(memoryStorage({ [UNIT_STORAGE_KEY]: "miles" }))).toBe("mi");
  });

  it("writes the bare string and reports failure without throwing", () => {
    const s = memoryStorage();
    expect(saveUnit(s, "km")).toBe(true);
    expect(s.getItem("gsr.distanceUnit.v1")).toBe("km");
    expect(saveUnit(null, "km")).toBe(false);
    expect(saveUnit(throwing(), "km")).toBe(false);
  });
});
