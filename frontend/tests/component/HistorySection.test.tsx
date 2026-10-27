import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { LineString } from "geojson";
import HistorySection from "../../src/components/chat/HistorySection";
import { StoreProvider, useStore, type State } from "../../src/state/store";
import type { SavedScenario } from "../../src/lib/history";

const glynn: LineString = { type: "LineString", coordinates: [[-80.8, 31.0], [-82.0, 31.4]] };
const iso = (min: number) => new Date(Date.UTC(2026, 9, 27, 12, min)).toISOString();

const entry = (id: string, name: string, openedMin: number): SavedScenario => ({
  id,
  name,
  nameIsCustom: false,
  track: glynn,
  category: 3,
  cutoff_km: 80,
  questions: [],
  created_at: iso(0),
  updated_at: iso(openedMin),
  last_opened_at: iso(openedMin),
});

/** Exposes store fields the assertions need, without reaching into React internals. */
function Probe() {
  const { state } = useStore();
  return (
    <div data-testid="probe" data-current={state.currentScenarioId ?? ""} data-scenario={state.scenario ? "yes" : "no"} />
  );
}

const renderSection = (initial: Partial<State>) =>
  render(
    <StoreProvider initial={{ historyLoaded: true, ...initial }}>
      <HistorySection />
      <Probe />
    </StoreProvider>,
  );

const two = { history: [entry("old", "Cat 3 · Older", 1), entry("new", "Cat 3 · Newer", 9)], currentScenarioId: "new" };

describe("HistorySection (T017, T021)", () => {
  it("is collapsed by default and shows the count", () => {
    renderSection(two);
    const header = screen.getByRole("button", { name: /History \(2\)/ });
    expect(header).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryAllByTestId("history-item")).toHaveLength(0);
  });

  it("lists newest first, marks the current one, and opens another on click", async () => {
    const user = userEvent.setup();
    renderSection(two);
    await user.click(screen.getByRole("button", { name: /History/ }));
    const items = screen.getAllByTestId("history-item");
    expect(items.map((i) => i.textContent)).toEqual([expect.stringContaining("Newer"), expect.stringContaining("Older")]);
    expect(items[0]).toHaveAttribute("aria-current", "true");
    expect(items[1]).not.toHaveAttribute("aria-current");
    await user.click(items[1]);
    expect(screen.getByTestId("probe")).toHaveAttribute("data-current", "old");
    expect(screen.getByTestId("probe")).toHaveAttribute("data-scenario", "yes");
  });

  it("says where history is kept, and when it can't be saved", async () => {
    const user = userEvent.setup();
    const { unmount } = renderSection(two);
    await user.click(screen.getByRole("button", { name: /History/ }));
    expect(screen.getByText(/Saved in this browser only/)).toBeInTheDocument();
    unmount();
    renderSection({ ...two, historyAvailable: false });
    await user.click(screen.getByRole("button", { name: /History/ }));
    expect(screen.getByText("History can't be saved in this browser.")).toBeInTheDocument();
  });

  it("renames with Enter, cancels with Esc", async () => {
    const user = userEvent.setup();
    renderSection(two);
    await user.click(screen.getByRole("button", { name: /History/ }));
    await user.click(screen.getAllByRole("button", { name: "Rename" })[0]);
    const input = screen.getByRole("textbox", { name: "Scenario name" });
    await user.clear(input);
    await user.type(input, "Glynn worst case{Enter}");
    expect(screen.getAllByTestId("history-item")[0]).toHaveTextContent("Glynn worst case");

    await user.click(screen.getAllByRole("button", { name: "Rename" })[1]);
    const input2 = screen.getByRole("textbox", { name: "Scenario name" });
    await user.type(input2, " changed{Escape}");
    expect(screen.getAllByTestId("history-item")[1]).toHaveTextContent("Cat 3 · Older");
  });

  it("asks before deleting; Cancel keeps it, Delete removes it", async () => {
    const user = userEvent.setup();
    renderSection(two);
    await user.click(screen.getByRole("button", { name: /History/ }));
    await user.click(screen.getAllByRole("button", { name: "Delete" })[1]);
    const confirm = screen.getByRole("group", { name: "Delete Cat 3 · Older" });
    await user.click(within(confirm).getByRole("button", { name: "Cancel" }));
    expect(screen.getAllByTestId("history-item")).toHaveLength(2);
    await user.click(screen.getAllByRole("button", { name: "Delete" })[1]);
    await user.click(within(screen.getByRole("group", { name: "Delete Cat 3 · Older" })).getByRole("button", { name: "Delete" }));
    expect(screen.getAllByTestId("history-item")).toHaveLength(1);
    expect(screen.getByRole("button", { name: /History \(1\)/ })).toBeInTheDocument();
  });

  it("deleting the current scenario clears it", async () => {
    const user = userEvent.setup();
    renderSection({ ...two, scenario: { track: glynn, category: 3, cutoff_km: 80 } });
    await user.click(screen.getByRole("button", { name: /History/ }));
    await user.click(screen.getAllByRole("button", { name: "Delete" })[0]);
    await user.click(within(screen.getByRole("group", { name: "Delete Cat 3 · Newer" })).getByRole("button", { name: "Delete" }));
    expect(screen.getByTestId("probe")).toHaveAttribute("data-current", "");
    expect(screen.getByTestId("probe")).toHaveAttribute("data-scenario", "no");
  });

  it("shows and dismisses the history-full notice", async () => {
    const user = userEvent.setup();
    renderSection({ ...two, notice: "History is full: removed 'Old 0' (least recently opened)" });
    await user.click(screen.getByRole("button", { name: /History/ }));
    expect(screen.getByRole("status")).toHaveTextContent("removed 'Old 0'");
    await user.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("lets a scenario be reopened while map data is still loading (edge case)", async () => {
    const user = userEvent.setup();
    renderSection({ ...two, mapData: { status: "loading" } });
    await user.click(screen.getByRole("button", { name: /History/ }));
    await user.click(screen.getAllByTestId("history-item")[1]);
    expect(screen.getByTestId("probe")).toHaveAttribute("data-current", "old");
  });
});
