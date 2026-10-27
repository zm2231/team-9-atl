import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ReportView from "../../src/components/chat/ReportView";
import type { Report } from "../../src/lib/types";
import county from "../mocks/report.county.fixture.json";
import run from "../mocks/report.run.fixture.json";

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
});
