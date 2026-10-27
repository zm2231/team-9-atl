import { createContext, useContext, useEffect, useMemo, useRef, useState } from "react";
import { geoMercator, geoPath, type GeoPath, type GeoProjection } from "d3-geo";
import { gaCounties } from "../../lib/geo";
import { useStore } from "../../state/store";
import CountyLayer from "./CountyLayer";
import ShelterLayer from "./ShelterLayer";
import TrackDrawer from "./TrackDrawer";

interface MapGeometry {
  projection: GeoProjection;
  path: GeoPath;
  width: number;
  height: number;
}

const MapContext = createContext<MapGeometry | null>(null);

export function useMapGeometry(): MapGeometry {
  const v = useContext(MapContext);
  if (!v) throw new Error("useMapGeometry must be used inside MapView");
  return v;
}

export default function MapView() {
  const ref = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 640, height: 720 });
  const { state } = useStore();

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

  const geometry = useMemo<MapGeometry>(() => {
    const projection = geoMercator().fitSize([size.width, size.height], gaCounties);
    return { projection, path: geoPath(projection), ...size };
  }, [size]);

  return (
    <MapContext.Provider value={geometry}>
      <div ref={ref} className={`map${state.drawing ? " map--drawing" : ""}`}>
        <svg viewBox={`0 0 ${size.width} ${size.height}`} role="img" aria-label="Georgia counties and shelters">
          <CountyLayer />
          <TrackDrawer />
          <ShelterLayer />
        </svg>
      </div>
    </MapContext.Provider>
  );
}
