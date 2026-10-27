// Browser-local scenario history (feature 002). Pure: no React, no window access.
// Stores the user's inputs only; every result is re-simulated on reopen (FR-002–FR-004).
import type { LineString, Point } from "geojson";
import type { Category } from "./types";

export const STORAGE_KEY = "gsr.scenarioHistory.v1";
export const MAX_SCENARIOS = 50;
export const MAX_QUESTIONS = 100;
export const MAX_QUESTION_CHARS = 2000;
export const MAX_NAME_CHARS = 80;

export interface SavedQuestion {
  text: string;
  asked_at: string;
}

export interface SavedScenario {
  id: string;
  name: string;
  nameIsCustom: boolean;
  track: LineString | Point;
  category: Category;
  cutoff_km: number;
  questions: SavedQuestion[];
  created_at: string;
  updated_at: string;
  last_opened_at: string;
}

const SCENARIO_KEYS = new Set([
  "id", "name", "nameIsCustom", "track", "category", "cutoff_km", "questions",
  "created_at", "updated_at", "last_opened_at",
]);

const isObj = (x: unknown): x is Record<string, unknown> => !!x && typeof x === "object" && !Array.isArray(x);
const onlyKeys = (o: Record<string, unknown>, keys: Set<string>) => Object.keys(o).every((k) => keys.has(k));
const isIso = (x: unknown): x is string => typeof x === "string" && !Number.isNaN(Date.parse(x));
const isPos = (p: unknown) =>
  Array.isArray(p) && p.length === 2 && typeof p[0] === "number" && typeof p[1] === "number" &&
  Math.abs(p[0]) <= 180 && Math.abs(p[1]) <= 90;

function isTrack(t: unknown): t is LineString | Point {
  if (!isObj(t) || !onlyKeys(t, new Set(["type", "coordinates"]))) return false;
  if (t.type === "Point") return isPos(t.coordinates);
  return (
    t.type === "LineString" && Array.isArray(t.coordinates) &&
    t.coordinates.length >= 2 && t.coordinates.length <= 2000 && t.coordinates.every(isPos)
  );
}

function isQuestion(q: unknown): q is SavedQuestion {
  return (
    isObj(q) && onlyKeys(q, new Set(["text", "asked_at"])) && typeof q.text === "string" &&
    q.text.length >= 1 && q.text.length <= MAX_QUESTION_CHARS && isIso(q.asked_at)
  );
}

/** One scenario, mirroring contracts/history-storage.schema.json (no unknown keys anywhere). */
export function isValidScenario(s: unknown): s is SavedScenario {
  return (
    isObj(s) && onlyKeys(s, SCENARIO_KEYS) &&
    typeof s.id === "string" && s.id.length > 0 &&
    typeof s.name === "string" && s.name.length >= 1 && s.name.length <= MAX_NAME_CHARS &&
    typeof s.nameIsCustom === "boolean" && isTrack(s.track) &&
    [1, 2, 3, 4, 5].includes(s.category as number) &&
    typeof s.cutoff_km === "number" && s.cutoff_km >= 25 && s.cutoff_km <= 200 &&
    Array.isArray(s.questions) && s.questions.length <= MAX_QUESTIONS && s.questions.every(isQuestion) &&
    isIso(s.created_at) && isIso(s.updated_at) && isIso(s.last_opened_at)
  );
}

/** Whole-document check, used by tests to prove what is written matches the contract. */
export function isValidDocument(x: unknown): x is { version: 1; scenarios: SavedScenario[] } {
  return (
    isObj(x) && onlyKeys(x, new Set(["version", "scenarios"])) && x.version === 1 &&
    Array.isArray(x.scenarios) && x.scenarios.length <= MAX_SCENARIOS && x.scenarios.every(isValidScenario)
  );
}

const byLastOpened = (a: SavedScenario, b: SavedScenario) => b.last_opened_at.localeCompare(a.last_opened_at);

export interface LoadResult {
  scenarios: SavedScenario[];
  available: boolean;
  /** Entries present in storage but invalid, and dropped. */
  dropped: number;
  /** The stored value could not be parsed at all; callers must not overwrite it blindly. */
  unreadable: boolean;
}

/**
 * Validates per entry: one bad scenario is dropped, never the whole history (analysis H1).
 * Never throws.
 */
export function loadHistory(storage: Pick<Storage, "getItem"> | null): LoadResult {
  if (!storage) return { scenarios: [], available: false, dropped: 0, unreadable: false };
  let raw: string | null;
  try {
    raw = storage.getItem(STORAGE_KEY);
  } catch {
    return { scenarios: [], available: false, dropped: 0, unreadable: false };
  }
  if (raw === null) return { scenarios: [], available: true, dropped: 0, unreadable: false };
  let doc: unknown;
  try {
    doc = JSON.parse(raw);
  } catch {
    return { scenarios: [], available: true, dropped: 0, unreadable: true };
  }
  if (!isObj(doc) || doc.version !== 1 || !Array.isArray(doc.scenarios)) {
    return { scenarios: [], available: true, dropped: 0, unreadable: true };
  }
  const valid = doc.scenarios.filter(isValidScenario);
  return {
    scenarios: valid.sort(byLastOpened).slice(0, MAX_SCENARIOS),
    available: true,
    dropped: doc.scenarios.length - valid.length,
    unreadable: false,
  };
}

/** Writes the whole document. Returns false if storage is unavailable or the write throws. */
export function saveHistory(storage: Pick<Storage, "setItem"> | null, scenarios: SavedScenario[]): boolean {
  if (!storage) return false;
  try {
    storage.setItem(STORAGE_KEY, JSON.stringify({ version: 1, scenarios }));
    return true;
  } catch {
    return false;
  }
}

/** Over the cap, evicts the least recently opened scenario that is not current (FR-014). */
export function capHistory(
  list: SavedScenario[],
  currentId: string | null,
): { list: SavedScenario[]; evicted: SavedScenario | null } {
  let out = list;
  let evicted: SavedScenario | null = null;
  while (out.length > MAX_SCENARIOS) {
    const candidates = out.filter((s) => s.id !== currentId);
    const oldest = candidates.reduce((a, b) => (a.last_opened_at <= b.last_opened_at ? a : b));
    evicted = oldest;
    out = out.filter((s) => s.id !== oldest.id);
  }
  return { list: out, evicted };
}

/** "Cat N · First → Last", "Cat N · Only" or "Cat N · offshore" (FR-012). */
export function defaultName(category: Category, countyNames: string[]): string {
  if (countyNames.length === 0) return `Cat ${category} · offshore`;
  if (countyNames.length === 1) return `Cat ${category} · ${countyNames[0]}`;
  return `Cat ${category} · ${countyNames[0]} → ${countyNames[countyNames.length - 1]}`;
}

export function abbreviateCounties(names: string[]): string {
  return names.length <= 3 ? names.join(", ") : `${names.slice(0, 3).join(", ")} +${names.length - 3}`;
}

export function relativeTime(iso: string, now: Date): string {
  const s = Math.max(0, (now.getTime() - Date.parse(iso)) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86_400) return `${Math.floor(s / 3600)} h ago`;
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

/** Question text as saved: trimmed and capped so one long question can never invalidate an entry. */
export function toSavedQuestionText(text: string): string {
  return text.trim().slice(0, MAX_QUESTION_CHARS);
}
