import { useMemo, useRef } from "react";
import { rewind } from "@turf/turf";
import { thinTrack } from "../../lib/simulation";
import { useStore } from "../../state/store";
import { useScenario } from "../../state/scenario";
import { useMapGeometry } from "./MapView";

/** A track being drawn, in lon/lat so it projects correctly at any zoom. */
export type LiveTrack = [number, number][];

/** Band, track, storm glyph and the in-progress track; rendered inside the zoomed group. */
export function TrackLayer({ live }: { live: LiveTrack }) {
  const { projection, path, k } = useMapGeometry();
  const scenario = useScenario();

  // d3-geo treats counter-clockwise rings (GeoJSON/turf order) as "everything except this area";
  // reverse the winding for rendering only.
  const bandPath = useMemo(
    () => (scenario ? path(rewind(scenario.band, { reverse: true })) ?? "" : ""),
    [scenario, path],
  );

  const trackPath = scenario ? path(scenario.track.type === "LineString" ? scenario.track : { type: "LineString", coordinates: [scenario.track.coordinates, scenario.track.coordinates] }) : null;
  const end = scenario
    ? projection(
        scenario.track.type === "LineString"
          ? (scenario.track.coordinates[scenario.track.coordinates.length - 1] as [number, number])
          : (scenario.track.coordinates as [number, number]),
      )
    : null;

  return (
    <g className="scenario-layer">
      {scenario && <path d={bandPath} className="band" data-testid="band" />}
      {trackPath && <path d={trackPath} className="track" />}
      {end && (
        // Counter-scaled so the glyph keeps its size as the map zooms (FR-020).
        <text
          transform={`translate(${end[0]},${end[1]}) scale(${1 / k})`}
          x={-7}
          y={6}
          className="storm-glyph"
          fontSize="18"
          aria-hidden="true"
        >
          🌀
        </text>
      )}
      {live.length > 1 && (
        <polyline
          className="track"
          points={live
            .map((p) => projection(p))
            .filter((p): p is [number, number] => !!p)
            .map(([x, y]) => `${x},${y}`)
            .join(" ")}
        />
      )}
    </g>
  );
}

/**
 * While drawing mode is on, pointer down/move/up collects a track. The scenario is recomputed only
 * when the drag ends, never on pointer move (FR-016, research R5). Rendered outside the zoomed
 * group so it always covers the visible map; positions go through the zoom first (feature 003 R10).
 */
export function DrawOverlay({ onLive }: { onLive: (pts: LiveTrack) => void }) {
  const { state, dispatch } = useStore();
  const { projection, transform, width, height } = useMapGeometry();
  const pts = useRef<LiveTrack>([]);
  const dragging = useRef(false);

  const toLonLat = (e: React.PointerEvent<SVGRectElement>): [number, number] | null => {
    const svg = e.currentTarget.ownerSVGElement;
    if (!svg) return null;
    const box = svg.getBoundingClientRect();
    const x = ((e.clientX - box.left) / box.width) * width;
    const y = ((e.clientY - box.top) / box.height) * height;
    return projection.invert?.(transform.invert([x, y])) as [number, number] | null;
  };

  if (!state.drawing) return null;
  return (
    <rect
      className="draw-overlay"
      data-testid="draw-overlay"
      x={0}
      y={0}
      width={width}
      height={height}
      onPointerDown={(e) => {
        const p = toLonLat(e);
        if (!p) return;
        dragging.current = true;
        e.currentTarget.setPointerCapture?.(e.pointerId);
        pts.current = [p];
        onLive(pts.current);
      }}
      onPointerMove={(e) => {
        if (!dragging.current) return;
        const p = toLonLat(e);
        if (!p) return;
        pts.current = [...pts.current, p];
        onLive(pts.current);
      }}
      onPointerUp={(e) => {
        if (!dragging.current) return;
        dragging.current = false;
        const p = toLonLat(e);
        const all = p ? [...pts.current, p] : pts.current;
        pts.current = [];
        onLive([]);
        if (all.length) dispatch({ type: "setTrack", track: thinTrack(all) });
      }}
    />
  );
}
