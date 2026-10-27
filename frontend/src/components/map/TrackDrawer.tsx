import { useMemo, useRef, useState } from "react";
import { rewind } from "@turf/turf";
import { thinTrack } from "../../lib/simulation";
import { useStore } from "../../state/store";
import { useScenario } from "../../state/scenario";
import { useMapGeometry } from "./MapView";

/**
 * While drawing mode is on, pointer down/move/up collects a track. The scenario is recomputed only
 * when the drag ends, never on pointer move (FR-016, research R5).
 */
export default function TrackDrawer() {
  const { state, dispatch } = useStore();
  const { projection, path, width, height } = useMapGeometry();
  const scenario = useScenario();
  const [live, setLive] = useState<[number, number][]>([]);
  const dragging = useRef(false);

  const toLonLat = (e: React.PointerEvent<SVGRectElement>): [number, number] | null => {
    const svg = e.currentTarget.ownerSVGElement;
    if (!svg) return null;
    const box = svg.getBoundingClientRect();
    const x = ((e.clientX - box.left) / box.width) * width;
    const y = ((e.clientY - box.top) / box.height) * height;
    return projection.invert?.([x, y]) as [number, number] | null;
  };

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
      {end && <text x={end[0] - 7} y={end[1] + 6} className="storm-glyph" fontSize="18" aria-hidden="true">🌀</text>}
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
      {state.drawing && (
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
            setLive([p]);
          }}
          onPointerMove={(e) => {
            if (!dragging.current) return;
            const p = toLonLat(e);
            if (p) setLive((pts) => [...pts, p]);
          }}
          onPointerUp={(e) => {
            if (!dragging.current) return;
            dragging.current = false;
            const p = toLonLat(e);
            const pts = p ? [...live, p] : live;
            setLive([]);
            if (pts.length) dispatch({ type: "setTrack", track: thinTrack(pts) });
          }}
        />
      )}
    </g>
  );
}
