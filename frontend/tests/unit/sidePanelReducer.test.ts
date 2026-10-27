import { describe, expect, it } from "vitest";
import type { LineString } from "geojson";
import { initialState, reducer, type Action, type State } from "../../src/state/store";

const glynn: LineString = { type: "LineString", coordinates: [[-80.8, 31.0], [-82.0, 31.4]] };
const base: State = { ...initialState, historyLoaded: true };
const run = (actions: Action[], from: State = base) => actions.reduce(reducer, from);
const withTrack = run([{ type: "setTrack", track: glynn, id: "a" }, { type: "setSideTab", tab: "details" }, { type: "setSideTab", tab: "chat" }]);

const NEWS: [string, Action, State][] = [
  ["selectCounty", { type: "selectCounty", fips: "13127" }, base],
  ["selectShelter", { type: "selectShelter", id: "M1" }, base],
  ["setTrack", { type: "setTrack", track: glynn, id: "b" }, base],
  ["setCategory", { type: "setCategory", category: 4 }, withTrack],
  ["setCutoff", { type: "setCutoff", cutoff_km: 120 }, withTrack],
  ["openScenario", { type: "openScenario", id: "a" }, run([{ type: "newSimulation" }], withTrack)],
];

describe("side panel tabs (data-model.md, FR-009, FR-012)", () => {
  it("opens on Chat with nothing unseen", () => {
    expect(initialState.sideTab).toBe("chat");
    expect(initialState.detailsUnseen).toBe(false);
    expect(withTrack.detailsUnseen).toBe(false);
  });

  it.each(NEWS)("%s while on Chat marks Details unseen", (_, action, from) => {
    expect(reducer(from, action).detailsUnseen).toBe(true);
  });

  it.each(NEWS)("%s while on Details leaves it seen", (_, action, from) => {
    const s = reducer({ ...from, sideTab: "details" }, action);
    expect(s.detailsUnseen).toBe(false);
    expect(s.sideTab).toBe("details");
  });

  it("hover never marks Details unseen", () => {
    expect(run([{ type: "hover", fips: "13127" }]).detailsUnseen).toBe(false);
  });

  it("opening Details clears the marker; going back to Chat does not set it", () => {
    const s = run([{ type: "selectCounty", fips: "13127" }, { type: "setSideTab", tab: "details" }]);
    expect(s.sideTab).toBe("details");
    expect(s.detailsUnseen).toBe(false);
    expect(reducer(s, { type: "setSideTab", tab: "chat" }).detailsUnseen).toBe(false);
  });
});
