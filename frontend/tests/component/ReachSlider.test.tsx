import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import ReachSlider from "../../src/components/scenario/ReachSlider";

describe("ReachSlider (research R3)", () => {
  it("shows miles and emits kilometres", () => {
    const onChange = vi.fn();
    render(<ReachSlider value={80} unit="mi" onChange={onChange} />);
    expect(screen.getByText("50 mi")).toBeInTheDocument();
    const slider = screen.getByRole("slider", { name: "Within reach cutoff in miles" });
    expect(slider).toHaveAttribute("min", "16");
    expect(slider).toHaveAttribute("max", "124");
    expect(slider).toHaveAttribute("step", "1");
    fireEvent.change(slider, { target: { value: "60" } });
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange.mock.calls[0][0]).toBeCloseTo(96.56064, 4);
  });

  it("shows kilometres on the existing scale", () => {
    render(<ReachSlider value={80} unit="km" onChange={() => {}} />);
    expect(screen.getByText("80 km")).toBeInTheDocument();
    const slider = screen.getByRole("slider", { name: "Within reach cutoff in kilometres" });
    expect(slider).toHaveAttribute("min", "25");
    expect(slider).toHaveAttribute("max", "200");
    expect(slider).toHaveAttribute("step", "5");
  });

  it("switching units never changes the reach", () => {
    const onChange = vi.fn();
    const { rerender } = render(<ReachSlider value={80.4672} unit="mi" onChange={onChange} />);
    expect(screen.getByText("50 mi")).toBeInTheDocument();
    rerender(<ReachSlider value={80.4672} unit="km" onChange={onChange} />);
    expect(screen.getByText("80 km")).toBeInTheDocument();
    rerender(<ReachSlider value={80.4672} unit="mi" onChange={onChange} />);
    expect(onChange).not.toHaveBeenCalled();
  });
});
