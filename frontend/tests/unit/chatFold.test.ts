import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { parseSseChunk, type AgentEvent } from "../../src/lib/agentClient";
import { emptyFold, foldEvent } from "../../src/lib/chatFold";
import { chatEvents } from "../mocks/handlers";

const fold = (events: AgentEvent[]) => events.reduce(foldEvent, emptyFold);

describe("foldEvent (T070)", () => {
  it("assembles partial deltas, then takes the final text once", () => {
    const final = fold(chatEvents as AgentEvent[]);
    const full = (chatEvents[chatEvents.length - 1].content.parts[0] as { text: string }).text;
    expect(final.text).toBe(full);
  });

  it("collects references and live checks from tool results", () => {
    const final = fold(chatEvents as AgentEvent[]);
    expect(final.shelterIds.sort()).toEqual(["M1", "W1"]);
    expect(final.countyFips).toEqual(expect.arrayContaining(["13021", "13299"]));
    expect(final.liveChecks).toEqual([{ shelter_id: "M1", status: "exists", place_id: "place-macon" }]);
    expect(final.grounding?.groundingChunks?.length).toBe(1);
  });

  it("ignores text on the user's own echoed event", () => {
    const out = fold([{ author: "user", content: { parts: [{ text: "my question" }] } }]);
    expect(out.text).toBe("");
  });
});

// Real agent turns captured with agent/scripts/capture_sse.py (T069), when present.
const RECORDED = join(__dirname, "../mocks/recorded");
let recorded: string[] = [];
try {
  recorded = readdirSync(RECORDED).filter((f) => f.endsWith(".sse"));
} catch {
  recorded = [];
}

describe.skipIf(recorded.length === 0)("recorded agent turns", () => {
  for (const file of recorded) {
    it(`${file}: text is not duplicated and stream parses`, () => {
      const { events } = parseSseChunk(readFileSync(join(RECORDED, file), "utf8") + "\n\n");
      expect(events.some((e) => e.error)).toBe(false);
      const out = fold(events);
      expect(out.text.length).toBeGreaterThan(0);
      const half = out.text.slice(0, Math.floor(out.text.length / 2));
      expect(out.text.length > 40 && out.text === half + half).toBe(false);
    });
  }
});

describe("foldEvent tool trace and report", () => {
  it("records each tool once and keeps the latest report", () => {
    const report = { report_version: 1, scope: "county", subject: {}, season: null, sections: {}, source: "s" };
    const out = fold([
      { content: { parts: [{ functionCall: { name: "county_plan" } }] } },
      { content: { parts: [{ functionResponse: { name: "county_plan", response: { report } } }] } },
      { content: { parts: [{ functionCall: { name: "check_shelter_google_maps" } }] } },
    ]);
    expect(out.tools).toEqual(["county_plan", "check_shelter_google_maps"]);
    expect(out.report?.scope).toBe("county");
  });
});
