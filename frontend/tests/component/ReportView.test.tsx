import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ReportView from "../../src/components/chat/ReportView";
import type { Report } from "../../src/lib/types";
import county from "../mocks/report.county.fixture.json";
import run from "../mocks/report.run.fixture.json";
import runs from "../mocks/report.runs.fixture.json";

describe("ReportView", () => {
  it("renders every section of a county report with season ranges", () => {
    render(<ReportView report={county as unknown as Report} />);
    expect(screen.getByText("Who cannot leave")).toBeTruthy();
    expect(screen.getByText("Audit")).toBeTruthy();
    expect(screen.getAllByText(/1-in-10/).length).toBeGreaterThan(0);
  });

  it("shows the reason for sections that do not apply", () => {
    render(<ReportView report={run as unknown as Report} />);
    expect(screen.getByText("Ask for a county plan for tracts and facilities.")).toBeTruthy();
  });

  it("expands to full screen and closes with Escape", () => {
    render(<ReportView report={county as unknown as Report} />);
    fireEvent.click(screen.getByRole("button", { name: "Open report full screen" }));
    expect(screen.getByTestId("report").className).toContain("report--expanded");
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.getByTestId("report").className).not.toContain("report--expanded");
  });

  it("shows the middle of each range and the most affected counties", () => {
    render(<ReportView report={runs as unknown as Report} />);
    expect(screen.getByTestId("report-counties").querySelectorAll("tbody tr").length).toBeGreaterThan(0);
    expect(screen.getAllByText("middle").length).toBeGreaterThan(1);
  });

  it("lists what the model could not tell and spells out the support label", () => {
    render(<ReportView report={runs as unknown as Report} />);
    expect(
      screen.getByText("Outage is modelled from wind exposure; local tree and line conditions are not known."),
    ).toBeTruthy();
    expect(screen.queryByText(/_labeled_support/)).toBeNull();
  });
});
