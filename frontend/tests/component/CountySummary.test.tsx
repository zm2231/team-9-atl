import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import mapData from "../mocks/mapData.fixture.json";
import { CountySummaryView } from "../../src/components/summary/CountySummary";
import type { MapData } from "../../src/lib/types";

const data = mapData as unknown as MapData;
const county = (fips: string) => data.counties.find((c) => c.county_fips === fips)!;

describe("CountySummary", () => {
  it("Jackson: total excludes Commerce, names both, and shows the including total", () => {
    render(<CountySummaryView county={county("13157")} />);
    const note = screen.getByTestId("exclusion-note");
    expect(note).toHaveTextContent("Excludes 2 shelters with suspect capacity: Commerce High School, Commerce Primary School");
    expect(note).toHaveTextContent((600 + 270135 + 225112).toLocaleString("en-US"));
    expect(screen.getByText("Recorded evacuation capacity").nextSibling).toHaveTextContent("600");
  });

  it("SC-003: unrecorded wheelchair count shown separately, not added to No", () => {
    render(<CountySummaryView county={county("13157")} />);
    // Jackson: J3 yes, J1 and J2 not recorded.
    expect(screen.getByText("Wheelchair access").nextSibling).toHaveTextContent("1 yes · 0 no · 2 not recorded");
  });

  it('zero-shelter county shows "No shelters on file"', () => {
    render(<CountySummaryView county={county("13001")} />);
    expect(screen.getByText("No shelters on file.")).toBeInTheDocument();
  });

  it("disability figure names its source, estimate type and table", () => {
    render(<CountySummaryView county={county("13051")} />);
    expect(screen.getAllByText(/ACS survey estimate via CDC SVI · vulnerability_tracts/).length).toBe(1);
  });
});
