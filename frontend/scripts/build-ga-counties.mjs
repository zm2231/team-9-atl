// Builds src/assets/ga-counties.topo.json from us-atlas (research R3).
// us-atlas is ISC-licensed and derived from US Census cartographic boundary files (public domain).
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const here = dirname(fileURLToPath(import.meta.url));
const src = require.resolve("us-atlas/counties-10m.json");
const version = JSON.parse(readFileSync(require.resolve("us-atlas/package.json"), "utf8")).version;

const topo = JSON.parse(readFileSync(src, "utf8"));
const geometries = topo.objects.counties.geometries.filter((g) => String(g.id).startsWith("13"));
if (geometries.length !== 159) {
  throw new Error(`Expected 159 Georgia counties, found ${geometries.length}`);
}

// Keep only the arcs Georgia uses, re-indexed, so the asset stays small.
const used = new Map();
const remap = (i) => {
  const key = i < 0 ? ~i : i;
  if (!used.has(key)) used.set(key, used.size);
  const n = used.get(key);
  return i < 0 ? ~n : n;
};
const mapArcs = (arcs) => (typeof arcs[0] === "number" ? arcs.map(remap) : arcs.map(mapArcs));
const counties = geometries.map((g) => ({ ...g, arcs: mapArcs(g.arcs) }));
const arcs = [...used.entries()].sort((a, b) => a[1] - b[1]).map(([old]) => topo.arcs[old]);

const out = {
  type: "Topology",
  transform: topo.transform,
  arcs,
  objects: { counties: { type: "GeometryCollection", geometries: counties } },
  source: `us-atlas@${version} counties-10m (ISC; US Census cartographic boundaries, public domain)`,
};
const dest = resolve(here, "../src/assets/ga-counties.topo.json");
mkdirSync(dirname(dest), { recursive: true });
writeFileSync(dest, JSON.stringify(out));
console.log(`Wrote ${counties.length} counties (${arcs.length} arcs) from us-atlas@${version} to ${dest}`);
