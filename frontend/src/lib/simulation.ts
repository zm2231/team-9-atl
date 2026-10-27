// Illustrative hurricane scenario (research R5, R6). Not a wind or surge model.
import { booleanIntersects, booleanPointInPolygon, buffer, distance, length, lineString, point } from "@turf/turf";
import type { Feature, LineString, MultiPolygon, Point, Polygon } from "geojson";
import { countFlags } from "./flags";
import type { Category, ExcludedShelter, FlagCounts, FlagKey, ReceivingEntry, Shelter } from "./types";
import type { CountyFeature } from "./geo";

/** Band half-width per category, loosely scaled to hurricane-force wind radii. Illustrative only. */
export const HALF_WIDTH_KM: Record<Category, number> = { 1: 30, 2: 45, 3: 60, 4: 80, 5: 100 };
export const CUTOFF_MIN_KM = 25;
export const CUTOFF_MAX_KM = 200;

export type Band = Feature<Polygon | MultiPolygon>;

/** Drag positions → a track. Points closer than minKm are dropped; a click becomes a Point. */
export function thinTrack(lonlats: [number, number][], minKm = 5): LineString | Point {
  if (lonlats.length === 0) throw new Error("A track needs at least one point");
  if (lonlats.length < 2 || length(lineString(lonlats), { units: "kilometers" }) < 1) {
    return { type: "Point", coordinates: lonlats[0] };
  }
  const kept: [number, number][] = [lonlats[0]];
  for (const p of lonlats.slice(1, -1)) {
    if (distance(kept[kept.length - 1], p, { units: "kilometers" }) >= minKm) kept.push(p);
  }
  const last = lonlats[lonlats.length - 1];
  if (distance(kept[kept.length - 1], last, { units: "kilometers" }) > 0) kept.push(last);
  return kept.length < 2 ? { type: "Point", coordinates: kept[0] } : { type: "LineString", coordinates: kept };
}

export function computeBand(track: LineString | Point, category: Category): Band {
  const band = buffer({ type: "Feature", properties: {}, geometry: track }, HALF_WIDTH_KM[category], {
    units: "kilometers",
  });
  if (!band) throw new Error("Could not build the impact band");
  return band as Band;
}

/** Only Georgia counties and shelters are counted, wherever the band reaches. */
export function affected(
  band: Band,
  shelters: Shelter[],
  counties: CountyFeature[],
): { countyFips: string[]; shelterIds: string[] } {
  return {
    countyFips: counties.filter((c) => booleanIntersects(c, band)).map((c) => c.id),
    shelterIds: shelters
      .filter((s) => s.county_fips?.startsWith("13") && booleanPointInPolygon(point([s.lon, s.lat]), band))
      .map((s) => s.shelter_id),
  };
}

const isSuspect = (s: Shelter) => s.quality_flags.includes("suspect_capacity");
/** A data error must never top the list: suspect capacities rank as 0. */
const rankCapacity = (s: Shelter) => (isSuspect(s) ? 0 : (s.evacuation_capacity ?? 0));

function reasonFor(s: Shelter, rank: number, d: number, cutoffKm: number): string {
  const parts: string[] = [];
  if (isSuspect(s)) parts.push("Capacity looks implausible; ranked as 0");
  else if (rank === 1) parts.push(`Largest recorded capacity within ${cutoffKm} km`);
  else if (s.evacuation_capacity === null) parts.push(`Capacity not recorded; ${Math.round(d)} km away`);
  else parts.push(`Recorded capacity ${s.evacuation_capacity.toLocaleString("en-US")}, ${Math.round(d)} km away`);
  parts.push(
    {
      YES: "wheelchair access recorded yes",
      NO: "wheelchair access recorded no",
      UNRECORDED: "wheelchair access not recorded",
    }[s.wheelchair_accessible],
  );
  if (s.in_surge_slosh_area === "YES") parts.push("itself in a recorded surge zone");
  return parts.join("; ");
}

/**
 * Shelters outside the band, within cutoffKm (straight-line) of the nearest affected county's
 * center, sorted by recorded capacity (largest first), ties by distance. Accessibility never
 * affects the order (FR-018a, FR-018c).
 */
export function receivingList(
  shelters: Shelter[],
  affectedShelterIds: Set<string>,
  affectedCountyFips: string[],
  centroids: Map<string, [number, number]>,
  cutoffKm: number,
): ReceivingEntry[] {
  const centers = affectedCountyFips
    .map((f) => [f, centroids.get(f)] as const)
    .filter((x): x is readonly [string, [number, number]] => !!x[1]);
  if (centers.length === 0) return [];

  const candidates = shelters
    .filter((s) => !affectedShelterIds.has(s.shelter_id) && s.county_fips?.startsWith("13"))
    .map((s) => {
      let best = Infinity;
      let nearest = "";
      for (const [fips, c] of centers) {
        const d = distance(c, [s.lon, s.lat], { units: "kilometers" });
        if (d < best) {
          best = d;
          nearest = fips;
        }
      }
      return { s, d: best, nearest };
    })
    .filter((x) => x.d <= cutoffKm)
    .sort((a, b) => rankCapacity(b.s) - rankCapacity(a.s) || a.d - b.d);

  return candidates.map(({ s, d, nearest }, i) => ({
    shelter_id: s.shelter_id,
    rank: i + 1,
    distance_km: { value: d, source: "Simulation (straight-line) · shelters", kind: "simulation" },
    nearest_affected_county: nearest,
    reason: reasonFor(s, i + 1, d, cutoffKm),
  }));
}

export function listFlagCounts(shelters: Shelter[], key: FlagKey): FlagCounts {
  return countFlags(shelters, key);
}

/** Totals for any set of shelters, naming what was left out (Constitution VI). */
export function capacitySummary(shelters: Shelter[]): {
  total: number;
  totalInclSuspect: number;
  excluded: ExcludedShelter[];
} {
  let total = 0;
  let totalInclSuspect = 0;
  const excluded: ExcludedShelter[] = [];
  for (const s of shelters) {
    const cap = s.evacuation_capacity ?? 0;
    totalInclSuspect += cap;
    if (isSuspect(s)) excluded.push({ shelter_id: s.shelter_id, name: s.name });
    else total += cap;
  }
  return { total, totalInclSuspect, excluded };
}
