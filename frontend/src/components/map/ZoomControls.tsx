import { MAX_ZOOM, MIN_ZOOM } from "./MapView";

const EPS = 1e-6;

/** Zoom in / out / reset over the map's corner; each is disabled at its limit (FR-015, FR-017). */
export default function ZoomControls({
  k,
  panned,
  onZoomIn,
  onZoomOut,
  onReset,
}: {
  k: number;
  panned: boolean;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onReset: () => void;
}) {
  const whole = k <= MIN_ZOOM + EPS;
  return (
    <div className="zoom-controls">
      <button type="button" className="btn zoom-btn" aria-label="Zoom in" disabled={k >= MAX_ZOOM - EPS} onClick={onZoomIn}>
        +
      </button>
      <button type="button" className="btn zoom-btn" aria-label="Zoom out" disabled={whole} onClick={onZoomOut}>
        −
      </button>
      <button type="button" className="btn zoom-btn" aria-label="Reset view" disabled={whole && !panned} onClick={onReset}>
        ⟲
      </button>
    </div>
  );
}
