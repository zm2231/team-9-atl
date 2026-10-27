import { createContext, useContext, useMemo, type ReactNode } from "react";
import { countyCentroids, gaCounties } from "../lib/geo";
import { HALF_WIDTH_KM, affected, computeBand, receivingList } from "../lib/simulation";
import type { HurricaneScenario } from "../lib/types";
import { useStore } from "./store";

const ScenarioContext = createContext<HurricaneScenario | null>(null);

/**
 * Derives the scenario once per input change (track set on drag end, category, cutoff), so every
 * consumer — map, side panel, chat context — sees the same affected set and receiving list.
 */
export function ScenarioProvider({ children }: { children: ReactNode }) {
  const { state } = useStore();
  const input = state.scenario;
  const shelters = state.mapData.data?.shelters;

  // The geometry depends only on track and category, so moving the cutoff never recomputes it.
  const track = input?.track;
  const category = input?.category;
  const geometry = useMemo(() => {
    if (!track || !category) return null;
    const band = computeBand(track, category);
    const hit = affected(band, shelters ?? [], gaCounties.features);
    return { band, ...hit };
  }, [track, category, shelters]);

  const scenario = useMemo<HurricaneScenario | null>(() => {
    if (!input || !geometry) return null;
    return {
      track: input.track,
      category: input.category,
      half_width_km: HALF_WIDTH_KM[input.category],
      band: geometry.band,
      cutoff_km: input.cutoff_km,
      affected_county_fips: geometry.countyFips,
      affected_shelter_ids: geometry.shelterIds,
      receiving: receivingList(
        shelters ?? [],
        new Set(geometry.shelterIds),
        geometry.countyFips,
        countyCentroids,
        input.cutoff_km,
      ),
    };
  }, [input, geometry, shelters]);

  return <ScenarioContext.Provider value={scenario}>{children}</ScenarioContext.Provider>;
}

export function useScenario(): HurricaneScenario | null {
  return useContext(ScenarioContext);
}
