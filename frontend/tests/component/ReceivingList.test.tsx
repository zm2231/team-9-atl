import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { LineString } from "geojson";
import mapData from "../mocks/mapData.fixture.json";
import { ReceivingListView } from "../../src/components/scenario/ReceivingList";
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
