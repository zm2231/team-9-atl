import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import mapData from "../mocks/mapData.fixture.json";
import SidePanel from "../../src/components/SidePanel";
import { StoreProvider, useStore, type State } from "../../src/state/store";
import { ScenarioProvider } from "../../src/state/scenario";
import type { MapData } from "../../src/lib/types";

const data = mapData as unknown as MapData;

let dispatchRef: ReturnType<typeof useStore>["dispatch"] | null = null;
function GrabDispatch() {
  dispatchRef = useStore().dispatch;
  return null;
}

const renderPanel = (initial: Partial<State> = {}) =>
  render(
    <StoreProvider initial={{ mapData: { status: "ready", data }, ...initial }}>
      <ScenarioProvider>
        <GrabDispatch />
        <SidePanel />
      </ScenarioProvider>
    </StoreProvider>,
  );

describe("SidePanel (FR-008–FR-014, contracts/ui-controls.md)", () => {
  it("opens on Chat with Details one click away", () => {
    renderPanel();
    expect(screen.getByRole("tablist", { name: "Side panel" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Chat" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "Details" })).toHaveAttribute("aria-selected", "false");
    expect(screen.getByRole("tabpanel", { name: "Chat" })).toBeVisible();
    expect(screen.getByTestId("could-not-tell")).not.toBeVisible();
  });

  it("shows everything the old details panel showed", async () => {
    const user = userEvent.setup();
    renderPanel({ selectedFips: "13157" });
    await user.click(screen.getByRole("tab", { name: /^Details/ }));
    expect(screen.getByRole("tabpanel", { name: /^Details/ })).toBeVisible();
    expect(screen.getByTestId("county-summary")).toHaveTextContent("Jackson County");
    expect(screen.getByTestId("could-not-tell")).toBeVisible();
    expect(screen.getByLabelText("Question for the agent")).not.toBeVisible();
  });

  it("keeps typed-but-unsent text across a tab switch", async () => {
    const user = userEvent.setup();
    renderPanel();
    await user.type(screen.getByLabelText("Question for the agent"), "hello");
    await user.click(screen.getByRole("tab", { name: "Details" }));
    await user.click(screen.getByRole("tab", { name: "Chat" }));
    expect(screen.getByLabelText("Question for the agent")).toHaveValue("hello");
  });

  it("marks new details while on Chat and clears the mark when Details is opened", async () => {
    const user = userEvent.setup();
    const { container } = renderPanel();
    act(() => dispatchRef!({ type: "selectCounty", fips: "13157" }));
    expect(screen.getByRole("tab", { name: "Chat" })).toHaveAttribute("aria-selected", "true");
    const details = screen.getByRole("tab", { name: "Details (new details available)" });
    expect(container.querySelector(".side-tab__dot")).not.toBeNull();
    await user.click(details);
    expect(screen.getByRole("tab", { name: "Details" })).toBeInTheDocument();
    expect(container.querySelector(".side-tab__dot")).toBeNull();
  });

  it("moves between tabs with the keyboard", async () => {
    const user = userEvent.setup();
    renderPanel();
    screen.getByRole("tab", { name: "Chat" }).focus();
    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "Details" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "Details" })).toHaveFocus();
    await user.keyboard("{Home}");
    expect(screen.getByRole("tab", { name: "Chat" })).toHaveAttribute("aria-selected", "true");
    await user.keyboard("{End}");
    expect(screen.getByRole("tab", { name: "Details" })).toHaveAttribute("aria-selected", "true");
  });

  it("cannot be hidden or collapsed (FR-013)", () => {
    renderPanel();
    expect(screen.queryByRole("button", { name: /Show details|Hide/ })).toBeNull();
  });
});
