// Live vs registry segmentation of an answer, from Gemini grounding metadata (research R8).
import type { AnswerSegment, GroundingMetadata, GroundingSource, LiveCheckReport, LiveCheckStatus } from "./types";

const encoder = new TextEncoder();
const decoder = new TextDecoder();

interface Span {
  start: number; // character offsets into text
  end: number;
  sources: GroundingSource[];
}

/**
 * Gemini reports segment offsets in UTF-8 bytes; JS strings index UTF-16 code units. Convert by
 * decoding the byte prefix. Falls back to locating segment.text if the offsets do not line up.
 */
function toSpan(text: string, bytes: Uint8Array, seg: NonNullable<NonNullable<GroundingMetadata["groundingSupports"]>[number]["segment"]>): { start: number; end: number } | null {
  const startByte = seg.startIndex ?? 0; // null on the first segment: treat as 0 (README)
  const endByte = seg.endIndex;
  if (endByte !== undefined && endByte <= bytes.length && startByte < endByte) {
    const start = decoder.decode(bytes.slice(0, startByte)).length;
    const end = decoder.decode(bytes.slice(0, endByte)).length;
    if (!seg.text || text.slice(start, end) === seg.text) return { start, end };
  }
  if (seg.text) {
    const at = text.indexOf(seg.text);
    if (at >= 0) return { start: at, end: at + seg.text.length };
  }
  return null;
}

/** Gemini sometimes writes inline "[INDEX 1]" citation markers; the sources render as links instead. */
const CITATION_MARKER = /\s*\[INDEX\s+\d+(?:\s*,\s*\d+)*\]/g;

export function segmentAnswer(text: string, gm?: GroundingMetadata): AnswerSegment[] {
  return splitAnswer(text, gm)
    .map((s) => ({ ...s, text: s.text.replace(CITATION_MARKER, "") }))
    .filter((s) => s.text.trim().length > 0);
}

function splitAnswer(text: string, gm?: GroundingMetadata): AnswerSegment[] {
  const supports = gm?.groundingSupports ?? [];
  const chunks = gm?.groundingChunks ?? [];
  if (!supports.length) return text ? [{ text, kind: "registry" }] : [];

  const bytes = encoder.encode(text);
  const spans: Span[] = [];
  for (const s of supports) {
    if (!s.segment) continue;
    const span = toSpan(text, bytes, s.segment);
    if (!span) continue;
    const sources = (s.groundingChunkIndices ?? [])
      .map((i) => chunks[i]?.maps)
      .filter((m): m is NonNullable<typeof m> => !!m?.uri)
      .map((m) => ({ title: m.title ?? m.uri!, uri: m.uri!, placeId: m.placeId }));
    spans.push({ ...span, sources });
  }
  spans.sort((a, b) => a.start - b.start);

  const out: AnswerSegment[] = [];
  let cursor = 0;
  for (const sp of spans) {
    if (sp.start < cursor) continue; // overlapping support; keep the first
    if (sp.start > cursor) out.push({ text: text.slice(cursor, sp.start), kind: "registry" });
    out.push({ text: text.slice(sp.start, sp.end), kind: "live", sources: sp.sources });
    cursor = sp.end;
  }
  if (cursor < text.length) out.push({ text: text.slice(cursor), kind: "registry" });
  return out.filter((s) => s.text.trim().length > 0);
}

/** Collects shelter_id / county_fips values anywhere in a tool result (FR-014, dependency D2). */
export function collectReferences(obj: unknown): { shelterIds: string[]; countyFips: string[] } {
  const shelterIds = new Set<string>();
  const countyFips = new Set<string>();
  const walk = (v: unknown) => {
    if (Array.isArray(v)) v.forEach(walk);
    else if (v && typeof v === "object") {
      for (const [k, val] of Object.entries(v)) {
        if (k === "shelter_id" && (typeof val === "string" || typeof val === "number")) shelterIds.add(String(val));
        else if (k === "county_fips" && typeof val === "string") countyFips.add(val);
        else walk(val);
      }
    }
  };
  walk(obj);
  return { shelterIds: [...shelterIds], countyFips: [...countyFips] };
}

const LIVE_STATUSES: readonly LiveCheckStatus[] = ["exists", "renamed", "closed", "unknown"];

/** Finds record_live_check results ({live_check: {...}}) anywhere in a tool result. */
export function collectLiveChecks(obj: unknown): LiveCheckReport[] {
  const out: LiveCheckReport[] = [];
  const walk = (v: unknown) => {
    if (Array.isArray(v)) v.forEach(walk);
    else if (v && typeof v === "object") {
      for (const [k, val] of Object.entries(v)) {
        if (k === "live_check" && val && typeof val === "object") {
          const lc = val as { shelter_id?: unknown; status?: unknown; place_id?: unknown };
          if (
            (typeof lc.shelter_id === "string" || typeof lc.shelter_id === "number") &&
            LIVE_STATUSES.includes(lc.status as LiveCheckStatus)
          ) {
            out.push({
              shelter_id: String(lc.shelter_id),
              status: lc.status as LiveCheckStatus,
              ...(typeof lc.place_id === "string" ? { place_id: lc.place_id } : {}),
            });
          }
        } else walk(val);
      }
    }
  };
  walk(obj);
  return out;
}
