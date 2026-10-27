import { describe, expect, it } from "vitest";
import type { LineString } from "geojson";
import { initialState, reducer, type Action, type State } from "../../src/state/store";
import { MAX_SCENARIOS, type SavedScenario } from "../../src/lib/history";
import type { ChatExchange } from "../../src/lib/types";

const glynn: LineString = { type: "LineString", coordinates: [[-80.8, 31.0], [-82.0, 31.4]] };
const chatham: LineString = { type: "LineString", coordinates: [[-80.9, 32.0], [-81.4, 32.3]] };
const iso = (min: number) => new Date(Date.UTC(2026, 9, 27, 12, min)).toISOString();

const run = (actions: Action[], from: State = { ...initialState, historyLoaded: true }) => actions.reduce(reducer, from);

const exchange = (q: string): ChatExchange => ({
  id: `x-${q}`,
  question: q,
  context: { county_fips: null, shelter_id: null, scenario: null },
  status: "pending",
  text: "",
  referenced_shelter_ids: [],
  referenced_county_fips: [],
});

describe("history reducer (T012)", () => {
  it("(a) drawing a track creates one current entry with a default name", () => {
    const s = run([{ type: "setTrack", track: glynn, id: "a", now: iso(1) }]);
    expect(s.history).toHaveLength(1);
    expect(s.currentScenarioId).toBe("a");
    expect(s.history[0].name).toMatch(/^Cat 3 · /);
    expect(s.history[0].questions).toEqual([]);
  });

  it("(b) redraw, category and cutoff keep the same single entry", () => {
    const s = run([
      { type: "setTrack", track: glynn, id: "a", now: iso(1) },
      { type: "setTrack", track: chatham, id: "ignored", now: iso(2) },
      { type: "setCategory", category: 4, now: iso(3) },
      { type: "setCutoff", cutoff_km: 120, now: iso(4) },
    ]);
    expect(s.history).toHaveLength(1);
    const h = s.history[0];
    expect(h.id).toBe("a");
    expect(h.track).toEqual(chatham);
    expect(h.category).toBe(4);
    expect(h.cutoff_km).toBe(120);
    expect(h.name).toMatch(/^Cat 4 · /);
    expect(h.updated_at).toBe(iso(4));
  });

  it("(c) asking appends the question text only", () => {
    const s = run([
      { type: "setTrack", track: glynn, id: "a", now: iso(1) },
      { type: "chatStart", exchange: exchange("Which shelters can take a wheelchair?"), now: iso(2) },
    ]);
    expect(s.history[0].questions).toEqual([{ text: "Which shelters can take a wheelchair?", asked_at: iso(2) }]);
  });

  it("does not save questions asked before any track is drawn (FR-005)", () => {
    const s = run([{ type: "chatStart", exchange: exchange("Hello?"), now: iso(1) }]);
    expect(s.history).toEqual([]);
  });

  it("(d) New simulation keeps the entry, clears the scenario, and creates nothing until a draw", () => {
    const s = run([
      { type: "setTrack", track: glynn, id: "a", now: iso(1) },
      { type: "chatStart", exchange: exchange("q1"), now: iso(2) },
      { type: "newSimulation" },
    ]);
    expect(s.history).toHaveLength(1);
    expect(s.currentScenarioId).toBeNull();
    expect(s.scenario).toBeNull();
    expect(s.chat).toEqual([]);
    const s2 = reducer(s, { type: "setTrack", track: chatham, id: "b", now: iso(3) });
    expect(s2.history.map((h) => h.id)).toEqual(["b", "a"]);
    expect(s2.history.find((h) => h.id === "a")!.track).toEqual(glynn);
  });

  it("(e) a full history evicts the least recently opened and says so", () => {
    const full: SavedScenario[] = Array.from({ length: MAX_SCENARIOS }, (_, i) => ({
      id: `s${i}`,
      name: `Old ${i}`,
      nameIsCustom: true,
      track: glynn,
      category: 3,
      cutoff_km: 80,
      questions: [],
      created_at: iso(0),
      updated_at: iso(0),
      last_opened_at: new Date(Date.UTC(2026, 9, 1, 0, i)).toISOString(),
    }));
    const s = run([{ type: "setTrack", track: chatham, id: "new", now: iso(9) }], {
      ...initialState,
      historyLoaded: true,
      history: full,
    });
    expect(s.history).toHaveLength(MAX_SCENARIOS);
    expect(s.history.some((h) => h.id === "s0")).toBe(false);
    expect(s.history.some((h) => h.id === "new")).toBe(true);
    expect(s.notice).toBe("History is full: removed 'Old 0' (least recently opened)");
  });

  it("(f) SC-006: 20 draw → ask → new cycles leave 20 entries", () => {
    let s: State = { ...initialState, historyLoaded: true };
    for (let i = 0; i < 20; i++) {
      s = run(
        [
          { type: "setTrack", track: i % 2 ? glynn : chatham, id: `c${i}`, now: iso(i * 2) },
          { type: "chatStart", exchange: exchange(`q${i}`), now: iso(i * 2 + 1) },
          { type: "newSimulation" },
        ],
        s,
      );
    }
    expect(s.history).toHaveLength(20);
    expect(s.history.every((h) => h.questions.length === 1)).toBe(true);
  });

  it("reopening restores the inputs, marks re-simulated, and appends new questions there (FR-007, FR-008, FR-010)", () => {
    const s = run([
      { type: "setTrack", track: glynn, id: "a", now: iso(1) },
      { type: "setCategory", category: 4, now: iso(2) },
      { type: "setCutoff", cutoff_km: 120, now: iso(3) },
      { type: "chatStart", exchange: exchange("q1"), now: iso(4) },
      { type: "newSimulation" },
      { type: "setTrack", track: chatham, id: "b", now: iso(5) },
      { type: "openScenario", id: "a", now: iso(6) },
      { type: "chatStart", exchange: exchange("q2"), now: iso(7) },
    ]);
    expect(s.scenario).toEqual({ track: glynn, category: 4, cutoff_km: 120 });
    expect(s.currentScenarioId).toBe("a");
    expect(s.resimulatedAt).toBe(iso(6));
    const a = s.history.find((h) => h.id === "a")!;
    expect(a.last_opened_at).toBe(iso(6));
    expect(a.questions.map((q) => q.text)).toEqual(["q1", "q2"]);
    expect(s.history.find((h) => h.id === "b")!.questions).toEqual([]);
  });

  it("rename sticks across category changes; deleting the current entry clears the scenario", () => {
    const s = run([
      { type: "setTrack", track: glynn, id: "a", now: iso(1) },
      { type: "renameScenario", id: "a", name: "  Glynn worst case  ", now: iso(2) },
      { type: "setCategory", category: 5, now: iso(3) },
    ]);
    expect(s.history[0].name).toBe("Glynn worst case");
    expect(s.history[0].nameIsCustom).toBe(true);
    const d = reducer(s, { type: "deleteScenario", id: "a" });
    expect(d.history).toEqual([]);
    expect(d.scenario).toBeNull();
    expect(d.currentScenarioId).toBeNull();
  });
});

describe("agent session on the current scenario", () => {
  it("records the session the current scenario's questions went to", () => {
    const s = run([
      { type: "setTrack", track: glynn, id: "a", now: iso(1) },
      { type: "chatSession", scenarioId: "a", sessionId: "sess-1" },
    ]);
    expect(s.history[0].session_id).toBe("sess-1");
  });

  it("stores a late session on the scenario that asked, not the one now current", () => {
    const s = run([
      { type: "setTrack", track: glynn, id: "a", now: iso(1) },
      { type: "newSimulation" } as Action,
      { type: "setTrack", track: chatham, id: "b", now: iso(2) },
      { type: "chatSession", scenarioId: "a", sessionId: "sess-a" },
    ]);
    expect(s.history.find((h) => h.id === "a")?.session_id).toBe("sess-a");
    expect(s.history.find((h) => h.id === "b")?.session_id).toBeUndefined();
  });
});
