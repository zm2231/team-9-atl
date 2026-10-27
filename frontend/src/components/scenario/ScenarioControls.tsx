import { resetChatSession } from "../../lib/agentClient";
import { DEFAULT_CATEGORY, DEFAULT_CUTOFF_KM, useStore } from "../../state/store";
import CategoryPicker from "./CategoryPicker";
import ReachSlider from "./ReachSlider";
import UnitToggle from "./UnitToggle";

export default function ScenarioControls() {
  const { state, dispatch } = useStore();
  const s = state.scenario;
  const ready = state.mapData.status === "ready";
  return (
    <div className="controls">
      <button
        type="button"
        className="btn"
        aria-pressed={state.drawing}
        disabled={!ready}
        onClick={() => dispatch({ type: "setDrawing", drawing: !state.drawing })}
      >
        {state.drawing ? "Drag across the map…" : s ? "Redraw hurricane track" : "Draw hurricane track"}
      </button>
      <CategoryPicker
        value={s?.category ?? DEFAULT_CATEGORY}
        disabled={!s}
        onChange={(category) => dispatch({ type: "setCategory", category })}
      />
      <ReachSlider
        value={s?.cutoff_km ?? DEFAULT_CUTOFF_KM}
        unit={state.unit}
        disabled={!s}
        onChange={(cutoff_km) => dispatch({ type: "setCutoff", cutoff_km })}
      />
      <UnitToggle />
      {(s || state.currentScenarioId) && (
        // Replaces Reset: the current scenario stays in History; a new one starts on the next draw.
        <button
          type="button"
          className="btn"
          onClick={() => {
            dispatch({ type: "newSimulation" });
            resetChatSession();
          }}
        >
          New simulation
        </button>
      )}
    </div>
  );
}
