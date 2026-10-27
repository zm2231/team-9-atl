import { describe, expect, it } from "vitest";
import { area } from "@turf/turf";
import type { LineString } from "geojson";
import mapData from "../mocks/mapData.fixture.json";
import { countyCentroids, gaCounties } from "../../src/lib/geo";
import {
  affected,
  capacitySummary,
  computeBand,
  receivingList,
  thinTrack,
} from "../../src/lib/simulation";
import type { Category, MapData } from "../../src/lib/types";

const data = mapData as unknown as MapData;
const shelters = data.shelters;

const glynnTrack: LineString = { type: "LineString", coordinates: [[-80.8, 31.0], [-82.0, 31.4]] };
const cobbTrack: LineString = { type: "LineString", coordinates: [[-84.7, 33.8], [-84.4, 34.1]] };
const coastTrack: LineString = { type: "LineString", coordinates: [[-80.9, 32.0], [-81.4, 32.3]] };

function run(track: LineString, category: Category, cutoff: number) {
  const band = computeBand(track, category);
  const hit = affected(band, shelters, gaCounties.features);
  const list = receivingList(shelters, new Set(hit.shelterIds), hit.countyFips, countyCentroids, cutoff);
  return { band, hit, list };
}

describe("receivingList (FR-018a–d)", () => {
  it("SC-005b: never includes a shelter inside the band", () => {
    for (const track of [glynnTrack, cobbTrack, coastTrack]) {
      for (const cat of [1, 2, 3, 4, 5] as Category[]) {
        const { hit, list } = run(track, cat, 200);
        const inside = new Set(hit.shelterIds);
        expect(list.filter((r) => inside.has(r.shelter_id))).toEqual([]);
      }
    }
  });

  it("sorts by capacity (largest first), ties by distance", () => {
    const { list } = run(cobbTrack, 1, 200);
    const caps = list.map((r) => {
      const s = shelters.find((x) => x.shelter_id === r.shelter_id)!;
      return s.quality_flags.includes("suspect_capacity") ? 0 : (s.evacuation_capacity ?? 0);
    });
    expect(caps).toEqual([...caps].sort((a, b) => b - a));
    list.forEach((r, i) => expect(r.rank).toBe(i + 1));
  });

  it("never ranks the suspect Commerce shelter first", () => {
    const { list } = run(cobbTrack, 1, 200);
    expect(list.some((r) => r.shelter_id === "J1")).toBe(true);
    expect(list[0].shelter_id).not.toBe("J1");
    expect(list.find((r) => r.shelter_id === "J1")!.reason).toContain("implausible");
  });

  it("filters by the cutoff at 25, 80 and 200 km", () => {
    const sizes = [25, 80, 200].map((c) => run(glynnTrack, 3, c).list);
    expect(sizes[0].length).toBeLessThanOrEqual(sizes[1].length);
    expect(sizes[1].length).toBeLessThanOrEqual(sizes[2].length);
    for (const [i, c] of [25, 80, 200].entries()) {
      for (const r of sizes[i]) expect(r.distance_km.value!).toBeLessThanOrEqual(c);
    }
  });

  it("labels distances as straight-line simulation values", () => {
    const { list } = run(glynnTrack, 3, 200);
    expect(list[0].distance_km.kind).toBe("simulation");
    expect(list[0].distance_km.source).toContain("straight-line");
  });

  it("returns [] when no Georgia county is affected", () => {
    const sea: LineString = { type: "LineString", coordinates: [[-75.0, 28.0], [-75.5, 28.3]] };
    expect(run(sea, 1, 200).list).toEqual([]);
  });
});

describe("band and affected set", () => {
  it("a click produces a Point track and a circular band", () => {
    const t = thinTrack([[-81.5, 31.2]]);
    expect(t.type).toBe("Point");
    expect(computeBand(t, 1).geometry.type).toBe("Polygon");
  });

  it("thins a dense drag to points at least 5 km apart", () => {
    const pts: [number, number][] = Array.from({ length: 50 }, (_, i) => [-82 + i * 0.01, 31.2]);
    const t = thinTrack(pts) as LineString;
    expect(t.type).toBe("LineString");
    expect(t.coordinates.length).toBeLessThan(pts.length);
  });

  it("only counts Georgia counties when the band crosses into Florida", () => {
    const border: LineString = { type: "LineString", coordinates: [[-82.2, 30.2], [-82.2, 30.9]] };
    const { hit } = run(border, 3, 80);
    expect(hit.countyFips.length).toBeGreaterThan(0);
    expect(hit.countyFips.every((f) => f.startsWith("13"))).toBe(true);
  });

  it("Category 5 band is wider than Category 1", () => {
    expect(area(computeBand(glynnTrack, 5))).toBeGreaterThan(area(computeBand(glynnTrack, 1)));
  });
});

describe("capacitySummary (Constitution VI)", () => {
  it("excludes and names suspect shelters", () => {
    const jackson = shelters.filter((s) => s.county_fips === "13157");
    const cap = capacitySummary(jackson);
    expect(cap.total).toBe(600);
    expect(cap.excluded.map((e) => e.name)).toEqual(["Commerce High School", "Commerce Primary School"]);
    expect(cap.totalInclSuspect).toBe(600 + 270135 + 225112);
  });
});
