import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "../../src/App";
import { ONBOARDING_KEY, TOUR_STEPS } from "../../src/lib/onboarding";
import { StoreProvider } from "../../src/state/store";

vi.mock("../../src/lib/agentClient", async (orig) => ({
  ...(await orig<typeof import("../../src/lib/agentClient")>()),
  loadMapData: () => new Promise(() => {}),
}));

const renderApp = () =>
  render(
    <StoreProvider>
      <App />
    </StoreProvider>,
  );

describe("Onboarding walkthrough", () => {
  beforeEach(() => window.localStorage.clear());

  it("opens on first visit, steps through, and stays closed after Done", async () => {
    const user = userEvent.setup();
    const { unmount } = renderApp();
    expect(screen.getByRole("dialog", { name: TOUR_STEPS[0].title })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Back" })).toBeDisabled();
    for (let i = 1; i < TOUR_STEPS.length; i++) {
      await user.click(screen.getByRole("button", { name: "Next" }));
      expect(screen.getByRole("dialog", { name: TOUR_STEPS[i].title })).toBeInTheDocument();
    }
    await user.click(screen.getByRole("button", { name: "Back" }));
    expect(screen.getByRole("dialog", { name: TOUR_STEPS[TOUR_STEPS.length - 2].title })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Next" }));
    await user.click(screen.getByRole("button", { name: "Done" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(window.localStorage.getItem(ONBOARDING_KEY)).toBe("done");
    unmount();
    renderApp();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("reopens from How to use, closes on Escape and returns focus to the trigger", async () => {
    window.localStorage.setItem(ONBOARDING_KEY, "done");
    const user = userEvent.setup();
    renderApp();
    const trigger = screen.getByRole("button", { name: "How to use" });
    await user.click(trigger);
    const next = screen.getByRole("button", { name: "Next" });
    await waitFor(() => expect(next).toHaveFocus());
    await user.tab();
    await user.tab();
    expect(screen.getByRole("dialog").contains(document.activeElement)).toBe(true);
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("Skip dismisses for good", async () => {
    const user = userEvent.setup();
    renderApp();
    await user.click(screen.getByRole("button", { name: "Skip" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(window.localStorage.getItem(ONBOARDING_KEY)).toBe("done");
  });
});
