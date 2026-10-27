import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import AnswerView from "../../src/components/chat/AnswerView";
import { StoreProvider } from "../../src/state/store";
import type { ChatExchange } from "../../src/lib/types";
import { chatEvents, mockGrounding } from "../mocks/handlers";

const finalText = (chatEvents[chatEvents.length - 1].content.parts[0] as { text: string }).text;

const exchange = (patch: Partial<ChatExchange> = {}): ChatExchange => ({
  id: "x",
  question: "q",
  context: { county_fips: null, shelter_id: null, scenario: null },
  status: "done",
  text: finalText,
  groundingMetadata: mockGrounding,
  referenced_shelter_ids: [],
  referenced_county_fips: [],
  ...patch,
});

const renderAnswer = (x: ChatExchange, onRetry = () => {}) =>
  render(
    <StoreProvider>
      <AnswerView exchange={x} onRetry={onRetry} />
    </StoreProvider>,
  );

describe("AnswerView (FR-012, FR-013)", () => {
  it("renders sources as the next sibling after the live segment", () => {
    renderAnswer(exchange());
    const live = document.querySelector('[data-kind="live"]')!;
    expect(live).toHaveTextContent("Macon Centreplex is open");
    expect(live.nextElementSibling).toBe(screen.getByTestId("sources"));
    expect(screen.getByRole("link", { name: "Macon Centreplex" })).toHaveAttribute("href", "https://maps.google.com/?cid=1");
  });

  it('keeps "Google Maps" untranslated', () => {
    renderAnswer(exchange());
    expect(screen.getByText("Google Maps")).toHaveAttribute("translate", "no");
  });

  it("registry text carries no live badge", () => {
    renderAnswer(exchange());
    const registry = [...document.querySelectorAll('[data-kind="registry"]')];
    expect(registry.length).toBeGreaterThan(0);
    for (const r of registry) expect(r).not.toHaveTextContent("Live check");
  });

  it("a failed exchange shows Retry", () => {
    const onRetry = vi.fn();
    renderAnswer(exchange({ status: "failed", text: "", error: "HTTP 500" }), onRetry);
    screen.getByRole("button", { name: "Retry" }).click();
    expect(onRetry).toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent("HTTP 500");
  });
});
