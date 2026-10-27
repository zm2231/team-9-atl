import { feature } from "topojson-client";
import type { Topology, GeometryCollection } from "topojson-specification";
import type { Feature, FeatureCollection, MultiPolygon, Polygon } from "geojson";
import { centroid } from "@turf/turf";
import topo from "../assets/ga-counties.topo.json";

export type CountyFeature = Feature<Polygon | MultiPolygon, { name: string }> & { id: string };

const t = topo as unknown as Topology<{ counties: GeometryCollection<{ name: string }> }>;

/** Georgia's 159 counties, bundled so outlines render before map data arrives (FR-008b). */
const raw = feature(t, t.objects.counties) as unknown as FeatureCollection<Polygon | MultiPolygon, { name: string }>;

export const gaCounties: Omit<typeof raw, "features"> & { features: CountyFeature[] } = {
  ...raw,
  features: raw.features.map((f) => ({ ...f, id: String(f.id) })),
};

/** County centers used for receiving-list distances (research R6). Computed once. */
export const countyCentroids: Map<string, [number, number]> = new Map(
  gaCounties.features.map((f) => [f.id, centroid(f).geometry.coordinates as [number, number]]),
);

/** County names for every Georgia FIPS, independent of the agent's data. */
export const countyNames: Map<string, string> = new Map(gaCounties.features.map((f) => [f.id, f.properties.name]));
