import { describe, expect, it } from "vitest";
import type { LineString } from "geojson";
import { initialState, reducer, type Action, type State } from "../../src/state/store";

const glynn: LineString = { type: "LineString", coordinates: [[-80.8, 31.0], [-82.0, 31.4]] };
const run = (actions: Action[], from: State = { ...initialState, historyLoaded: true }) => actions.reduce(reducer, from);

describe("distance unit in the store (data-model.md)", () => {
  it("starts in miles and switches", () => {
    expect(initialState.unit).toBe("mi");
    expect(run([{ type: "setUnit", unit: "km" }]).unit).toBe("km");
  });

  it("reopening a scenario keeps the unit and the stored km cutoff", () => {
    const s = run([
      { type: "setUnit", unit: "km" },
      { type: "setTrack", track: glynn, id: "a" },
      { type: "setCutoff", cutoff_km: 120 },
      { type: "newSimulation" },
      { type: "setUnit", unit: "mi" },
      { type: "openScenario", id: "a" },
    ]);
    expect(s.unit).toBe("mi");
    expect(s.scenario?.cutoff_km).toBe(120);
    expect(s.history[0].cutoff_km).toBe(120);
  });
});
