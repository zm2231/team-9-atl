import { createContext, useContext, useMemo, useReducer, type Dispatch, type ReactNode } from "react";
import type { Category, ChatExchange, County, LiveCheckStatus, MapData, Shelter, WheelchairCheck } from "../lib/types";
import type { LineString, Point } from "geojson";

export interface ScenarioInput {
  track: LineString | Point;
  category: Category;
  cutoff_km: number;
}

export interface State {
  mapData: { status: "loading" | "ready" | "failed"; data?: MapData; error?: string };
  hoverFips: string | null;
  lastHoverFips: string | null;
  selectedFips: string | null;
  selectedShelterId: string | null;
  highlight: { shelterIds: Set<string>; countyFips: Set<string> };
  scenario: ScenarioInput | null;
  drawing: boolean;
  /** The details panel is collapsed by default; only the user's toggle changes it. */
  detailsOpen: boolean;
  /** Session memory only: status and place ids per shelter, never titles/URIs/text (FR-022). */
  liveChecks: Map<string, { status: LiveCheckStatus; placeIds: string[]; checked_at: string }>;
  /** Google Maps wheelchair lookups, shown with attribution and kept only while the page is open. */
  wheelchairChecks: Map<string, WheelchairCheck>;
  chat: ChatExchange[];
}

export const DEFAULT_CATEGORY: Category = 3;
export const DEFAULT_CUTOFF_KM = 80;

export const initialState: State = {
  mapData: { status: "loading" },
  hoverFips: null,
  lastHoverFips: null,
  selectedFips: null,
  selectedShelterId: null,
  highlight: { shelterIds: new Set(), countyFips: new Set() },
  scenario: null,
  drawing: false,
  detailsOpen: false,
  liveChecks: new Map(),
  wheelchairChecks: new Map(),
  chat: [],
};

export type Action =
  | { type: "mapLoading" }
  | { type: "mapReady"; data: MapData }
  | { type: "mapFailed"; error: string }
  | { type: "hover"; fips: string | null }
  | { type: "selectCounty"; fips: string | null }
  | { type: "selectShelter"; id: string | null }
  | { type: "highlight"; shelterIds: string[]; countyFips: string[] }
  | { type: "setTrack"; track: LineString | Point }
  | { type: "setCategory"; category: Category }
  | { type: "setCutoff"; cutoff_km: number }
  | { type: "resetScenario" }
  | { type: "setDrawing"; drawing: boolean }
  | { type: "setDetailsOpen"; open: boolean }
  | { type: "chatStart"; exchange: ChatExchange }
  | { type: "chatUpdate"; id: string; patch: Partial<ChatExchange> }
  | { type: "liveCheck"; shelterId: string; status: LiveCheckStatus; placeIds: string[] }
  | { type: "wheelchairChecked"; results: WheelchairCheck[] };

export function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "mapLoading":
      return { ...state, mapData: { status: "loading" } };
    case "mapReady":
      return { ...state, mapData: { status: "ready", data: action.data } };
    case "mapFailed":
      return { ...state, mapData: { status: "failed", error: action.error } };
    case "hover":
      return {
        ...state,
        hoverFips: action.fips,
        lastHoverFips: action.fips ?? state.lastHoverFips,
      };
    case "selectCounty":
      return { ...state, selectedFips: action.fips, selectedShelterId: null };
    case "selectShelter":
      return { ...state, selectedShelterId: action.id };
    case "highlight":
      return {
        ...state,
        highlight: { shelterIds: new Set(action.shelterIds), countyFips: new Set(action.countyFips) },
      };
    // Scenario inputs only; derived results are computed once in ScenarioProvider (research R5).
    case "setTrack":
      return {
        ...state,
        drawing: false,
        scenario: {
          track: action.track,
          category: state.scenario?.category ?? DEFAULT_CATEGORY,
          cutoff_km: state.scenario?.cutoff_km ?? DEFAULT_CUTOFF_KM,
        },
      };
    case "setCategory":
      return state.scenario ? { ...state, scenario: { ...state.scenario, category: action.category } } : state;
    case "setCutoff":
      return state.scenario ? { ...state, scenario: { ...state.scenario, cutoff_km: action.cutoff_km } } : state;
    case "resetScenario":
      return { ...state, scenario: null, drawing: false };
    case "setDrawing":
      return { ...state, drawing: action.drawing };
    case "setDetailsOpen":
      return { ...state, detailsOpen: action.open };
    case "chatStart":
      return {
        ...state,
        chat: [...state.chat, action.exchange],
        highlight: { shelterIds: new Set(), countyFips: new Set() },
      };
    case "chatUpdate":
      return {
        ...state,
        chat: state.chat.map((c) => (c.id === action.id ? { ...c, ...action.patch } : c)),
      };
    case "liveCheck": {
      const liveChecks = new Map(state.liveChecks);
      liveChecks.set(action.shelterId, {
        status: action.status,
        placeIds: action.placeIds,
        checked_at: new Date().toISOString(),
      });
      return { ...state, liveChecks };
    }
    case "wheelchairChecked": {
      const wheelchairChecks = new Map(state.wheelchairChecks);
      for (const r of action.results) wheelchairChecks.set(r.shelter_id, r);
      return { ...state, wheelchairChecks };
    }
  }
}

interface StoreValue {
  state: State;
  dispatch: Dispatch<Action>;
  countyByFips: Map<string, County>;
  shelterById: Map<string, Shelter>;
}

const StoreContext = createContext<StoreValue | null>(null);

export function StoreProvider({ children, initial }: { children: ReactNode; initial?: Partial<State> }) {
  const [state, dispatch] = useReducer(reducer, { ...initialState, ...initial });
  const data = state.mapData.data;
  const countyByFips = useMemo(() => new Map((data?.counties ?? []).map((c) => [c.county_fips, c])), [data]);
  const shelterById = useMemo(() => new Map((data?.shelters ?? []).map((s) => [s.shelter_id, s])), [data]);
  const value = useMemo(
    () => ({ state, dispatch, countyByFips, shelterById }),
    [state, countyByFips, shelterById],
  );
  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}

export function useStore(): StoreValue {
  const v = useContext(StoreContext);
  if (!v) throw new Error("useStore must be used inside StoreProvider");
  return v;
}
