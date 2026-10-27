import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import EarlierQuestions from "../../src/components/chat/EarlierQuestions";

const questions = [
  { text: "Which of these receiving shelters can actually take a wheelchair?", asked_at: "2026-10-27T12:01:00.000Z" },
  { text: "Which are in the surge zone?", asked_at: "2026-10-27T12:02:00.000Z" },
];

describe("EarlierQuestions (T018)", () => {
  it("lists every question and re-asks the exact text", async () => {
    const user = userEvent.setup();
    const onAsk = vi.fn();
    render(<EarlierQuestions questions={questions} resimulatedAt="2026-10-27T13:00:00.000Z" onAsk={onAsk} disabled={false} />);
    expect(screen.getByText(/Results re-simulated at/)).toBeInTheDocument();
    const buttons = screen.getAllByRole("button", { name: "Ask again" });
    expect(buttons).toHaveLength(2);
    await user.click(buttons[1]);
    expect(onAsk).toHaveBeenCalledWith("Which are in the surge zone?");
    // Still available after re-asking one (analysis H2).
    expect(screen.getAllByRole("button", { name: "Ask again" })).toHaveLength(2);
  });

  it("disables Ask again while an answer is streaming", () => {
    render(<EarlierQuestions questions={questions} resimulatedAt="2026-10-27T13:00:00.000Z" onAsk={() => {}} disabled />);
    for (const b of screen.getAllByRole("button", { name: "Ask again" })) expect(b).toBeDisabled();
  });
});
