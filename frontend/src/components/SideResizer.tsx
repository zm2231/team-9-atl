import { useRef, type KeyboardEvent, type PointerEvent } from "react";
import { SIDE_STEP } from "../lib/sideWidth";

export default function SideResizer({
  width,
  min,
  max,
  onResize,
}: {
  width: number;
  min: number;
  max: number;
  onResize: (width: number, persist: boolean) => void;
}) {
  const drag = useRef<{ x: number; width: number } | null>(null);

  const widthAt = (e: PointerEvent) => (drag.current ? drag.current.width - (e.clientX - drag.current.x) : width);

  const onKeyDown = (e: KeyboardEvent) => {
    const to = { ArrowLeft: width + SIDE_STEP, ArrowRight: width - SIDE_STEP, Home: max, End: min }[e.key];
    if (to === undefined) return;
    e.preventDefault();
    onResize(to, true);
  };

  return (
    <div
      className="side-resizer"
      role="separator"
      aria-orientation="vertical"
      aria-label="Resize side panel"
      aria-controls="side-panel"
      aria-valuenow={width}
      aria-valuemin={min}
      aria-valuemax={max}
      tabIndex={0}
      onKeyDown={onKeyDown}
      onPointerDown={(e) => {
        e.preventDefault();
        e.currentTarget.setPointerCapture?.(e.pointerId);
        drag.current = { x: e.clientX, width };
      }}
      onPointerMove={(e) => drag.current && onResize(widthAt(e), false)}
      onPointerUp={(e) => {
        if (!drag.current) return;
        onResize(widthAt(e), true);
        drag.current = null;
      }}
      onPointerCancel={() => {
        drag.current = null;
      }}
    />
  );
}
