import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { geoMercator, geoPath, type GeoPath, type GeoProjection } from "d3-geo";
import { pointer, select } from "d3-selection";
import { zoom, zoomIdentity, zoomTransform, type ZoomTransform } from "d3-zoom";
import { gaCounties } from "../../lib/geo";
import { useStore } from "../../state/store";
import CountyLayer from "./CountyLayer";
import ShelterLayer from "./ShelterLayer";
import { DrawOverlay, TrackLayer, type LiveTrack } from "./TrackDrawer";
import ZoomControls from "./ZoomControls";

/** Whole state to 8× (feature 003 FR-017); each button click is one 1.5× step (FR-016). */
export const MIN_ZOOM = 1;
export const MAX_ZOOM = 8;
export const ZOOM_STEP = 1.5;

interface MapGeometry {
  projection: GeoProjection;
  path: GeoPath;
  width: number;
  height: number;
  /** The current zoom; pointer input goes through transform.invert (research R10). */
  transform: ZoomTransform;
  /** Zoom scale, used to keep markers a constant on-screen size (research R9). */
  k: number;
}

const MapContext = createContext<MapGeometry | null>(null);

export function useMapGeometry(): MapGeometry {
  const v = useContext(MapContext);
  if (!v) throw new Error("useMapGeometry must be used inside MapView");
  return v;
}

export const CLICK_DISTANCE = 5;
export const PAN_MARGIN = 0.5;

/** Wheel and pinch always zoom; a drag pans only when not drawing; double-click never zooms. */
export function createMapZoom(isDrawing: () => boolean, onZoom: (t: ZoomTransform) => void) {
  return zoom<SVGSVGElement, unknown>()
    .scaleExtent([MIN_ZOOM, MAX_ZOOM])
    .clickDistance(CLICK_DISTANCE)
    .filter((e: Event) => e.type === "wheel" || (!isDrawing() && !(e as MouseEvent).button))
    .on("zoom", (e: { transform: ZoomTransform }) => onZoom(e.transform));
}

export function panExtent(width: number, height: number): [[number, number], [number, number]] {
  return [
    [-width * PAN_MARGIN, -height * PAN_MARGIN],
    [width * (1 + PAN_MARGIN), height * (1 + PAN_MARGIN)],
  ];
}

/** Safari reports a trackpad pinch as gesture events rather than ctrl+wheel (research R8). */
type GestureEvent = UIEvent & { scale: number; clientX: number; clientY: number };

export default function MapView() {
  const ref = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const [size, setSize] = useState({ width: 640, height: 720 });
  const [transform, setTransform] = useState<ZoomTransform>(zoomIdentity);
  const [live, setLive] = useState<LiveTrack>([]);
  const { state } = useStore();

  // Dragging draws a track while drawing is on, so the zoom must not also pan (FR-018).
  const drawingRef = useRef(state.drawing);
  drawingRef.current = state.drawing;

  const [behavior] = useState(() => createMapZoom(() => drawingRef.current, setTransform));

  useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      if (width > 0 && height > 0) setSize({ width, height });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const sel = select(svg);
    sel.call(behavior).on("dblclick.zoom", null);

    let lastScale = 1;
    const start = (e: Event) => {
      e.preventDefault();
      lastScale = 1;
    };
    const change = (e: Event) => {
      e.preventDefault();
      const g = e as GestureEvent;
      behavior.scaleBy(sel, g.scale / lastScale, pointer(g, svg));
      lastScale = g.scale;
    };
    const end = (e: Event) => e.preventDefault();
    svg.addEventListener("gesturestart", start, { passive: false });
    svg.addEventListener("gesturechange", change, { passive: false });
    svg.addEventListener("gestureend", end, { passive: false });
    return () => {
      sel.on(".zoom", null);
      svg.removeEventListener("gesturestart", start);
      svg.removeEventListener("gesturechange", change);
      svg.removeEventListener("gestureend", end);
    };
  }, [behavior]);

  // On resize, keep the zoom and the area in view, then let the new extent clamp it (research R11).
  const lastSize = useRef(size);
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const { width, height } = size;
    const prev = lastSize.current;
    lastSize.current = size;
    behavior.extent([[0, 0], [width, height]]).translateExtent(panExtent(width, height));
    const t = zoomTransform(svg);
    const next = zoomIdentity.translate((t.x * width) / prev.width, (t.y * height) / prev.height).scale(t.k);
    select(svg).call(behavior.transform, next);
  }, [size, behavior]);

  const zoomBy = useCallback(
    (factor: number) => svgRef.current && select(svgRef.current).call(behavior.scaleBy, factor),
    [behavior],
  );
  const resetZoom = useCallback(
    () => svgRef.current && select(svgRef.current).call(behavior.transform, zoomIdentity),
    [behavior],
  );

  // A reopened scenario starts at the whole state; the view is never saved (FR-021).
  useEffect(() => {
    if (state.resimulatedAt) resetZoom();
  }, [state.resimulatedAt, resetZoom]);

  // The projection depends on size only, so zooming never recomputes county paths.
  const base = useMemo(() => {
    const projection = geoMercator().fitSize([size.width, size.height], gaCounties);
    return { projection, path: geoPath(projection), ...size };
  }, [size]);
  const geometry = useMemo<MapGeometry>(() => ({ ...base, transform, k: transform.k }), [base, transform]);

  return (
    <MapContext.Provider value={geometry}>
      <div ref={ref} className={`map${state.drawing ? " map--drawing" : ""}`}>
        <svg
          ref={svgRef}
          viewBox={`0 0 ${size.width} ${size.height}`}
          role="img"
          aria-label="Georgia counties and shelters"
          data-zoom-k={transform.k}
        >
          <g className="zoom-layer" transform={transform.toString()}>
            <CountyLayer />
            <TrackLayer live={live} />
            <ShelterLayer />
          </g>
          <DrawOverlay onLive={setLive} />
        </svg>
        <ZoomControls
          k={transform.k}
          panned={transform.x !== 0 || transform.y !== 0}
          onZoomIn={() => zoomBy(ZOOM_STEP)}
          onZoomOut={() => zoomBy(1 / ZOOM_STEP)}
          onReset={resetZoom}
        />
      </div>
    </MapContext.Provider>
  );
}
