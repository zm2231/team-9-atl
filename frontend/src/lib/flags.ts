import type { ExcludedShelter, Flag, FlagCounts, FlagKey, Shelter, SourcedValue } from "./types";

const LABELS: Record<Flag, string> = { YES: "Yes", NO: "No", UNRECORDED: "Not recorded" };

export function flagLabel(f: Flag): string {
  return LABELS[f];
}

/** UNRECORDED has its own hatched neutral style; it never borrows the "No" color. */
export function flagClass(f: Flag): string {
  return { YES: "flag flag--yes", NO: "flag flag--no", UNRECORDED: "flag flag--unrecorded" }[f];
}

export function countFlags(shelters: Shelter[], key: FlagKey): FlagCounts {
  const counts: FlagCounts = { yes: 0, no: 0, unrecorded: 0 };
  for (const s of shelters) {
    const f = s[key];
    if (f === "YES") counts.yes++;
    else if (f === "NO") counts.no++;
    else counts.unrecorded++;
  }
  return counts;
}

/** Always all three counts, even when some are zero (Constitution I). */
export function flagCountsLine(c: FlagCounts): string {
  return `${c.yes} yes · ${c.no} no · ${c.unrecorded} not recorded`;
}

/** Names every shelter left out of a total, and how many (Constitution VI). */
export function exclusionNote(excluded: Pick<ExcludedShelter, "name">[]): string {
  if (excluded.length === 0) return "";
  const noun = excluded.length === 1 ? "shelter" : "shelters";
  return `Excludes ${excluded.length} ${noun} with suspect capacity: ${excluded.map((e) => e.name).join(", ")}`;
}

/** Dataset and table, plus coverage when an aggregate has gaps (Constitution III). */
export function sourceLabel(v: SourcedValue): string {
  return v.coverage ? `${v.source} · ${v.coverage}` : v.source;
}

const KIND_LABELS: Record<SourcedValue["kind"], string> = {
  registry: "Registry",
  survey: "Survey",
  live: "Live check",
  simulation: "Simulation",
};

export function kindLabel(kind: SourcedValue["kind"]): string {
  return KIND_LABELS[kind];
}

export function formatNumber(v: number | null, opts: { percent?: boolean } = {}): string {
  if (v === null || Number.isNaN(v)) return "no data";
  if (opts.percent) return `${(v * 100).toFixed(1)}%`;
  return Math.round(v).toLocaleString("en-US");
}
