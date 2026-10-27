import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { LineString } from "geojson";
import mapData from "../mocks/mapData.fixture.json";
import { MAPS_CHECK_BATCH, ReceivingListView } from "../../src/components/scenario/ReceivingList";
import { countyCentroids, gaCounties } from "../../src/lib/geo";
import { HALF_WIDTH_KM, affected, computeBand, receivingList } from "../../src/lib/simulation";
import type { HurricaneScenario, MapData } from "../../src/lib/types";

const data = mapData as unknown as MapData;
const shelterById = new Map(data.shelters.map((s) => [s.shelter_id, s]));

function scenario(track: LineString, cutoff: number): HurricaneScenario {
  const band = computeBand(track, 1);
  const hit = affected(band, data.shelters, gaCounties.features);
  return {
    track,
    category: 1,
    half_width_km: HALF_WIDTH_KM[1],
    band,
    cutoff_km: cutoff,
    affected_county_fips: hit.countyFips,
    affected_shelter_ids: hit.shelterIds,
    receiving: receivingList(data.shelters, new Set(hit.shelterIds), hit.countyFips, countyCentroids, cutoff),
  };
}

const cobb: LineString = { type: "LineString", coordinates: [[-84.7, 33.8], [-84.4, 34.1]] };

describe("ReceivingList", () => {
  it("header shows the cutoff and all three wheelchair counts", () => {
    render(<ReceivingListView scenario={scenario(cobb, 200)} shelterById={shelterById} onSelect={() => {}} />);
    const header = screen.getByTestId("receiving-header");
    expect(header).toHaveTextContent("within 200 km");
    expect(header).toHaveTextContent(/\d+ yes · \d+ no · \d+ not recorded/);
  });

  it('shows "Not recorded", never "No", for a blank wheelchair flag', () => {
    render(<ReceivingListView scenario={scenario(cobb, 200)} shelterById={shelterById} onSelect={() => {}} />);
    // Commerce Primary School has no wheelchair record.
    const row = screen.getByText("Commerce Primary School").closest("tr")!;
    expect(row).toHaveTextContent("Not recorded");
  });

  it("a suspect shelter row shows its warning and reason, and totals name it", () => {
    render(<ReceivingListView scenario={scenario(cobb, 200)} shelterById={shelterById} onSelect={() => {}} />);
    const row = screen.getByText("Commerce High School").closest("tr")!;
    expect(row).toHaveTextContent("!");
    expect(row.nextElementSibling).toHaveTextContent("Capacity looks implausible; ranked as 0");
    expect(screen.getByText(/Excludes 2 shelters with suspect capacity/)).toBeInTheDocument();
  });

  it("shows the empty state for an empty list", () => {
    render(<ReceivingListView scenario={scenario(cobb, 25)} shelterById={shelterById} onSelect={() => {}} />);
    expect(screen.getByTestId("receiving-empty")).toHaveTextContent("No shelters within 25 km");
  });

  it("is labeled illustrative (FR-019)", () => {
    render(<ReceivingListView scenario={scenario(cobb, 200)} shelterById={shelterById} onSelect={() => {}} />);
    expect(screen.getByText("Illustrative scenario — not a forecast")).toBeInTheDocument();
  });
});

describe("ReceivingList: filled and live-checked data is called out", () => {
  const view = (extra: Partial<Parameters<typeof ReceivingListView>[0]> = {}) =>
    render(<ReceivingListView scenario={scenario(cobb, 200)} shelterById={shelterById} onSelect={() => {}} {...extra} />);

  it("offers a Maps check only for not-recorded shelters and calls it back with their ids", () => {
    const ids: string[][] = [];
    view({ onCheckWheelchair: (x) => ids.push(x) });
    screen.getByTestId("maps-check-button").click();
    expect(ids).toHaveLength(1);
    expect(ids[0].length).toBeLessThanOrEqual(MAPS_CHECK_BATCH);
    for (const id of ids[0]) expect(shelterById.get(id)!.wheelchair_accessible).toBe("UNRECORDED");
  });

  it("shows a Maps result beside 'Not recorded', labelled unverified, never as Yes", () => {
    const s = data.shelters.find((x) => x.name === "Commerce Primary School")!;
    const checks = new Map([[s.shelter_id, {
      shelter_id: s.shelter_id, status: "listed_accessible" as const, place: "same" as const, evidence: "",
      sources: [{ title: "Commerce Primary", uri: "https://maps.google.com/?cid=1" }], checked_at: "2026-10-27T00:00:00Z",
    }]]);
    view({ wheelchairChecks: checks });
    const row = screen.getByText("Commerce Primary School").closest("tr")!;
    expect(row).toHaveTextContent("Not recorded");
    expect(row).toHaveTextContent("Maps lists accessible entrance");
    expect(row).toHaveTextContent("unverified");
    expect(screen.getByTestId("maps-summary")).toHaveTextContent("Unverified");
  });

  it("marks a surge flag filled from NOAA and counts them", () => {
    const filled = { ...data.shelters[0], in_surge_slosh_area: "YES" as const, in_surge_source: "noaa_slosh" as const,
      surge_noaa: { status: "inundated" as const, first_category: 3 } };
    const sc = scenario(cobb, 200);
    const id = sc.receiving[0].shelter_id;
    const map = new Map(shelterById);
    map.set(id, { ...filled, shelter_id: id });
    render(<ReceivingListView scenario={sc} shelterById={map} onSelect={() => {}} />);
    expect(screen.getAllByText("NOAA map").length).toBeGreaterThan(0);
    expect(screen.getByTestId("surge-noaa-note")).toHaveTextContent("1 surge flags had no registry record");
    expect(screen.getAllByText("Floods from Cat 3").length).toBeGreaterThan(0);
  });
});
