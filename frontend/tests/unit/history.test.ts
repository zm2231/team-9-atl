import { describe, expect, it } from "vitest";
import {
  MAX_QUESTION_CHARS,
  MAX_SCENARIOS,
  STORAGE_KEY,
  abbreviateCounties,
  capHistory,
  defaultName,
  isValidDocument,
  loadHistory,
  relativeTime,
  saveHistory,
  toSavedQuestionText,
  type SavedScenario,
} from "../../src/lib/history";

function fakeStorage(initial: Record<string, string> = {}) {
  const data = new Map(Object.entries(initial));
  return {
    data,
    getItem: (k: string) => data.get(k) ?? null,
    setItem: (k: string, v: string) => void data.set(k, v),
  };
}

const iso = (min: number) => new Date(Date.UTC(2026, 9, 27, 12, min)).toISOString();

function scenario(id: string, openedMin: number, patch: Partial<SavedScenario> = {}): SavedScenario {
  return {
    id,
    name: `Cat 3 · ${id}`,
    nameIsCustom: false,
    track: { type: "LineString", coordinates: [[-80.8, 31.0], [-82.0, 31.4]] },
    category: 3,
    cutoff_km: 80,
    questions: [],
    created_at: iso(0),
    updated_at: iso(openedMin),
    last_opened_at: iso(openedMin),
    ...patch,
  };
}

describe("load/save (T007 a–c)", () => {
  it("round-trips and sorts by last opened, newest first", () => {
    const s = fakeStorage();
    expect(saveHistory(s, [scenario("old", 1), scenario("new", 9)])).toBe(true);
    const loaded = loadHistory(s);
    expect(loaded.available).toBe(true);
    expect(loaded.scenarios.map((x) => x.id)).toEqual(["new", "old"]);
    expect(isValidDocument(JSON.parse(s.data.get(STORAGE_KEY)!))).toBe(true);
  });

  it("returns an empty list, never throws, for missing or unparseable data", () => {
    expect(loadHistory(fakeStorage()).scenarios).toEqual([]);
    const bad = loadHistory(fakeStorage({ [STORAGE_KEY]: "{not json" }));
    expect(bad.scenarios).toEqual([]);
    expect(bad.unreadable).toBe(true);
    expect(loadHistory(fakeStorage({ [STORAGE_KEY]: JSON.stringify({ version: 2, scenarios: [] }) })).unreadable).toBe(true);
  });

  it("drops only the invalid entry, keeping the rest (analysis H1)", () => {
    const tooLong = scenario("bad", 5, { questions: [{ text: "x".repeat(MAX_QUESTION_CHARS + 1), asked_at: iso(5) }] });
    const extraKey = { ...scenario("bad2", 6), answer: "an agent answer" };
    const s = fakeStorage({
      [STORAGE_KEY]: JSON.stringify({ version: 1, scenarios: [scenario("ok", 4), tooLong, extraKey] }),
    });
    const loaded = loadHistory(s);
    expect(loaded.scenarios.map((x) => x.id)).toEqual(["ok"]);
    expect(loaded.dropped).toBe(2);
    expect(loaded.unreadable).toBe(false);
  });

  it("reports unavailable storage instead of throwing", () => {
    const throwing = {
      getItem: () => {
        throw new Error("denied");
      },
      setItem: () => {
        throw new Error("quota");
      },
    };
    expect(loadHistory(throwing).available).toBe(false);
    expect(loadHistory(null).available).toBe(false);
    expect(saveHistory(throwing, [scenario("a", 1)])).toBe(false);
    expect(saveHistory(null, [])).toBe(false);
  });
});

describe("capHistory (T007 d, FR-014)", () => {
  it("evicts the least recently opened, never the current one", () => {
    const list = Array.from({ length: MAX_SCENARIOS + 1 }, (_, i) => scenario(`s${i}`, i + 1));
    // s0 is the oldest; make it current, so the next oldest (s1) must go.
    const { list: out, evicted } = capHistory(list, "s0");
    expect(out).toHaveLength(MAX_SCENARIOS);
    expect(evicted?.id).toBe("s1");
    expect(out.some((s) => s.id === "s0")).toBe(true);
  });

  it("does nothing at or under the cap", () => {
    expect(capHistory([scenario("a", 1)], null).evicted).toBeNull();
  });
});

describe("naming and display helpers (T007 e–f)", () => {
  it("builds default names", () => {
    expect(defaultName(3, ["Glynn", "Wayne", "Ware"])).toBe("Cat 3 · Glynn → Ware");
    expect(defaultName(1, ["Cobb"])).toBe("Cat 1 · Cobb");
    expect(defaultName(5, [])).toBe("Cat 5 · offshore");
  });

  it("abbreviates long county lists", () => {
    expect(abbreviateCounties(["A", "B", "C", "D", "E"])).toBe("A, B, C +2");
    expect(abbreviateCounties(["A", "B"])).toBe("A, B");
  });

  it("formats relative times", () => {
    const now = new Date(iso(30));
    expect(relativeTime(iso(30), now)).toBe("just now");
    expect(relativeTime(iso(25), now)).toBe("5 min ago");
  });

  it("caps saved question text so it can never invalidate an entry", () => {
    expect(toSavedQuestionText("  hi  ")).toBe("hi");
    expect(toSavedQuestionText("y".repeat(MAX_QUESTION_CHARS + 50))).toHaveLength(MAX_QUESTION_CHARS);
  });
});

describe("SC-005: nothing computed and no Maps content is ever stored (T007 g)", () => {
  it("a fully used history serializes to inputs only", () => {
    const s = fakeStorage();
    const used = scenario("a", 3, {
      name: "Glynn worst case",
      nameIsCustom: true,
      questions: [{ text: "Which of these receiving shelters can actually take a wheelchair?", asked_at: iso(3) }],
    });
    saveHistory(s, [used]);
    const raw = s.data.get(STORAGE_KEY)!;
    // Keys that would mean results or Maps content were stored. The user's own question text may
    // mention "receiving shelters", so check keys, not words.
    for (const key of [
      "groundingMetadata", "maps", "uri", "title", "receiving", "affected_shelter_ids", "band",
      "evacuation_capacity", "answer", "text_answer", "sources",
    ]) {
      expect(raw).not.toContain(`"${key}":`);
    }
    expect(raw).not.toContain("Google Maps");
    expect(isValidDocument(JSON.parse(raw))).toBe(true);
  });
});
