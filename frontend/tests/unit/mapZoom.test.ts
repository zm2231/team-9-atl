import { describe, expect, it } from "vitest";
import { CLICK_DISTANCE, createMapZoom, panExtent } from "../../src/components/map/MapView";

describe("map zoom", () => {
  it("pans on drag only when not drawing; wheel always zooms", () => {
    let drawing = false;
    const z = createMapZoom(() => drawing, () => {});
    const filter = z.filter() as unknown as (e: Event) => boolean;
    const down = { type: "mousedown", button: 0 } as unknown as Event;
    const wheel = { type: "wheel" } as unknown as Event;
    expect(filter(down)).toBe(true);
    drawing = true;
    expect(filter(down)).toBe(false);
    expect(filter(wheel)).toBe(true);
  });

  it("treats a small press as a click and allows panning past the edges", () => {
    expect(createMapZoom(() => false, () => {}).clickDistance()).toBe(CLICK_DISTANCE);
    expect(panExtent(100, 200)).toEqual([[-50, -100], [150, 300]]);
  });
});
