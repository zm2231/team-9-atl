import { createContext, useContext, useMemo, useReducer, type Dispatch, type ReactNode } from "react";
import type { Category, ChatExchange, County, LiveCheckStatus, MapData, Shelter, WheelchairCheck } from "../lib/types";
import type { LineString, Point } from "geojson";
import { countyNames } from "../lib/geo";
import {
  MAX_QUESTIONS,
  capHistory,
  defaultName,
  toSavedQuestionText,
  type SavedScenario,
} from "../lib/history";
import { countiesAlongTrack } from "../lib/simulation";

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
  /** Scenario history (feature 002): user inputs only, mirrored to this browser's storage. */
  history: SavedScenario[];
  historyLoaded: boolean;
  historyAvailable: boolean;
  currentScenarioId: string | null;
  /** Set when a scenario is reopened from history; its results were just re-simulated (FR-008). */
  resimulatedAt: string | null;
  notice: string | null;
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
  history: [],
  historyLoaded: false,
  historyAvailable: true,
  currentScenarioId: null,
  resimulatedAt: null,
  notice: null,
};

export type Action =
  | { type: "mapLoading" }
  | { type: "mapReady"; data: MapData }
  | { type: "mapFailed"; error: string }
  | { type: "hover"; fips: string | null }
  | { type: "selectCounty"; fips: string | null }
  | { type: "selectShelter"; id: string | null }
  | { type: "highlight"; shelterIds: string[]; countyFips: string[] }
  | { type: "setTrack"; track: LineString | Point; id?: string; now?: string }
  | { type: "setCategory"; category: Category; now?: string }
  | { type: "setCutoff"; cutoff_km: number; now?: string }
  | { type: "newSimulation" }
  | { type: "historyLoaded"; scenarios: SavedScenario[]; available: boolean }
  | { type: "historyUnavailable" }
  | { type: "openScenario"; id: string; now?: string }
  | { type: "renameScenario"; id: string; name: string; now?: string }
  | { type: "deleteScenario"; id: string }
  | { type: "dismissNotice" }
  | { type: "setDrawing"; drawing: boolean }
  | { type: "setDetailsOpen"; open: boolean }
  | { type: "chatStart"; exchange: ChatExchange; now?: string }
  | { type: "chatSession"; sessionId: string }
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
    // Every input change is mirrored into the current history entry (feature 002 FR-001, FR-001c).
    case "setTrack": {
      const now = action.now ?? new Date().toISOString();
      const scenario = {
        track: action.track,
        category: state.scenario?.category ?? DEFAULT_CATEGORY,
        cutoff_km: state.scenario?.cutoff_km ?? DEFAULT_CUTOFF_KM,
      };
      const base = { ...state, drawing: false, scenario, resimulatedAt: null };
      if (state.currentScenarioId && state.history.some((h) => h.id === state.currentScenarioId)) {
        return {
          ...base,
          history: updateCurrent(state, (h) => named({ ...h, track: action.track, updated_at: now })),
        };
      }
      const created: SavedScenario = named({
        id: action.id ?? crypto.randomUUID(),
        name: "",
        nameIsCustom: false,
        track: action.track,
        category: scenario.category,
        cutoff_km: scenario.cutoff_km,
        questions: [],
        created_at: now,
        updated_at: now,
        last_opened_at: now,
      });
      const { list, evicted } = capHistory([created, ...state.history], created.id);
      return {
        ...base,
        history: list,
        currentScenarioId: created.id,
        notice: evicted ? `History is full: removed '${evicted.name}' (least recently opened)` : state.notice,
      };
    }
    case "setCategory": {
      if (!state.scenario) return state;
      const now = action.now ?? new Date().toISOString();
      return {
        ...state,
        scenario: { ...state.scenario, category: action.category },
        history: updateCurrent(state, (h) => named({ ...h, category: action.category, updated_at: now })),
      };
    }
    case "setCutoff": {
      if (!state.scenario) return state;
      const now = action.now ?? new Date().toISOString();
      return {
        ...state,
        scenario: { ...state.scenario, cutoff_km: action.cutoff_km },
        history: updateCurrent(state, (h) => ({ ...h, cutoff_km: action.cutoff_km, updated_at: now })),
      };
    }
    case "newSimulation":
      return clearScenario(state);
    case "historyLoaded":
      return { ...state, history: action.scenarios, historyLoaded: true, historyAvailable: action.available };
    case "historyUnavailable":
      return { ...state, historyAvailable: false };
    case "openScenario": {
      const entry = state.history.find((h) => h.id === action.id);
      if (!entry) return state;
      const now = action.now ?? new Date().toISOString();
      return {
        ...clearScenario(state),
        scenario: { track: entry.track, category: entry.category, cutoff_km: entry.cutoff_km },
        currentScenarioId: entry.id,
        resimulatedAt: now,
        history: state.history.map((h) => (h.id === entry.id ? { ...h, last_opened_at: now } : h)),
      };
    }
    case "renameScenario": {
      const name = action.name.trim().slice(0, 80);
      if (!name) return state;
      const now = action.now ?? new Date().toISOString();
      return {
        ...state,
        history: state.history.map((h) =>
          h.id === action.id ? { ...h, name, nameIsCustom: true, updated_at: now } : h,
        ),
      };
    }
    case "deleteScenario": {
      const rest = state.history.filter((h) => h.id !== action.id);
      return action.id === state.currentScenarioId
        ? { ...clearScenario(state), history: rest }
        : { ...state, history: rest };
    }
    case "dismissNotice":
      return { ...state, notice: null };
    case "setDrawing":
      return { ...state, drawing: action.drawing };
    case "setDetailsOpen":
      return { ...state, detailsOpen: action.open };
    case "chatSession":
      return {
        ...state,
        history: updateCurrent(state, (h) => (h.session_id === action.sessionId ? h : { ...h, session_id: action.sessionId })),
      };
    case "chatStart": {
      const now = action.now ?? new Date().toISOString();
      const text = toSavedQuestionText(action.exchange.question);
      return {
        ...state,
        chat: [...state.chat, action.exchange],
        highlight: { shelterIds: new Set(), countyFips: new Set() },
        // Only the question text is saved, never the answer or the CONTEXT part (FR-016).
        history: text
          ? updateCurrent(state, (h) => ({
              ...h,
              questions: [...h.questions, { text, asked_at: now }].slice(-MAX_QUESTIONS),
              updated_at: now,
            }))
          : state.history,
      };
    }
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

function updateCurrent(state: State, f: (h: SavedScenario) => SavedScenario): SavedScenario[] {
  return state.currentScenarioId
    ? state.history.map((h) => (h.id === state.currentScenarioId ? f(h) : h))
    : state.history;
}

/** Recomputes the default name from the track and category unless the user renamed it (FR-012). */
function named(h: SavedScenario): SavedScenario {
  if (h.nameIsCustom) return h;
  const names = countiesAlongTrack(h.track).map((f) => countyNames.get(f) ?? f);
  return { ...h, name: defaultName(h.category, names) };
}

/** New simulation: the current scenario stays saved; the map, lists and chat clear (FR-001b). */
function clearScenario(state: State): State {
  return {
    ...state,
    scenario: null,
    drawing: false,
    chat: [],
    highlight: { shelterIds: new Set(), countyFips: new Set() },
    selectedShelterId: null,
    currentScenarioId: null,
    resimulatedAt: null,
  };
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
