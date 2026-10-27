import { describe, expect, it } from "vitest";
import {
  countFlags,
  exclusionNote,
  flagClass,
  flagCountsLine,
  flagLabel,
  sourceLabel,
} from "../../src/lib/flags";
import type { Flag, Shelter } from "../../src/lib/types";

const s = (wc: Flag): Shelter => ({
  shelter_id: wc,
  name: wc,
  county_fips: "13001",
  county_name: "X",
  lat: 0,
  lon: 0,
  evacuation_capacity: 1,
  usage: null,
  wheelchair_accessible: wc,
  generator_onsite: "UNRECORDED",
  is_medical: "UNRECORDED",
  in_surge_slosh_area: "UNRECORDED",
  quality_flags: [],
});

describe("flags (SC-003, Constitution I)", () => {
  it('labels UNRECORDED "Not recorded" with a class distinct from NO', () => {
    expect(flagLabel("UNRECORDED")).toBe("Not recorded");
    expect(flagLabel("NO")).toBe("No");
    expect(flagClass("UNRECORDED")).not.toBe(flagClass("NO"));
  });

  it("keeps unrecorded separate and never adds it to no", () => {
    const c = countFlags([s("YES"), s("NO"), s("UNRECORDED"), s("UNRECORDED")], "wheelchair_accessible");
    expect(c).toEqual({ yes: 1, no: 1, unrecorded: 2 });
  });

  it("never returns a boolean for a flag", () => {
    for (const f of ["YES", "NO", "UNRECORDED"] as Flag[]) {
      expect(typeof flagLabel(f)).toBe("string");
      expect(typeof flagClass(f)).toBe("string");
    }
  });

  it("always shows all three counts, even when zero", () => {
    expect(flagCountsLine({ yes: 4, no: 0, unrecorded: 0 })).toBe("4 yes · 0 no · 0 not recorded");
  });
});

describe("exclusionNote (Constitution VI)", () => {
  it("names every excluded shelter and the count", () => {
    expect(exclusionNote([{ name: "Commerce High School" }, { name: "Commerce Primary School" }])).toBe(
      "Excludes 2 shelters with suspect capacity: Commerce High School, Commerce Primary School",
    );
  });
  it("is empty only for an empty list", () => {
    expect(exclusionNote([])).toBe("");
    expect(exclusionNote([{ name: "A" }])).toContain("1 shelter ");
  });
});

describe("sourceLabel (Constitution III)", () => {
  it("contains the table name and coverage", () => {
    const label = sourceLabel({
      value: 0.1,
      source: "ACS survey estimate via CDC SVI · vulnerability_tracts",
      kind: "survey",
      coverage: "412 of 415 tracts",
    });
    expect(label).toContain("vulnerability_tracts");
    expect(label).toContain("412 of 415 tracts");
  });
});
