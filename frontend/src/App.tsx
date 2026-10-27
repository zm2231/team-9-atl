import { useCallback, useEffect } from "react";
import { loadMapData } from "./lib/agentClient";
import { useStore } from "./state/store";
import { ScenarioProvider, useScenario } from "./state/scenario";
import MapView from "./components/map/MapView";
import Legend from "./components/map/Legend";
import CountySummary from "./components/summary/CountySummary";
import ShelterDetails from "./components/summary/ShelterDetails";
import CouldNotTell from "./components/summary/CouldNotTell";
import ScenarioControls from "./components/scenario/ScenarioControls";
import AffectedSummary from "./components/scenario/AffectedSummary";
import ReceivingList from "./components/scenario/ReceivingList";
import ChatPanel from "./components/chat/ChatPanel";

function DataBanner({ onRetry }: { onRetry: () => void }) {
  const { state } = useStore();
  const { status, error } = state.mapData;
  if (status === "ready") return null;
  return (
    <div className={`banner banner--${status}`} role={status === "failed" ? "alert" : "status"}>
      {status === "loading" ? (
        <span>Loading Georgia shelters from the agent…</span>
      ) : (
        <>
          <span>Shelter data could not be loaded. {error}</span>
          <button type="button" onClick={onRetry}>
            Retry
          </button>
        </>
      )}
    </div>
  );
}

function SidePanel() {
  const { state } = useStore();
  const scenario = useScenario();
  return (
    <aside className="side" aria-label="Details">
      {state.selectedShelterId ? <ShelterDetails /> : <CountySummary />}
      {scenario && (
        <>
          <AffectedSummary />
          <ReceivingList />
        </>
      )}
      <CouldNotTell />
    </aside>
  );
}

export default function App() {
  const { dispatch } = useStore();

  const load = useCallback(() => {
    const ctrl = new AbortController();
    dispatch({ type: "mapLoading" });
    loadMapData(ctrl.signal)
      .then((data) => dispatch({ type: "mapReady", data }))
      .catch((e: unknown) => {
        if (!ctrl.signal.aborted) dispatch({ type: "mapFailed", error: e instanceof Error ? e.message : String(e) });
      });
    return ctrl;
  }, [dispatch]);

  useEffect(() => {
    const ctrl = load();
    return () => ctrl.abort();
  }, [load]);

  return (
    <ScenarioProvider>
      <div className="app">
        <header className="topbar">
          <h1>Georgia Shelter Readiness</h1>
          <span className="topbar__note">Planning tool · August, before the season · not for live operations</span>
        </header>
        <DataBanner onRetry={load} />
        <main className="layout">
          <section className="map-col" aria-label="Map of Georgia">
            <ScenarioControls />
            <MapView />
            <Legend />
          </section>
          <SidePanel />
          <ChatPanel />
        </main>
      </div>
    </ScenarioProvider>
  );
}
