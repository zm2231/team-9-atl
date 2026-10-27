import { describe, expect, it } from "vitest";
import { collectReferences, segmentAnswer } from "../../src/lib/grounding";

const chunks = [
  { maps: { uri: "https://maps.example/a", title: "A Place", placeId: "pa" } },
  { maps: { uri: "https://maps.example/b", title: "B Place", placeId: "pb" } },
];

describe("segmentAnswer", () => {
  it("treats a null startIndex as 0", () => {
    const text = "Open now. Registry says yes.";
    const segs = segmentAnswer(text, {
      groundingChunks: chunks,
      groundingSupports: [{ segment: { startIndex: null, endIndex: 9 }, groundingChunkIndices: [0] }],
    });
    expect(segs[0]).toMatchObject({ kind: "live", text: "Open now." });
    expect(segs[0].sources?.[0].title).toBe("A Place");
    expect(segs[1].kind).toBe("registry");
  });

  it("orders live / registry / live and maps sources to the right segment", () => {
    const text = "First live. Middle record. Last live.";
    const segs = segmentAnswer(text, {
      groundingChunks: chunks,
      groundingSupports: [
        { segment: { startIndex: 27, endIndex: 37 }, groundingChunkIndices: [1] },
        { segment: { startIndex: 0, endIndex: 11 }, groundingChunkIndices: [0] },
      ],
    });
    expect(segs.map((s) => s.kind)).toEqual(["live", "registry", "live"]);
    expect(segs[0].sources?.[0].uri).toBe("https://maps.example/a");
    expect(segs[2].sources?.[0].uri).toBe("https://maps.example/b");
  });

  it("converts UTF-8 byte offsets to string offsets", () => {
    const text = "Café open. Next.";
    // "Café open." is 11 bytes in UTF-8 (é is 2 bytes) but 10 UTF-16 units.
    const segs = segmentAnswer(text, {
      groundingChunks: chunks,
      groundingSupports: [{ segment: { startIndex: 0, endIndex: 11, text: "Café open." }, groundingChunkIndices: [0] }],
    });
    expect(segs[0]).toMatchObject({ kind: "live", text: "Café open." });
  });

  it("returns one registry segment with no grounding", () => {
    expect(segmentAnswer("Plain answer.")).toEqual([{ text: "Plain answer.", kind: "registry" }]);
  });

  it("drops inline [INDEX n] citation markers and keeps the grounded span's sources", () => {
    const text = "Shelter A is open [INDEX 1]. Shelter B is unknown [INDEX 2, 3].";
    const segs = segmentAnswer(text, {
      groundingChunks: [{ maps: { uri: "https://maps.google.com/?cid=1", title: "Shelter A" } }],
      groundingSupports: [{ segment: { text: "Shelter A is open [INDEX 1]." }, groundingChunkIndices: [0] }],
    });
    expect(segs.map((s) => s.text).join("")).toBe("Shelter A is open. Shelter B is unknown.");
    expect(segs[0]).toMatchObject({ kind: "live", sources: [{ title: "Shelter A" }] });
  });
});

describe("collectReferences", () => {
  it("finds nested ids in arrays and objects", () => {
    const refs = collectReferences({
      result: { shelters: [{ shelter_id: "a" }, { shelter_id: 7, county_fips: "13051" }] },
      county: { county_fips: "13127" },
    });
    expect(refs.shelterIds.sort()).toEqual(["7", "a"]);
    expect(refs.countyFips.sort()).toEqual(["13051", "13127"]);
  });
});

describe("collectLiveChecks (T078)", () => {
  it("finds nested live_check objects and ignores invalid statuses", async () => {
    const { collectLiveChecks } = await import("../../src/lib/grounding");
    const found = collectLiveChecks({
      a: { live_check: { shelter_id: "M1", status: "renamed", place_id: "p1" } },
      b: [{ live_check: { shelter_id: 7, status: "closed" } }],
      c: { live_check: { shelter_id: "X", status: "gone" } },
    });
    expect(found).toEqual([
      { shelter_id: "M1", status: "renamed", place_id: "p1" },
      { shelter_id: "7", status: "closed" },
    ]);
  });
});
